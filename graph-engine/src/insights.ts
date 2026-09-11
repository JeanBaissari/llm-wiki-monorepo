// Graph Engine — insights: surprising connections + knowledge gaps.
//
// Clean-room, original MIT implementation (2026-09). Independently written
// against the behavioral contract in graph-engine/test/test_insights.test.ts
// and graph-engine/test/tuning-parity.test.ts (public API + defaults parity).
// No third-party source code was reproduced.

import type {
  GraphNode,
  GraphEdge,
  CommunityInfo,
  SurprisingConnection,
  KnowledgeGap,
} from './types.js';

export interface InsightsSignalScores {
  crossCommunity: number;
  crossTypeStrong: number;
  crossTypeWeak: number;
  peripheralToHub: number;
  lowWeight: number;
}

export interface InsightsOptions {
  surpriseThreshold?: number;
  sparseCohesionThreshold?: number;
  sparseMinNodes?: number;
  bridgeCommunityMin?: number;
  peripheralMaxDegree?: number;
  peripheralHubRatio?: number;
  isolatedMaxDegree?: number;
  structuralTypes?: string[];
  limit?: number;
  signalScores?: Partial<InsightsSignalScores>;
}

/** Fully-resolved options after merging defaults (what the signal functions see). */
export interface MergedInsightsOptions extends Omit<Required<InsightsOptions>, 'signalScores'> {
  signalScores: InsightsSignalScores;
}

export const DEFAULT_INSIGHTS_OPTIONS: MergedInsightsOptions = {
  surpriseThreshold: 3,
  sparseCohesionThreshold: 0.15,
  sparseMinNodes: 3,
  bridgeCommunityMin: 3,
  peripheralMaxDegree: 2,
  peripheralHubRatio: 0.5,
  isolatedMaxDegree: 1,
  structuralTypes: [],
  limit: 8,
  signalScores: {
    crossCommunity: 3,
    crossTypeStrong: 2,
    crossTypeWeak: 1,
    peripheralToHub: 2,
    lowWeight: 1,
  },
};

/** Page types excluded from content-gap detection regardless of caller options. */
const BUILTIN_STRUCTURAL_TYPES = ['index', 'log', 'overview'] as const;

/** Type pair whose cross-type link is treated as "distant" (stronger signal). */
const DISTANT_TYPE_PAIR = 'concept-source';

function resolveOptions(overrides?: InsightsOptions): MergedInsightsOptions {
  if (!overrides) return DEFAULT_INSIGHTS_OPTIONS;
  return {
    ...DEFAULT_INSIGHTS_OPTIONS,
    ...overrides,
    structuralTypes: overrides.structuralTypes ?? DEFAULT_INSIGHTS_OPTIONS.structuralTypes,
    signalScores: { ...DEFAULT_INSIGHTS_OPTIONS.signalScores, ...overrides.signalScores },
  };
}

export type SurpriseSignalFn = (
  edge: GraphEdge,
  source: GraphNode,
  target: GraphNode,
  degree: Map<string, number>,
  maxDegree: number,
  options: MergedInsightsOptions,
) => { score: number; reason: string } | null;

export function crossCommunitySignal(
  _edge: GraphEdge,
  source: GraphNode,
  target: GraphNode,
  _degree: Map<string, number>,
  _maxDegree: number,
  options: MergedInsightsOptions,
): { score: number; reason: string } | null {
  if (source.community === target.community) return null;
  return { score: options.signalScores.crossCommunity, reason: 'cross-community edge' };
}

export function crossTypeSignal(
  _edge: GraphEdge,
  source: GraphNode,
  target: GraphNode,
  _degree: Map<string, number>,
  _maxDegree: number,
  options: MergedInsightsOptions,
): { score: number; reason: string } | null {
  if (source.type === target.type) return null;

  const pair = [source.type.toLowerCase(), target.type.toLowerCase()].sort().join('-');
  if (pair === DISTANT_TYPE_PAIR) {
    return { score: options.signalScores.crossTypeStrong, reason: 'cross-type edge (distant pair)' };
  }
  return { score: options.signalScores.crossTypeWeak, reason: 'cross-type edge' };
}

export function peripheralToHubSignal(
  _edge: GraphEdge,
  source: GraphNode,
  target: GraphNode,
  degree: Map<string, number>,
  maxDegree: number,
  options: MergedInsightsOptions,
): { score: number; reason: string } | null {
  const sourceDegree = degree.get(source.id) ?? 0;
  const targetDegree = degree.get(target.id) ?? 0;
  const lower = Math.min(sourceDegree, targetDegree);
  const upper = Math.max(sourceDegree, targetDegree);

  if (lower <= options.peripheralMaxDegree && upper >= maxDegree * options.peripheralHubRatio) {
    return { score: options.signalScores.peripheralToHub, reason: 'peripheral-to-hub connection' };
  }
  return null;
}

export function lowWeightSignal(
  edge: GraphEdge,
  _source: GraphNode,
  _target: GraphNode,
  _degree: Map<string, number>,
  _maxDegree: number,
  options: MergedInsightsOptions,
): { score: number; reason: string } | null {
  if (edge.weight > 0 && edge.weight < 2) {
    return { score: options.signalScores.lowWeight, reason: 'low-weight edge' };
  }
  return null;
}

export const DEFAULT_SURPRISE_SIGNALS: SurpriseSignalFn[] = [
  crossCommunitySignal,
  crossTypeSignal,
  peripheralToHubSignal,
  lowWeightSignal,
];

function countDegrees(nodes: GraphNode[], edges: GraphEdge[]): Map<string, number> {
  const degree = new Map<string, number>();
  for (const node of nodes) degree.set(node.id, 0);
  for (const edge of edges) {
    degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
  }
  return degree;
}

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

  const config = resolveOptions(options);
  const effectiveLimit = config.limit && limit === 5 ? config.limit : limit;

  const byId = new Map<string, GraphNode>();
  for (const node of nodes) byId.set(node.id, node);

  const degree = countDegrees(nodes, edges);
  const degreeValues = [...degree.values()];
  const maxDegree = degreeValues.length > 0 ? Math.max(...degreeValues) : 1;

  const activeSignals = signals ?? DEFAULT_SURPRISE_SIGNALS;
  const found: SurprisingConnection[] = [];

  for (const edge of edges) {
    const source = byId.get(edge.source);
    const target = byId.get(edge.target);
    if (!source || !target) continue;

    let score = 0;
    const reasons: string[] = [];
    for (const signal of activeSignals) {
      const verdict = signal(edge, source, target, degree, maxDegree, config);
      if (verdict) {
        score += verdict.score;
        reasons.push(verdict.reason);
      }
    }

    if (score >= config.surpriseThreshold) {
      found.push({
        source,
        target,
        score,
        reasons,
        key: `${source.id}\u2194${target.id}`,
      });
    }
  }

  found.sort((left, right) => right.score - left.score);
  return found.slice(0, effectiveLimit);
}

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
  const config = resolveOptions(options);
  const effectiveLimit = config.limit && limit === 8 ? config.limit : limit;

  const structuralTypes = new Set<string>();
  for (const type of BUILTIN_STRUCTURAL_TYPES) structuralTypes.add(type);
  for (const type of config.structuralTypes) structuralTypes.add(type);

  const byId = new Map<string, GraphNode>();
  const degree = new Map<string, number>();
  const linkedCommunities = new Map<string, Set<number>>();
  for (const node of nodes) {
    byId.set(node.id, node);
    degree.set(node.id, 0);
    linkedCommunities.set(node.id, new Set());
  }

  for (const edge of edges) {
    degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);

    const source = byId.get(edge.source);
    const target = byId.get(edge.target);
    if (!source || !target) continue;
    linkedCommunities.get(source.id)!.add(target.community);
    linkedCommunities.get(target.id)!.add(source.community);
  }

  const gaps: KnowledgeGap[] = [];

  for (const node of nodes) {
    if (structuralTypes.has(node.type)) continue;
    const connections = degree.get(node.id) ?? 0;
    if (connections <= config.isolatedMaxDegree) {
      gaps.push({
        type: 'isolated-node',
        title: `Isolated Node: "${node.label}"`,
        description: `Node "${node.label}" (${node.id}) has only ${connections} connection${
          connections === 1 ? '' : 's'
        } and may be disconnected from the rest of the graph.`,
        nodeIds: [node.id],
        suggestion: `Consider adding more wikilinks to/from "${node.label}" to integrate it better with related topics.`,
      });
    }
  }

  for (const community of communities) {
    if (
      community.cohesion < config.sparseCohesionThreshold &&
      community.nodeCount >= config.sparseMinNodes
    ) {
      gaps.push({
        type: 'sparse-community',
        title: `Sparse Community #${community.id}`,
        description: `Community #${community.id} has low cohesion (${community.cohesion.toFixed(
          3,
        )}) with ${community.nodeCount} nodes, suggesting weak internal connectivity.`,
        nodeIds: community.topNodes.slice(),
        suggestion: `Add more cross-links among members of community #${community.id} to strengthen internal connections.`,
      });
    }
  }

  for (const node of nodes) {
    if (structuralTypes.has(node.type)) continue;
    const bridged = linkedCommunities.get(node.id);
    if (bridged && bridged.size >= config.bridgeCommunityMin) {
      gaps.push({
        type: 'bridge-node',
        title: `Bridge Node: "${node.label}"`,
        description: `Node "${node.label}" connects ${bridged.size} different communities, acting as a bridge across knowledge domains.`,
        nodeIds: [node.id],
        suggestion: `Ensure "${node.label}" has sufficient content depth to properly bridge these communities.`,
      });
    }
  }

  const priorityByType: Record<string, number> = {
    'isolated-node': 0,
    'sparse-community': 1,
    'bridge-node': 2,
  };
  gaps.sort((left, right) => (priorityByType[left.type] ?? 99) - (priorityByType[right.type] ?? 99));

  return gaps.slice(0, effectiveLimit);
}
