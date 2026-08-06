import Graph from "graphology";
import louvain from "graphology-communities-louvain";
import type { GraphNode, GraphEdge, CommunityInfo } from "./types.js";

export interface LouvainOptions {
  _graph?: Graph;
  seed?: number;
  resolution?: number;
}

export interface CommunityDetectionResult {
  assignments: Map<string, number>;
  communities: CommunityInfo[];
}

/**
 * Deterministic PRNG (mulberry32) used to seed graphology's Louvain. Without a
 * seeded rng the library defaults to Math.random, making community IDs in
 * graph-data.json non-deterministic across builds. Seeding it (default 42,
 * matching the Python engine) makes graph builds reproducible (LWM_024).
 */
function seededRng(seed: number): () => number {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function buildGraphologyGraph(nodes: GraphNode[], edges: GraphEdge[]): Graph {
  const g = new Graph({ type: "undirected" });
  const nodeSet = new Set<string>();
  for (const node of nodes) {
    g.addNode(node.id);
    nodeSet.add(node.id);
  }
  for (const edge of edges) {
    if (!nodeSet.has(edge.source) || !nodeSet.has(edge.target)) continue;
    const [u, v] = edge.source < edge.target ? [edge.source, edge.target] : [edge.target, edge.source];
    const key = `${u}→${v}`;
    if (!g.hasEdge(key)) {
      g.addEdgeWithKey(key, u, v, { weight: edge.weight });
    }
  }
  return g;
}

export function detectCommunities(
  nodes: GraphNode[],
  edges: GraphEdge[],
  options?: LouvainOptions,
): CommunityDetectionResult {
  if (!nodes.length) {
    return { assignments: new Map(), communities: [] };
  }

  const g = options?._graph ?? buildGraphologyGraph(nodes, edges);
  const resolution = options?.resolution ?? 1;
  const seed = options?.seed ?? 42;

  // Seed the rng so community IDs are deterministic across builds (LWM_024).
  const rawCommunities = louvain(g, { resolution, rng: seededRng(seed) });

  const assignments = new Map<string, number>(
    Object.entries(rawCommunities).map(([k, v]) => [k, v as number]),
  );

  const communityNodes = new Map<number, GraphNode[]>();
  for (const node of nodes) {
    const cid = assignments.get(node.id);
    if (cid === undefined) continue;
    const bucket = communityNodes.get(cid);
    if (bucket) {
      bucket.push(node);
    } else {
      communityNodes.set(cid, [node]);
    }
  }

  const nodeToCommunity = new Map<string, number>();
  for (const [nid, cid] of assignments) {
    nodeToCommunity.set(nid, cid);
  }

  const communityEntries: Array<{
    oldId: number;
    nodeCount: number;
    cohesion: number;
    topNodes: string[];
  }> = [];

  for (const [cid, members] of communityNodes) {
    const n = members.length;

    let intraEdges = 0;
    for (const edge of edges) {
      const srcC = nodeToCommunity.get(edge.source);
      const tgtC = nodeToCommunity.get(edge.target);
      if (srcC === cid && tgtC === cid) {
        intraEdges++;
      }
    }

    const possibleEdges = n * (n - 1) / 2;
    const cohesion = possibleEdges > 0 ? intraEdges / possibleEdges : 0;

    const sorted = [...members].sort((a, b) => b.linkCount - a.linkCount);
    const topNodes = sorted.slice(0, 5).map((node) => node.label);

    communityEntries.push({ oldId: cid, nodeCount: n, cohesion, topNodes });
  }

  communityEntries.sort((a, b) => b.nodeCount - a.nodeCount);

  const cidMap = new Map<number, number>();
  const communities: CommunityInfo[] = communityEntries.map((entry, idx) => {
    cidMap.set(entry.oldId, idx);
    return {
      id: idx,
      nodeCount: entry.nodeCount,
      cohesion: entry.cohesion,
      topNodes: entry.topNodes,
    };
  });

  const remappedAssignments = new Map<string, number>();
  for (const [nodeId, oldCid] of assignments) {
    remappedAssignments.set(nodeId, cidMap.get(oldCid) ?? oldCid);
  }

  return { assignments: remappedAssignments, communities };
}
