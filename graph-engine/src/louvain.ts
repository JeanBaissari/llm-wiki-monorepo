/**
 * graph-engine/src/louvain.ts
 *
 * Louvain community detection using graphology.
 * Wraps graphology-communities-louvain with ergonomic output:
 *  - Community IDs renumbered sequentially (0, 1, 2…) sorted by size
 *  - Cohesion (intra-community edge density) computed per community
 *  - Top 5 nodes (by linkCount) surfaced as labels
 */

import Graph from "graphology";
import louvain from "graphology-communities-louvain";
import type { GraphNode, GraphEdge, CommunityInfo } from "./types.js";

export interface CommunityDetectionResult {
  assignments: Map<string, number>;
  communities: CommunityInfo[];
}

/**
 * Run Louvain community detection on the given nodes and edges.
 *
 * @param nodes  – Graph nodes (must include id, label, linkCount).
 * @param edges  – Weighted edges between nodes.
 * @returns      A map of node → community and a sorted list of community
 *               metadata (cohesion, top nodes).
 */
export function detectCommunities(
  nodes: GraphNode[],
  edges: GraphEdge[],
): CommunityDetectionResult {
  // ── Empty graph guard ────────────────────────────────────────────────
  if (!nodes.length) {
    return { assignments: new Map(), communities: [] };
  }

  // ── Build graphology graph ──────────────────────────────────────────
  const g = new Graph({ type: "undirected" });

  const nodeSet = new Set<string>();
  for (const node of nodes) {
    g.addNode(node.id);
    nodeSet.add(node.id);
  }

  for (const edge of edges) {
    if (!nodeSet.has(edge.source) || !nodeSet.has(edge.target)) continue;
    // graphology-communities-louvain treats edges with the same
    // source+target as parallel; use a compound key to avoid duplicates.
    const key = `${edge.source}→${edge.target}`;
    if (!g.hasEdge(key)) {
      g.addEdgeWithKey(key, edge.source, edge.target, { weight: edge.weight });
    }
  }

  // ── Run Louvain ─────────────────────────────────────────────────────
  // louvain() returns Record<nodeId, communityNumber>
  const rawCommunities = louvain(g, { resolution: 1 });

  // ── Build assignments Map ───────────────────────────────────────────
  const assignments = new Map<string, number>(
    Object.entries(rawCommunities).map(([k, v]) => [k, v as number]),
  );

  // ── Group nodes by community ────────────────────────────────────────
  const communityNodes = new Map<number, GraphNode[]>();
  for (const node of nodes) {
    const cid = assignments.get(node.id);
    if (cid === undefined) continue; // should never happen
    const bucket = communityNodes.get(cid);
    if (bucket) {
      bucket.push(node);
    } else {
      communityNodes.set(cid, [node]);
    }
  }

  // ── Pre-process: map node → community for fast intra-edge checks ────
  const nodeToCommunity = new Map<string, number>();
  for (const [nid, cid] of assignments) {
    nodeToCommunity.set(nid, cid);
  }

  // ── Compute cohesion and top nodes per community ────────────────────
  const communityEntries: Array<{
    oldId: number;
    nodeCount: number;
    cohesion: number;
    topNodes: string[];
  }> = [];

  for (const [cid, members] of communityNodes) {
    const n = members.length;

    // Count intra-community edges
    let intraEdges = 0;
    for (const edge of edges) {
      const srcC = nodeToCommunity.get(edge.source);
      const tgtC = nodeToCommunity.get(edge.target);
      if (srcC === cid && tgtC === cid) {
        intraEdges++;
      }
    }

    // Edge density (cohesion): actual intra-edges / possible edges
    const possibleEdges = n * (n - 1) / 2;
    const cohesion = possibleEdges > 0 ? intraEdges / possibleEdges : 0;

    // Top 5 nodes by linkCount, descending
    const sorted = [...members].sort((a, b) => b.linkCount - a.linkCount);
    const topNodes = sorted.slice(0, 5).map((node) => node.label);

    communityEntries.push({ oldId: cid, nodeCount: n, cohesion, topNodes });
  }

  // ── Sort by nodeCount descending and re-number sequentially ─────────
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

  // ── Remap assignments to new sequential IDs ─────────────────────────
  const remappedAssignments = new Map<string, number>();
  for (const [nodeId, oldCid] of assignments) {
    remappedAssignments.set(nodeId, cidMap.get(oldCid) ?? oldCid);
  }

  return { assignments: remappedAssignments, communities };
}
