import type { GraphNode, GraphEdge } from './types.js';

const WEIGHTS = {
  directLink: 3.0,
  sourceOverlap: 4.0,
  commonNeighbor: 1.5,
  typeAffinity: 1.0,
} as const;

export interface RelevanceOptions {
  weights?: {
    directLink?: number;
    sourceOverlap?: number;
    commonNeighbor?: number;
    typeAffinity?: number;
  };
  typeAffinityMatrix?: Record<string, Record<string, number>>;
}

export function buildSourceIndex(nodes: GraphNode[]): Map<string, string[]> {
  const index = new Map<string, string[]>();
  for (const node of nodes) {
    const sources = node.sources;
    if (sources) {
      for (const src of sources) {
        if (!index.has(src)) index.set(src, []);
        index.get(src)!.push(node.id);
      }
    }
  }
  return index;
}

const TYPE_AFFINITY: Record<string, Record<string, number>> = {
  entity: { concept: 1.2, entity: 0.8, source: 1.0, synthesis: 1.0, query: 0.8 },
  concept: { entity: 1.2, concept: 0.8, source: 1.0, synthesis: 1.2, query: 1.0 },
  source: { entity: 1.0, concept: 1.0, source: 0.5, query: 0.8, synthesis: 1.0 },
  query: { concept: 1.0, entity: 0.8, synthesis: 1.0, source: 0.8, query: 0.5 },
  synthesis: { concept: 1.2, entity: 1.0, source: 1.0, query: 1.0, synthesis: 0.8 },
};

export interface RetrievalNode {
  id: string;
  outLinks: Set<string>;
  sources: string[];
  type: string;
}

export interface RetrievalGraph {
  nodes: Map<string, RetrievalNode>;
}

export interface GraphStructure {
  adjacency: Map<string, Set<string>>;
  neighbors: Map<string, Set<string>>;
  degree: Map<string, number>;
}

export function buildGraphStructure(edges: GraphEdge[]): GraphStructure {
  const adjacency = new Map<string, Set<string>>();
  const neighbors = new Map<string, Set<string>>();
  const degree = new Map<string, number>();

  for (const edge of edges) {
    // Directed adjacency: only source→target
    if (!adjacency.has(edge.source)) adjacency.set(edge.source, new Set());
    adjacency.get(edge.source)!.add(edge.target);

    // Undirected neighbors: both directions
    if (!neighbors.has(edge.source)) neighbors.set(edge.source, new Set());
    neighbors.get(edge.source)!.add(edge.target);
    if (!neighbors.has(edge.target)) neighbors.set(edge.target, new Set());
    neighbors.get(edge.target)!.add(edge.source);

    // Degree: count each edge occurrence for both nodes
    degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
  }

  return { adjacency, neighbors, degree };
}

export function getNeighbors(nodeId: string, edges: GraphEdge[]): Set<string> {
  const neighbors = new Set<string>();
  for (const edge of edges) {
    if (edge.source === nodeId) neighbors.add(edge.target);
    if (edge.target === nodeId) neighbors.add(edge.source);
  }
  return neighbors;
}

export function getNodeDegree(nodeId: string, edges: GraphEdge[]): number {
  let degree = 0;
  for (const edge of edges) {
    if (edge.source === nodeId || edge.target === nodeId) degree++;
  }
  return degree;
}

export function calculateRelevance(
  nodeA: GraphNode,
  nodeB: GraphNode,
  _nodes: GraphNode[],
  structure: GraphStructure,
  nodeMap: Map<string, GraphNode>,
  options?: RelevanceOptions,
): number {
  if (nodeA.id === nodeB.id) return 0;

  const w = { ...WEIGHTS, ...options?.weights };
  const affinity = options?.typeAffinityMatrix ?? TYPE_AFFINITY;

  const degA = structure.degree.get(nodeA.id) ?? 0;
  const degB = structure.degree.get(nodeB.id) ?? 0;

  const affinityMap = affinity[nodeA.type];
  const typeAffinityScore = (affinityMap?.[nodeB.type] ?? 0.5) * w.typeAffinity;

  if (degA === 0 && degB === 0) return typeAffinityScore;

  let forwardLinks = 0;
  let backwardLinks = 0;
  const adjA = structure.adjacency.get(nodeA.id);
  const adjB = structure.adjacency.get(nodeB.id);
  if (adjA?.has(nodeB.id)) forwardLinks = 1;
  if (adjB?.has(nodeA.id)) backwardLinks = 1;
  const directLinkScore = (forwardLinks + backwardLinks) * w.directLink;

  const nodeASources = getEnrichedSources(nodeA.id, nodeMap);
  const nodeBSources = getEnrichedSources(nodeB.id, nodeMap);
  let sharedSourceCount = 0;
  if (nodeASources && nodeBSources) {
    const sourcesA = new Set(nodeASources);
    for (const src of nodeBSources) {
      if (sourcesA.has(src)) sharedSourceCount++;
    }
  }
  const sourceOverlapScore = sharedSourceCount * w.sourceOverlap;

  const neighborsA = structure.neighbors.get(nodeA.id);
  const neighborsB = structure.neighbors.get(nodeB.id);
  let adamicAdar = 0;
  if (neighborsA && neighborsB) {
    for (const neighborId of neighborsA) {
      if (neighborsB.has(neighborId)) {
        const degree = structure.degree.get(neighborId) ?? 2;
        adamicAdar += 1 / Math.log(Math.max(degree, 2));
      }
    }
  }
  const commonNeighborScore = adamicAdar * w.commonNeighbor;

  return directLinkScore + sourceOverlapScore + commonNeighborScore + typeAffinityScore;
}

export function getRelatedNodes(
  nodeId: string,
  nodes: GraphNode[],
  structure: GraphStructure,
  limit: number = 5,
): { node: GraphNode; score: number }[] {
  const nodeMap = new Map<string, GraphNode>();
  for (const n of nodes) nodeMap.set(n.id, n);

  const targetNode = nodeMap.get(nodeId);
  if (!targetNode) return [];

  const scored: { node: GraphNode; score: number }[] = [];

  for (const other of nodes) {
    if (other.id === nodeId) continue;
    const score = calculateRelevance(targetNode, other, nodes, structure, nodeMap);
    scored.push({ node: other, score });
  }

  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, limit);
}

function getEnrichedSources(
  nodeId: string,
  nodeMap: Map<string, GraphNode>,
  _sourceIndex?: Map<string, string[]>,
): string[] | undefined {
  const entry = nodeMap.get(nodeId);
  if (!entry) return undefined;
  return entry.sources;
}
