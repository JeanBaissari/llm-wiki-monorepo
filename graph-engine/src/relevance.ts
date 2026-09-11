// Graph Engine — 4-signal relevance model.
//
// Clean-room, original MIT implementation (2026-09). Independently written
// against the behavioral contract in graph-engine/test/test_relevance.test.ts
// and the public API consumed by build.ts / index.ts / tuning.ts. No
// third-party source code was reproduced.

import type { GraphNode, GraphEdge } from './types.js';

const DEFAULT_WEIGHTS = {
  directLink: 3.0,
  sourceOverlap: 4.0,
  commonNeighbor: 1.5,
  typeAffinity: 1.0,
} as const;

const UNKNOWN_PAIR_AFFINITY = 0.5;

export interface RelevanceOptions {
  weights?: {
    directLink?: number;
    sourceOverlap?: number;
    commonNeighbor?: number;
    typeAffinity?: number;
  };
  typeAffinityMatrix?: Record<string, Record<string, number>>;
}

const DEFAULT_TYPE_AFFINITY: Record<string, Record<string, number>> = {
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

type WeightSet = { [K in keyof typeof DEFAULT_WEIGHTS]: number };

function linkOnce(index: Map<string, Set<string>>, from: string, to: string): void {
  const bucket = index.get(from);
  if (bucket) {
    bucket.add(to);
  } else {
    index.set(from, new Set([to]));
  }
}

/** Precompute directed adjacency, undirected neighbors and per-edge degree counts. */
export function buildGraphStructure(edges: GraphEdge[]): GraphStructure {
  const adjacency = new Map<string, Set<string>>();
  const neighbors = new Map<string, Set<string>>();
  const degree = new Map<string, number>();

  for (const { source, target } of edges) {
    linkOnce(adjacency, source, target);
    linkOnce(neighbors, source, target);
    linkOnce(neighbors, target, source);

    degree.set(source, (degree.get(source) ?? 0) + 1);
    degree.set(target, (degree.get(target) ?? 0) + 1);
  }

  return { adjacency, neighbors, degree };
}

function resolveWeights(options?: RelevanceOptions): WeightSet {
  return { ...DEFAULT_WEIGHTS, ...options?.weights };
}

function affinityFor(
  sourceType: string,
  targetType: string,
  matrix: Record<string, Record<string, number>>,
): number {
  return matrix[sourceType]?.[targetType] ?? UNKNOWN_PAIR_AFFINITY;
}

function sharedSourceCount(
  leftId: string,
  rightId: string,
  nodeMap: Map<string, GraphNode>,
): number {
  const leftSources = nodeMap.get(leftId)?.sources;
  const rightSources = nodeMap.get(rightId)?.sources;
  if (!leftSources || !rightSources) return 0;

  const leftSet = new Set(leftSources);
  let shared = 0;
  for (const source of rightSources) {
    if (leftSet.has(source)) shared += 1;
  }
  return shared;
}

function adamicAdarScore(
  leftId: string,
  rightId: string,
  structure: GraphStructure,
): number {
  const leftNeighbors = structure.neighbors.get(leftId);
  const rightNeighbors = structure.neighbors.get(rightId);
  if (!leftNeighbors || !rightNeighbors) return 0;

  let weight = 0;
  for (const neighborId of leftNeighbors) {
    if (!rightNeighbors.has(neighborId)) continue;
    const neighborDegree = structure.degree.get(neighborId) ?? 2;
    weight += 1 / Math.log(Math.max(neighborDegree, 2));
  }
  return weight;
}

/**
 * Score how strongly two nodes relate using four additive signals:
 * direct links (both orientations), shared sources, Adamic-Adar over common
 * neighbors, and a type-affinity prior. Same-id pairs score 0; two nodes with
 * no incident edges fall back to the type-affinity term alone.
 */
export function calculateRelevance(
  nodeA: GraphNode,
  nodeB: GraphNode,
  _nodes: GraphNode[],
  structure: GraphStructure,
  nodeMap: Map<string, GraphNode>,
  options?: RelevanceOptions,
): number {
  if (nodeA.id === nodeB.id) return 0;

  const weights = resolveWeights(options);
  const typeAffinityScore =
    affinityFor(
      nodeA.type,
      nodeB.type,
      options?.typeAffinityMatrix ?? DEFAULT_TYPE_AFFINITY,
    ) * weights.typeAffinity;

  const degreeA = structure.degree.get(nodeA.id) ?? 0;
  const degreeB = structure.degree.get(nodeB.id) ?? 0;
  if (degreeA === 0 && degreeB === 0) return typeAffinityScore;

  const forward = structure.adjacency.get(nodeA.id)?.has(nodeB.id) ? 1 : 0;
  const backward = structure.adjacency.get(nodeB.id)?.has(nodeA.id) ? 1 : 0;
  const directLinkScore = (forward + backward) * weights.directLink;

  const sourceOverlapScore =
    sharedSourceCount(nodeA.id, nodeB.id, nodeMap) * weights.sourceOverlap;

  const commonNeighborScore =
    adamicAdarScore(nodeA.id, nodeB.id, structure) * weights.commonNeighbor;

  return directLinkScore + sourceOverlapScore + commonNeighborScore + typeAffinityScore;
}

/** Rank every other node against `nodeId`, highest score first (stable on ties). */
export function getRelatedNodes(
  nodeId: string,
  nodes: GraphNode[],
  structure: GraphStructure,
  limit: number = 5,
  options?: RelevanceOptions,
): { node: GraphNode; score: number }[] {
  const nodeMap = new Map<string, GraphNode>();
  for (const node of nodes) nodeMap.set(node.id, node);

  const anchor = nodeMap.get(nodeId);
  if (!anchor) return [];

  const ranked: { node: GraphNode; score: number }[] = [];
  for (const candidate of nodes) {
    if (candidate.id === nodeId) continue;
    ranked.push({
      node: candidate,
      score: calculateRelevance(anchor, candidate, nodes, structure, nodeMap, options),
    });
  }

  ranked.sort((left, right) => right.score - left.score);
  return ranked.slice(0, limit);
}
