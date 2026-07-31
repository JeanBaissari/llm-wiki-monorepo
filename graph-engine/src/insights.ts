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
// Configurable options
// ---------------------------------------------------------------------------

export interface InsightsOptions {
  surpriseThreshold?: number;
  sparseCohesionThreshold?: number;
  sparseMinNodes?: number;
  bridgeCommunityMin?: number;
  peripheralMaxDegree?: number;
  peripheralHubRatio?: number;
  structuralTypes?: string[];
  limit?: number;
}

export const DEFAULT_INSIGHTS_OPTIONS: Required<InsightsOptions> = {
  surpriseThreshold: 3,
  sparseCohesionThreshold: 0.15,
  sparseMinNodes: 3,
  bridgeCommunityMin: 3,
  peripheralMaxDegree: 2,
  peripheralHubRatio: 0.5,
  structuralTypes: [],
  limit: 8,
};

function mergeOptions(overrides?: InsightsOptions): Required<InsightsOptions> {
  if (!overrides) return DEFAULT_INSIGHTS_OPTIONS;
  return { ...DEFAULT_INSIGHTS_OPTIONS, ...overrides };
}

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
}

// ---------------------------------------------------------------------------
// Surprise Signal Registry
// ---------------------------------------------------------------------------

export type SurpriseSignalFn = (
  edge: GraphEdge,
  source: GraphNode,
  target: GraphNode,
  degree: Map<string, number>,
  maxDegree: number,
  options: Required<InsightsOptions>,
) => { score: number; reason: string } | null;

export function crossCommunitySignal(
  edge: GraphEdge,
  source: GraphNode,
  target: GraphNode,
  _degree: Map<string, number>,
  _maxDegree: number,
  _options: Required<InsightsOptions>,
): { score: number; reason: string } | null {
  if (source.community !== target.community) {
    return { score: 3, reason: 'cross-community edge' };
  }
  return null;
}

export function crossTypeSignal(
  _edge: GraphEdge,
  source: GraphNode,
  target: GraphNode,
  _degree: Map<string, number>,
  _maxDegree: number,
  _options: Required<InsightsOptions>,
): { score: number; reason: string } | null {
  if (source.type !== target.type) {
    if (isDistantTypePair(source.type, target.type)) {
      return { score: 2, reason: 'cross-type edge (distant pair)' };
    }
    return { score: 1, reason: 'cross-type edge' };
  }
  return null;
}

export function peripheralToHubSignal(
  _edge: GraphEdge,
  source: GraphNode,
  target: GraphNode,
  degree: Map<string, number>,
  maxDegree: number,
  options: Required<InsightsOptions>,
): { score: number; reason: string } | null {
  const sourceDeg = degree.get(source.id) ?? 0;
  const targetDeg = degree.get(target.id) ?? 0;
  const minDeg = Math.min(sourceDeg, targetDeg);
  const maxDeg = Math.max(sourceDeg, targetDeg);
  if (minDeg <= options.peripheralMaxDegree && maxDeg >= maxDegree * options.peripheralHubRatio) {
    return { score: 2, reason: 'peripheral-to-hub connection' };
  }
  return null;
}

export function lowWeightSignal(
  edge: GraphEdge,
  _source: GraphNode,
  _target: GraphNode,
  _degree: Map<string, number>,
  _maxDegree: number,
  _options: Required<InsightsOptions>,
): { score: number; reason: string } | null {
  if (edge.weight > 0 && edge.weight < 2) {
    return { score: 1, reason: 'low-weight edge' };
  }
  return null;
}

export const DEFAULT_SURPRISE_SIGNALS: SurpriseSignalFn[] = [
  crossCommunitySignal,
  crossTypeSignal,
  peripheralToHubSignal,
  lowWeightSignal,
];

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
 * Only edges with a total score ≥ threshold are returned, sorted descending.
 *
 * @param nodes       All graph nodes.
 * @param edges       All graph edges.
 * @param communities Community metadata (used for cross-community detection).
 * @param limit       Maximum number of results (default 5).
 * @param options     Optional configuration overrides.
 * @param signals     Optional custom signal functions. When provided, replaces default signals.
 */
export function findSurprisingConnections(
  nodes: GraphNode[],
  edges: GraphEdge[],
  communities: CommunityInfo[],
  limit: number = 5,
  options?: InsightsOptions,
  signals?: SurpriseSignalFn[],
): SurprisingConnection[] {
  if (nodes.length === 0 || edges.length === 0) return [];

  const opts = mergeOptions(options);
  const effectiveLimit = opts.limit && limit === 5 ? opts.limit : limit;

  const nodeMap = new Map<string, GraphNode>();
  for (const n of nodes) nodeMap.set(n.id, n);

  const degree = computeDegree(nodes, edges);
  const maxDegree = degree.size > 0
    ? Math.max(...Array.from(degree.values()))
    : 1;

  const signalFns = signals ?? DEFAULT_SURPRISE_SIGNALS;

  const candidates: SurprisingConnection[] = [];

  for (const edge of edges) {
    const source = nodeMap.get(edge.source);
    const target = nodeMap.get(edge.target);
    if (!source || !target) continue;

    let score = 0;
    const reasons: string[] = [];

    for (const signalFn of signalFns) {
      const result = signalFn(edge, source, target, degree, maxDegree, opts);
      if (result) {
        score += result.score;
        reasons.push(result.reason);
      }
    }

    if (score >= opts.surpriseThreshold) {
      candidates.push({
        source,
        target,
        score,
        reasons,
        key: `${source.id}\u2194${target.id}`,
      });
    }
  }

  candidates.sort((a, b) => b.score - a.score);
  return candidates.slice(0, effectiveLimit);
}

// ---------------------------------------------------------------------------
// Knowledge Gaps
// ---------------------------------------------------------------------------

/**
 * Detect knowledge gaps in the graph.
 *
 * Three gap types are identified:
 * 1. **isolated-node**   — degree ≤ 1, not a structural page.
 * 2. **sparse-community** — cohesion < threshold, ≥ minNodes nodes.
 * 3. **bridge-node**     — connected to minComms+ communities, not structural.
 *
 * @param nodes       All graph nodes.
 * @param edges       All graph edges.
 * @param communities Community metadata.
 * @param limit       Maximum number of gaps to return (default 8).
 * @param options     Optional configuration overrides.
 */
export function detectKnowledgeGaps(
  nodes: GraphNode[],
  edges: GraphEdge[],
  communities: CommunityInfo[],
  limit: number = 8,
  options?: InsightsOptions,
): KnowledgeGap[] {
  const opts = mergeOptions(options);
  const effectiveLimit = opts.limit && limit === 8 ? opts.limit : limit;

  const structuralTypes = new Set([
    ...Array.from(STRUCTURAL_TYPES),
    ...Array.from(opts.structuralTypes || []),
  ]);

  const gaps: KnowledgeGap[] = [];
  const nodeMap = new Map<string, GraphNode>();
  for (const n of nodes) nodeMap.set(n.id, n);

  // Single pass over edges: build degree + communityLinks simultaneously
  const degree = new Map<string, number>();
  const communityLinks = new Map<string, Set<number>>();
  for (const n of nodes) {
    degree.set(n.id, 0);
    communityLinks.set(n.id, new Set<number>());
  }
  for (const edge of edges) {
    degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);

    const source = nodeMap.get(edge.source);
    const target = nodeMap.get(edge.target);
    if (source && target) {
      communityLinks.get(source.id)!.add(target.community);
      communityLinks.get(target.id)!.add(source.community);
    }
  }

  // ---- Type 1: Isolated nodes ----
  for (const node of nodes) {
    if (structuralTypes.has(node.type)) continue;
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
    if (comm.cohesion < opts.sparseCohesionThreshold && comm.nodeCount >= opts.sparseMinNodes) {
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

  // ---- Type 3: Bridge nodes (connected to minComms+ communities) ----
  for (const node of nodes) {
    if (structuralTypes.has(node.type)) continue;
    const connectedComms = communityLinks.get(node.id);
    if (connectedComms && connectedComms.size >= opts.bridgeCommunityMin) {
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

  return gaps.slice(0, effectiveLimit);
}
