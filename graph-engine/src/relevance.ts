// ============================================================
// graph-engine/src/relevance.ts — 4-Signal Relevance Model
// Ported from nashsu/llm_wiki src/lib/graph-relevance.ts
// ============================================================

import type { GraphNode, GraphEdge } from './types.js';

// ============================================================
// Weights
// ============================================================

const WEIGHTS = {
  directLink: 3.0,
  sourceOverlap: 4.0,
  commonNeighbor: 1.5,
  typeAffinity: 1.0,
} as const;

// ============================================================
// Type affinity lookup table
// ============================================================

const TYPE_AFFINITY: Record<string, Record<string, number>> = {
  entity: { concept: 1.2, entity: 0.8, source: 1.0, synthesis: 1.0, query: 0.8 },
  concept: { entity: 1.2, concept: 0.8, source: 1.0, synthesis: 1.2, query: 1.0 },
  source: { entity: 1.0, concept: 1.0, source: 0.5, query: 0.8, synthesis: 1.0 },
  query: { concept: 1.0, entity: 0.8, synthesis: 1.0, source: 0.8, query: 0.5 },
  synthesis: { concept: 1.2, entity: 1.0, source: 1.0, query: 1.0, synthesis: 0.8 },
};

// ============================================================
// RetrievalGraph types (for external consumers / build.ts)
// ============================================================

export interface RetrievalNode {
  id: string;
  outLinks: Set<string>;
  sources: string[];
  type: string;
}

export interface RetrievalGraph {
  nodes: Map<string, RetrievalNode>;
}

// ============================================================
// Graph helpers
// ============================================================

/**
 * Get all neighboring node IDs for a given node from the edge list.
 * Treats edges as undirected.
 */
export function getNeighbors(nodeId: string, edges: GraphEdge[]): Set<string> {
  const neighbors = new Set<string>();
  for (const edge of edges) {
    if (edge.source === nodeId) neighbors.add(edge.target);
    if (edge.target === nodeId) neighbors.add(edge.source);
  }
  return neighbors;
}

/**
 * Get the degree (number of incident edges) for a node.
 */
export function getNodeDegree(nodeId: string, edges: GraphEdge[]): number {
  let degree = 0;
  for (const edge of edges) {
    if (edge.source === nodeId || edge.target === nodeId) degree++;
  }
  return degree;
}

// ============================================================
// Core: 4-signal relevance calculation
// ============================================================

/**
 * Calculate the 4-signal relevance score between two nodes.
 *
 * Signal 1 — Direct links (weight 3.0): count of forward+backward edges between nodes
 * Signal 2 — Source overlap (weight 4.0): shared source count × weight
 * Signal 3 — Common neighbors / Adamic-Adar (weight 1.5): Σ 1/log(degree) for shared neighbors
 * Signal 4 — Type affinity (weight 1.0): lookup table based on node types
 *
 * @param nodeA   - First node
 * @param nodeB   - Second node
 * @param nodes   - All graph nodes (for lookups)
 * @param edges   - All graph edges
 * @param nodeMap - Fast node lookup map; entries MAY carry extra fields like `sources`
 *                  (set by build.ts for signal 2 support)
 */
export function calculateRelevance(
  nodeA: GraphNode,
  nodeB: GraphNode,
  _nodes: GraphNode[],
  edges: GraphEdge[],
  nodeMap: Map<string, GraphNode>,
): number {
  if (nodeA.id === nodeB.id) return 0;

  // ── Signal 1: Direct links ──────────────────────────────────
  let forwardLinks = 0;
  let backwardLinks = 0;
  for (const edge of edges) {
    if (edge.source === nodeA.id && edge.target === nodeB.id) forwardLinks = 1;
    if (edge.source === nodeB.id && edge.target === nodeA.id) backwardLinks = 1;
    if (forwardLinks && backwardLinks) break;
  }
  const directLinkScore = (forwardLinks + backwardLinks) * WEIGHTS.directLink;

  // ── Signal 2: Source overlap ────────────────────────────────
  // Sources are NOT part of GraphNode; build.ts enriches nodeMap entries
  // with a `sources` property when source data is available.
  const nodeASources = getEnrichedSources(nodeA.id, nodeMap);
  const nodeBSources = getEnrichedSources(nodeB.id, nodeMap);
  let sharedSourceCount = 0;
  if (nodeASources && nodeBSources) {
    const sourcesA = new Set(nodeASources);
    for (const src of nodeBSources) {
      if (sourcesA.has(src)) sharedSourceCount++;
    }
  }
  const sourceOverlapScore = sharedSourceCount * WEIGHTS.sourceOverlap;

  // ── Signal 3: Common neighbors / Adamic-Adar ────────────────
  const neighborsA = getNeighbors(nodeA.id, edges);
  const neighborsB = getNeighbors(nodeB.id, edges);
  let adamicAdar = 0;
  for (const neighborId of neighborsA) {
    if (neighborsB.has(neighborId)) {
      const degree = getNodeDegree(neighborId, edges);
      adamicAdar += 1 / Math.log(Math.max(degree, 2));
    }
  }
  const commonNeighborScore = adamicAdar * WEIGHTS.commonNeighbor;

  // ── Signal 4: Type affinity ─────────────────────────────────
  const affinityMap = TYPE_AFFINITY[nodeA.type];
  const typeAffinityScore = (affinityMap?.[nodeB.type] ?? 0.5) * WEIGHTS.typeAffinity;

  return directLinkScore + sourceOverlapScore + commonNeighborScore + typeAffinityScore;
}

/**
 * Get top-N related nodes for a given node, sorted by relevance score descending.
 *
 * @param nodeId - ID of the node to find relations for
 * @param nodes  - All graph nodes
 * @param edges  - All graph edges
 * @param limit  - Maximum number of results (default: 5)
 */
export function getRelatedNodes(
  nodeId: string,
  nodes: GraphNode[],
  edges: GraphEdge[],
  limit: number = 5,
): { node: GraphNode; score: number }[] {
  const nodeMap = new Map<string, GraphNode>();
  for (const n of nodes) nodeMap.set(n.id, n);

  const targetNode = nodeMap.get(nodeId);
  if (!targetNode) return [];

  const scored: { node: GraphNode; score: number }[] = [];

  for (const other of nodes) {
    if (other.id === nodeId) continue;
    const score = calculateRelevance(targetNode, other, nodes, edges, nodeMap);
    scored.push({ node: other, score });
  }

  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, limit);
}

// ============================================================
// Internal helpers
// ============================================================

/**
 * Extract `sources` array from a nodeMap entry if it was enriched by build.ts.
 * Returns undefined when the field doesn't exist (graceful degradation).
 */
function getEnrichedSources(
  nodeId: string,
  nodeMap: Map<string, GraphNode>,
): string[] | undefined {
  const entry = nodeMap.get(nodeId);
  if (!entry) return undefined;
  // Enriched nodes carry `sources` as an extra own property
  return (entry as GraphNode & { sources?: string[] }).sources;
}
