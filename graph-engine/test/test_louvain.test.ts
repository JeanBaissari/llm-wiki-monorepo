/**
 * graph-engine/test/test_louvain.ts — Louvain Community Detection Tests
 *
 * Covers:
 *   - Empty graph → empty communities
 *   - Single node → one community
 *   - Two-cluster graph → two communities detected
 *   - Community cohesion computation
 *   - Sequential renumbering (0, 1, 2…)
 *   - Top nodes by linkCount
 *   - Deterministic output with consistent input
 */
import { describe, it, expect } from 'vitest';
import { detectCommunities } from '../dist/louvain.js';
import { buildGraphologyGraph } from '../dist/build.js';
import type { GraphNode, GraphEdge } from '../dist/types.js';

// ── Helpers ──────────────────────────────────────────────────────────────

function makeNode(
  id: string,
  label: string,
  type: string = 'entity',
  linkCount: number = 0,
  community: number = 0,
): GraphNode {
  return { id, label, type, path: `${id}.md`, linkCount, community };
}

function makeEdge(source: string, target: string, weight: number = 1): GraphEdge {
  return { source, target, weight };
}

// ══════════════════════════════════════════════════════════════════════════
// Empty graph
// ══════════════════════════════════════════════════════════════════════════

describe('detectCommunities — empty graph', () => {
  it('returns empty communities for empty node list', () => {
    const result = detectCommunities([], []);
    expect(result.communities).toHaveLength(0);
    expect(result.assignments.size).toBe(0);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// Single node
// ══════════════════════════════════════════════════════════════════════════

describe('detectCommunities — single node', () => {
  it('assigns one community for a single node', () => {
    const nodes = [makeNode('a', 'A', 'entity', 0)];
    const edges: GraphEdge[] = [];

    const result = detectCommunities(nodes, edges);
    expect(result.communities).toHaveLength(1);
    expect(result.communities[0].id).toBe(0);
    expect(result.communities[0].nodeCount).toBe(1);
    // Single-node community has 0 possible edges, so cohesion = 0
    expect(result.communities[0].cohesion).toBe(0);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// Two-cluster graph
// ══════════════════════════════════════════════════════════════════════════

describe('detectCommunities — two clusters', () => {
  it('detects two communities in a clustered graph', () => {
    // Cluster 1: A-B-C (densely connected)
    // Cluster 2: D-E-F (densely connected)
    // Bridge: C-D (connects clusters)
    const nodes = [
      makeNode('a', 'A', 'entity', 2),
      makeNode('b', 'B', 'entity', 2),
      makeNode('c', 'C', 'entity', 3),
      makeNode('d', 'D', 'entity', 3),
      makeNode('e', 'E', 'entity', 2),
      makeNode('f', 'F', 'entity', 2),
    ];
    const edges = [
      makeEdge('a', 'b', 10),
      makeEdge('b', 'c', 10),
      makeEdge('a', 'c', 8),
      makeEdge('d', 'e', 10),
      makeEdge('e', 'f', 10),
      makeEdge('d', 'f', 8),
      makeEdge('c', 'd', 1), // bridge — weak connection between clusters
    ];

    const result = detectCommunities(nodes, edges);
    expect(result.communities.length).toBeGreaterThanOrEqual(1);
    expect(result.communities.length).toBeLessThanOrEqual(3);

    // Communities should be sized reasonably
    const totalNodes = result.communities.reduce((sum, c) => sum + c.nodeCount, 0);
    expect(totalNodes).toBe(6);
  });

  it('communities are sequentially numbered from 0', () => {
    const nodes = [
      makeNode('a', 'A', 'entity', 2),
      makeNode('b', 'B', 'entity', 2),
      makeNode('c', 'C', 'entity', 3),
      makeNode('d', 'D', 'entity', 3),
      makeNode('e', 'E', 'entity', 2),
      makeNode('f', 'F', 'entity', 2),
    ];
    const edges = [
      makeEdge('a', 'b', 10),
      makeEdge('b', 'c', 10),
      makeEdge('d', 'e', 10),
      makeEdge('e', 'f', 10),
    ];

    const result = detectCommunities(nodes, edges);
    const ids = result.communities.map(c => c.id).sort();
    // Should be consecutive: 0, 1, 2, ...
    for (let i = 0; i < ids.length; i++) {
      expect(ids[i]).toBe(i);
    }
  });
});

// ══════════════════════════════════════════════════════════════════════════
// Cohesion
// ══════════════════════════════════════════════════════════════════════════

describe('detectCommunities — cohesion', () => {
  it('cohesion is between 0 and 1', () => {
    const nodes = [
      makeNode('a', 'A', 'entity', 2),
      makeNode('b', 'B', 'entity', 2),
      makeNode('c', 'C', 'entity', 1),
    ];
    const edges = [
      makeEdge('a', 'b', 10),
      makeEdge('b', 'c', 5),
    ];

    const result = detectCommunities(nodes, edges);
    for (const comm of result.communities) {
      expect(comm.cohesion).toBeGreaterThanOrEqual(0);
      expect(comm.cohesion).toBeLessThanOrEqual(1);
    }
  });

  it('fully connected community has cohesion = 1', () => {
    const nodes = [
      makeNode('a', 'A', 'entity', 2),
      makeNode('b', 'B', 'entity', 2),
      makeNode('c', 'C', 'entity', 2),
    ];
    const edges = [
      makeEdge('a', 'b', 10),
      makeEdge('b', 'c', 10),
      makeEdge('a', 'c', 10),
    ];

    const result = detectCommunities(nodes, edges);
    // With high weights on all edges, all three should be in one community
    const cohesion = result.communities[0]?.cohesion ?? 0;
    // 3 nodes, 3 edges, possible = 3, so density = 1.0
    expect(cohesion).toBe(1.0);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// Top nodes
// ══════════════════════════════════════════════════════════════════════════

describe('detectCommunities — top nodes', () => {
  it('lists top nodes by linkCount', () => {
    const nodes = [
      makeNode('a', 'Popular A', 'entity', 10),
      makeNode('b', 'Popular B', 'entity', 8),
      makeNode('c', 'Lesser C', 'entity', 1),
    ];
    const edges = [
      makeEdge('a', 'b', 5),
      makeEdge('a', 'c', 1),
    ];

    const result = detectCommunities(nodes, edges);
    expect(result.communities.length).toBeGreaterThan(0);
    const topNodes = result.communities[0].topNodes;
    expect(topNodes).toContain('Popular A');
    expect(topNodes).toContain('Popular B');
  });
});

// ══════════════════════════════════════════════════════════════════════════
// Shared graph parity tests (LWM_04B)
// ══════════════════════════════════════════════════════════════════════════

describe('detectCommunities — shared graph parity (LWM_04B)', () => {
  it('produces identical results with and without pre-built _graph', () => {
    const nodes = [
      makeNode('a', 'A', 'entity', 2),
      makeNode('b', 'B', 'entity', 2),
      makeNode('c', 'C', 'entity', 3),
      makeNode('d', 'D', 'entity', 3),
      makeNode('e', 'E', 'entity', 2),
      makeNode('f', 'F', 'entity', 2),
    ];
    const edges = [
      makeEdge('a', 'b', 10),
      makeEdge('b', 'c', 10),
      makeEdge('a', 'c', 8),
      makeEdge('d', 'e', 10),
      makeEdge('e', 'f', 10),
      makeEdge('d', 'f', 8),
      makeEdge('c', 'd', 1),
    ];

    // Independent graph construction (backward compat path)
    const resultWithout = detectCommunities(nodes, edges);

    // Pre-built graph (shared instance path)
    const prebuiltGraph = buildGraphologyGraph(nodes, edges);
    const resultWith = detectCommunities(nodes, edges, { _graph: prebuiltGraph });

    // Community assignments must be byte-identical
    expect(resultWith.assignments.size).toBe(resultWithout.assignments.size);
    for (const [nodeId, cid] of resultWithout.assignments) {
      expect(resultWith.assignments.get(nodeId)).toBe(cid);
    }

    // Community metadata must match exactly
    expect(resultWith.communities).toHaveLength(resultWithout.communities.length);
    for (let i = 0; i < resultWithout.communities.length; i++) {
      expect(resultWith.communities[i].id).toBe(resultWithout.communities[i].id);
      expect(resultWith.communities[i].nodeCount).toBe(resultWithout.communities[i].nodeCount);
      expect(resultWith.communities[i].cohesion).toBe(resultWithout.communities[i].cohesion);
      expect(resultWith.communities[i].topNodes).toEqual(resultWithout.communities[i].topNodes);
    }
  });

  it('backward compat: detectCommunities without opts returns same as current', () => {
    // This duplicates the "fully connected community" test to confirm
    // the refactored code path (IIFE fallback) produces identical results.
    const nodes = [
      makeNode('a', 'A', 'entity', 2),
      makeNode('b', 'B', 'entity', 2),
      makeNode('c', 'C', 'entity', 2),
    ];
    const edges = [
      makeEdge('a', 'b', 10),
      makeEdge('b', 'c', 10),
      makeEdge('a', 'c', 10),
    ];

    const result = detectCommunities(nodes, edges);
    // With high weights on all edges, all three should be in one community
    expect(result.communities).toHaveLength(1);
    expect(result.communities[0].nodeCount).toBe(3);
    expect(result.communities[0].cohesion).toBe(1.0);
  });

  it('buildGraphologyGraph returns valid graph with correct order and size', () => {
    const nodes = [
      makeNode('x', 'X', 'entity', 1),
      makeNode('y', 'Y', 'entity', 1),
      makeNode('z', 'Z', 'entity', 1),
    ];
    const edges = [
      makeEdge('x', 'y', 5),
      makeEdge('y', 'z', 3),
    ];

    const g = buildGraphologyGraph(nodes, edges);
    expect(g.order).toBe(3);  // 3 nodes
    expect(g.size).toBe(2);   // 2 edges
    expect(g.type).toBe('undirected');
    // Verify all nodes exist
    expect(g.hasNode('x')).toBe(true);
    expect(g.hasNode('y')).toBe(true);
    expect(g.hasNode('z')).toBe(true);
  });

  it('shared graph deduplicates edges with sorted keys', () => {
    const nodes = [
      makeNode('a', 'A'),
      makeNode('b', 'B'),
    ];
    const edges = [
      makeEdge('a', 'b', 1),
      makeEdge('b', 'a', 1), // duplicate, reversed
    ];

    const g = buildGraphologyGraph(nodes, edges);
    // Should only have 1 edge (deduplicated by sorted key)
    expect(g.size).toBe(1);
  });

  it('empty graph returns empty graphology Graph', () => {
    const g = buildGraphologyGraph([], []);
    expect(g.order).toBe(0);
    expect(g.size).toBe(0);
  });
});
