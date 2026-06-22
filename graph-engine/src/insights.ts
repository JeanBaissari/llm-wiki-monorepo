// Graph Engine — Insights: Surprising Connections + Knowledge Gaps
// Port of nashsu's graph-insights.ts logic.

import {
  GraphNode,
  GraphEdge,
  CommunityInfo,
  SurprisingConnection,
  KnowledgeGap,
} from './types.js';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build degree (total connections) map for all nodes. */
function computeDegree(nodes: GraphNode[], edges: GraphEdge[]): Map<string, number> {
  const degree = new Map<string, number>();
  for (const n of nodes) degree.set(n.id, 0);
  for (const e of edges) {
    degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
    degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
  }
  return degree;
}

/** Structural (non-content) page types that should be excluded from certain gap types. */
const STRUCTURAL_TYPES = new Set(['index', 'log', 'overview']);

/**
 * Check whether a pair of types is considered a "distant" cross-type pair.
 * Distant pairs receive a higher signal weight (+2 vs +1).
 */
function isDistantTypePair(t1: string, t2: string): boolean {
  const pair = [t1.toLowerCase(), t2.toLowerCase()].sort().join('-');
  return pair === 'concept-source';
  // Note: original nashsu code also included 'entity-query' as a distant pair;
  // "query" is not a standard type in this wiki schema so it is omitted here.
}

// ---------------------------------------------------------------------------
// Surprising Connections
// ---------------------------------------------------------------------------

/**
 * Find surprising connections in the knowledge graph.
 *
 * Four signals contribute to the surprise score:
 * 1. Cross-community edge         (+3)
 * 2. Cross-type edge              (+2 distant pair / +1 otherwise)
 * 3. Peripheral-to-hub            (+2)
 * 4. Low-weight edge              (+1)
 *
 * Only edges with a total score ≥ 3 are returned, sorted descending.
 *
 * @param nodes       All graph nodes.
 * @param edges       All graph edges.
 * @param communities Community metadata (used for cross-community detection).
 * @param limit       Maximum number of results (default 5).
 */
export function findSurprisingConnections(
  nodes: GraphNode[],
  edges: GraphEdge[],
  communities: CommunityInfo[],
  limit: number = 5,
): SurprisingConnection[] {
  if (nodes.length === 0 || edges.length === 0) return [];

  const nodeMap = new Map<string, GraphNode>();
  for (const n of nodes) nodeMap.set(n.id, n);

  const degree = computeDegree(nodes, edges);
  const maxDegree = degree.size > 0
    ? Math.max(...Array.from(degree.values()))
    : 1;

  const candidates: SurprisingConnection[] = [];

  for (const edge of edges) {
    const source = nodeMap.get(edge.source);
    const target = nodeMap.get(edge.target);
    if (!source || !target) continue;

    let score = 0;
    const reasons: string[] = [];

    // Signal 1: Cross-community edge (+3)
    if (source.community !== target.community) {
      score += 3;
      reasons.push('cross-community edge');
    }

    // Signal 2: Cross-type edge (+2 distant pair, +1 otherwise)
    if (source.type !== target.type) {
      if (isDistantTypePair(source.type, target.type)) {
        score += 2;
        reasons.push('cross-type edge (distant pair)');
      } else {
        score += 1;
        reasons.push('cross-type edge');
      }
    }

    // Signal 3: Peripheral-to-hub (+2)
    const sourceDeg = degree.get(source.id) ?? 0;
    const targetDeg = degree.get(target.id) ?? 0;
    const minDeg = Math.min(sourceDeg, targetDeg);
    const maxDeg = Math.max(sourceDeg, targetDeg);
    if (minDeg <= 2 && maxDeg >= maxDegree * 0.5) {
      score += 2;
      reasons.push('peripheral-to-hub connection');
    }

    // Signal 4: Low-weight edge (+1)
    if (edge.weight > 0 && edge.weight < 2) {
      score += 1;
      reasons.push('low-weight edge');
    }

    // Minimum score threshold
    if (score >= 3) {
      candidates.push({
        source,
        target,
        score,
        reasons,
        key: `${source.id}\u2194${target.id}`,  // ↔ arrow
      });
    }
  }

  // Sort descending by score
  candidates.sort((a, b) => b.score - a.score);
  return candidates.slice(0, limit);
}

// ---------------------------------------------------------------------------
// Knowledge Gaps
// ---------------------------------------------------------------------------

/**
 * Detect knowledge gaps in the graph.
 *
 * Three gap types are identified:
 * 1. **isolated-node**   — degree ≤ 1, not a structural page.
 * 2. **sparse-community** — cohesion < 0.15, ≥ 3 nodes.
 * 3. **bridge-node**     — connected to 3+ communities, not structural.
 *
 * @param nodes       All graph nodes.
 * @param edges       All graph edges.
 * @param communities Community metadata.
 * @param limit       Maximum number of gaps to return (default 8).
 */
export function detectKnowledgeGaps(
  nodes: GraphNode[],
  edges: GraphEdge[],
  communities: CommunityInfo[],
  limit: number = 8,
): KnowledgeGap[] {
  const gaps: KnowledgeGap[] = [];
  const nodeMap = new Map<string, GraphNode>();
  for (const n of nodes) nodeMap.set(n.id, n);

  // ---- Type 1: Isolated nodes ----
  const degree = computeDegree(nodes, edges);

  for (const node of nodes) {
    if (STRUCTURAL_TYPES.has(node.type)) continue;
    const deg = degree.get(node.id) ?? 0;
    if (deg <= 1) {
      gaps.push({
        type: 'isolated-node',
        title: `Isolated Node: "${node.label}"`,
        description: `Node "${node.label}" (${node.id}) has only ${deg} connection${
          deg === 1 ? '' : 's'
        } and may be disconnected from the rest of the graph.`,
        nodeIds: [node.id],
        suggestion: `Consider adding more wikilinks to/from "${node.label}" to integrate it better with related topics.`,
      });
    }
  }

  // ---- Type 2: Sparse communities ----
  for (const comm of communities) {
    if (comm.cohesion < 0.15 && comm.nodeCount >= 3) {
      gaps.push({
        type: 'sparse-community',
        title: `Sparse Community #${comm.id}`,
        description: `Community #${comm.id} has low cohesion (${comm.cohesion.toFixed(
          3,
        )}) with ${comm.nodeCount} nodes, suggesting weak internal connectivity.`,
        nodeIds: comm.topNodes.slice(),
        suggestion: `Add more cross-links among members of community #${comm.id} to strengthen internal connections.`,
      });
    }
  }

  // ---- Type 3: Bridge nodes (connected to 3+ communities) ----
  // For each node, collect the set of communities its neighbours belong to.
  const communityLinks = new Map<string, Set<number>>();
  for (const node of nodes) communityLinks.set(node.id, new Set<number>());

  for (const edge of edges) {
    const source = nodeMap.get(edge.source);
    const target = nodeMap.get(edge.target);
    if (!source || !target) continue;
    communityLinks.get(source.id)!.add(target.community);
    communityLinks.get(target.id)!.add(source.community);
  }

  for (const node of nodes) {
    if (STRUCTURAL_TYPES.has(node.type)) continue;
    const connectedComms = communityLinks.get(node.id);
    if (connectedComms && connectedComms.size >= 3) {
      gaps.push({
        type: 'bridge-node',
        title: `Bridge Node: "${node.label}"`,
        description: `Node "${node.label}" connects ${connectedComms.size} different communities, acting as a bridge across knowledge domains.`,
        nodeIds: [node.id],
        suggestion: `Ensure "${node.label}" has sufficient content depth to properly bridge these communities.`,
      });
    }
  }

  // Sort: isolated-node → sparse-community → bridge-node
  const typeOrder: Record<string, number> = {
    'isolated-node': 0,
    'sparse-community': 1,
    'bridge-node': 2,
  };
  gaps.sort((a, b) => (typeOrder[a.type] ?? 99) - (typeOrder[b.type] ?? 99));

  return gaps.slice(0, limit);
}
