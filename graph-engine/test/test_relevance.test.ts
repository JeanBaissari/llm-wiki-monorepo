/**
 * graph-engine/test/test_relevance.ts — 4-Signal Relevance Model Tests
 *
 * Covers:
 *   - Signal 1: Direct links (forward, backward, bidirectional)
 *   - Signal 2: Source overlap (shared sources)
 *   - Signal 3: Common neighbors / Adamic-Adar (shared neighbors)
 *   - Signal 4: Type affinity (lookup table)
 *   - Zero score for same-node pair
 *   - Zero score for nodes with no relationship
 *   - buildGraphStructure: adjacency, neighbors, degree, empty edges
 *   - getRelatedNodes: top-N ranking
 *
 * LWM_04: Uses precomputed GraphStructure instead of raw edges.
 */
import { describe, it, expect } from 'vitest';
import {
  calculateRelevance,
  buildGraphStructure,
  getRelatedNodes,
} from '../dist/relevance.js';
import type { GraphNode, GraphEdge } from '../dist/types.js';
import type { GraphStructure } from '../dist/relevance.js';

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

function makeEdge(source: string, target: string, weight: number = 0): GraphEdge {
  return { source, target, weight };
}

// ══════════════════════════════════════════════════════════════════════════
// buildGraphStructure
// ══════════════════════════════════════════════════════════════════════════

describe('buildGraphStructure', () => {
  it('builds adjacency, neighbors, and degree from edges', () => {
    const edges: GraphEdge[] = [
      makeEdge('a', 'b'),
      makeEdge('b', 'c'),
      makeEdge('a', 'c'),
    ];
    const structure = buildGraphStructure(edges);

    // Directed adjacency
    expect(structure.adjacency.get('a')?.has('b')).toBe(true);
    expect(structure.adjacency.get('a')?.has('c')).toBe(true);
    expect(structure.adjacency.get('b')?.has('c')).toBe(true);
    // Edge direction not reversed in adjacency
    expect(structure.adjacency.get('b')?.has('a')).toBe(false);

    // Undirected neighbors
    expect(structure.neighbors.get('a')?.has('b')).toBe(true);
    expect(structure.neighbors.get('b')?.has('a')).toBe(true);
    expect(structure.neighbors.get('a')?.size).toBe(2);

    // Degree
    expect(structure.degree.get('a')).toBe(2);
    expect(structure.degree.get('b')).toBe(2);
    expect(structure.degree.get('c')).toBe(2);
  });

  it('handles bidirectional edges correctly', () => {
    const edges: GraphEdge[] = [
      makeEdge('a', 'b'),
      makeEdge('b', 'a'),
    ];
    const structure = buildGraphStructure(edges);

    // Directed adjacency: both directions recorded
    expect(structure.adjacency.get('a')?.has('b')).toBe(true);
    expect(structure.adjacency.get('b')?.has('a')).toBe(true);

    // Undirected neighbors: each sees the other
    expect(structure.neighbors.get('a')?.has('b')).toBe(true);
    expect(structure.neighbors.get('b')?.has('a')).toBe(true);

    // Degree: 2 edges, both are undirected degree contributions
    // a has 2 edges (a→b and b→a), b has 2 edges (a→b and b→a)
    expect(structure.degree.get('a')).toBe(2);
    expect(structure.degree.get('b')).toBe(2);
  });

  it('returns empty maps for empty edge list', () => {
    const structure = buildGraphStructure([]);
    expect(structure.adjacency.size).toBe(0);
    expect(structure.neighbors.size).toBe(0);
    expect(structure.degree.size).toBe(0);
  });

  it('isolated nodes have no adjacency entries', () => {
    const edges: GraphEdge[] = [makeEdge('a', 'b')];
    const structure = buildGraphStructure(edges);
    // 'c' is never referenced in any edge
    expect(structure.adjacency.has('c')).toBe(false);
    expect(structure.neighbors.has('c')).toBe(false);
    expect(structure.degree.has('c')).toBe(false);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// Signal 1: Direct links
// ══════════════════════════════════════════════════════════════════════════

describe('calculateRelevance — Signal 1: Direct links', () => {
  it('returns non-zero score for directly linked nodes', () => {
    const nodeA = makeNode('a', 'A');
    const nodeB = makeNode('b', 'B');
    const nodes = [nodeA, nodeB];
    const edges = [makeEdge('a', 'b')];
    const structure = buildGraphStructure(edges);
    const nodeMap = new Map(nodes.map(n => [n.id, n]));

    const score = calculateRelevance(nodeA, nodeB, nodes, structure, nodeMap);
    expect(score).toBeGreaterThan(0);
    // Direct link weight = 3.0
    expect(score).toBeGreaterThanOrEqual(3.0);
  });

  it('includes both forward and backward links in score', () => {
    const nodeA = makeNode('a', 'A');
    const nodeB = makeNode('b', 'B');
    const nodes = [nodeA, nodeB];
    const edges = [makeEdge('a', 'b'), makeEdge('b', 'a')];
    const structure = buildGraphStructure(edges);
    const nodeMap = new Map(nodes.map(n => [n.id, n]));

    const score = calculateRelevance(nodeA, nodeB, nodes, structure, nodeMap);
    // Bidirectional = 2 * 3.0 = 6.0 (plus type affinity)
    expect(score).toBeGreaterThanOrEqual(6.0);
  });

  it('returns zero for same-node pair', () => {
    const nodeA = makeNode('a', 'A');
    const nodes = [nodeA];
    const edges: GraphEdge[] = [];
    const structure = buildGraphStructure(edges);
    const nodeMap = new Map(nodes.map(n => [n.id, n]));

    const score = calculateRelevance(nodeA, nodeA, nodes, structure, nodeMap);
    expect(score).toBe(0);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// Signal 2: Source overlap
// ══════════════════════════════════════════════════════════════════════════

describe('calculateRelevance — Signal 2: Source overlap', () => {
  it('adds score for shared sources', () => {
    const nodeA = makeNode('a', 'A');
    const nodeB = makeNode('b', 'B');
    const nodes = [nodeA, nodeB];
    const edges = [makeEdge('a', 'b')];
    const structure = buildGraphStructure(edges);
    const nodeMap = new Map<string, GraphNode & { sources?: string[] }>();
    nodeMap.set('a', { ...nodeA, sources: ['src1', 'src2'] });
    nodeMap.set('b', { ...nodeB, sources: ['src1', 'src3'] });

    const score = calculateRelevance(nodeA, nodeB, nodes, structure, nodeMap);
    // Direct link (3.0) + shared source (1 * 4.0) + type affinity (~1.0) = ~8.0
    expect(score).toBeGreaterThanOrEqual(7.0);
  });

  it('no source overlap = no extra score', () => {
    const nodeA = makeNode('a', 'A');
    const nodeB = makeNode('b', 'B');
    const nodes = [nodeA, nodeB];
    const edges = [makeEdge('a', 'b')];
    const structure = buildGraphStructure(edges);
    const nodeMap = new Map<string, GraphNode & { sources?: string[] }>();
    nodeMap.set('a', { ...nodeA, sources: ['src1'] });
    nodeMap.set('b', { ...nodeB, sources: ['src2'] });

    const score = calculateRelevance(nodeA, nodeB, nodes, structure, nodeMap);
    // Direct link (3.0) + 0 source overlap + type affinity
    expect(score).toBeLessThan(5.0);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// Signal 3: Common neighbors / Adamic-Adar
// ══════════════════════════════════════════════════════════════════════════

describe('calculateRelevance — Signal 3: Common neighbors', () => {
  it('adds score for shared neighbors', () => {
    const nodeA = makeNode('a', 'A', 'entity', 2);
    const nodeB = makeNode('b', 'B', 'entity', 2);
    const nodeC = makeNode('c', 'C', 'entity', 2);
    const nodes = [nodeA, nodeB, nodeC];
    const edges = [
      makeEdge('a', 'c'), // A connects to C
      makeEdge('b', 'c'), // B connects to C
      makeEdge('a', 'b'), // A connects to B directly
    ];
    const structure = buildGraphStructure(edges);
    const nodeMap = new Map(nodes.map(n => [n.id, n]));

    const score = calculateRelevance(nodeA, nodeB, nodes, structure, nodeMap);
    // Direct link (3.0) + Adamic-Adar (1/log(2) * 1.5 ≈ 2.16) + type affinity
    expect(score).toBeGreaterThan(5.0);
  });

  it('no common neighbors = zero from this signal', () => {
    const nodeA = makeNode('a', 'A', 'entity', 1);
    const nodeB = makeNode('b', 'B', 'entity', 1);
    const nodes = [nodeA, nodeB];
    const edges = [makeEdge('a', 'b')];
    const structure = buildGraphStructure(edges);
    const nodeMap = new Map(nodes.map(n => [n.id, n]));

    const score = calculateRelevance(nodeA, nodeB, nodes, structure, nodeMap);
    // Direct link (3.0) + 0 Adamic-Adar + type affinity (0.8 * 1.0)
    expect(score).toBeLessThan(4.5);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// Signal 4: Type affinity
// ══════════════════════════════════════════════════════════════════════════

describe('calculateRelevance — Signal 4: Type affinity', () => {
  it('entity-concept pair gets boosted affinity', () => {
    const nodeA = makeNode('a', 'A', 'entity');
    const nodeB = makeNode('b', 'B', 'concept');
    const nodes = [nodeA, nodeB];
    const edges = [makeEdge('a', 'b')];
    const structure = buildGraphStructure(edges);
    const nodeMap = new Map(nodes.map(n => [n.id, n]));

    const score = calculateRelevance(nodeA, nodeB, nodes, structure, nodeMap);
    // Direct link (3.0) + type affinity (1.2 * 1.0 = 1.2) = 4.2
    expect(score).toBeGreaterThanOrEqual(4.0);
  });

  it('same-type nodes get lower affinity', () => {
    const nodeA = makeNode('a', 'A', 'entity');
    const nodeB = makeNode('b', 'B', 'entity');
    const nodes = [nodeA, nodeB];
    const edges = [makeEdge('a', 'b')];
    const structure = buildGraphStructure(edges);
    const nodeMap = new Map(nodes.map(n => [n.id, n]));

    const score = calculateRelevance(nodeA, nodeB, nodes, structure, nodeMap);
    // Direct link (3.0) + type affinity (0.8 * 1.0) = 3.8
    expect(score).toBeGreaterThanOrEqual(3.5);
  });

  it('source-source pair gets minimum affinity', () => {
    const nodeA = makeNode('a', 'A', 'source');
    const nodeB = makeNode('b', 'B', 'source');
    const nodes = [nodeA, nodeB];
    const edges = [makeEdge('a', 'b')];
    const structure = buildGraphStructure(edges);
    const nodeMap = new Map(nodes.map(n => [n.id, n]));

    const score = calculateRelevance(nodeA, nodeB, nodes, structure, nodeMap);
    // Direct link (3.0) + type affinity (0.5 * 1.0) = 3.5
    expect(score).toBeGreaterThanOrEqual(3.0);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// getRelatedNodes: top-N ranking
// ══════════════════════════════════════════════════════════════════════════

describe('getRelatedNodes', () => {
  it('returns top-N related nodes sorted by score', () => {
    const nodeA = makeNode('a', 'A', 'entity', 0, 0);
    const nodeB = makeNode('b', 'B', 'concept', 0, 0);
    const nodeC = makeNode('c', 'C', 'entity', 0, 0);
    const nodes = [nodeA, nodeB, nodeC];
    const edges = [
      makeEdge('a', 'b'), // Direct link to B
      makeEdge('a', 'c'), // Direct link to C
    ];
    const structure = buildGraphStructure(edges);
    const related = getRelatedNodes('a', nodes, structure, 2);
    expect(related).toHaveLength(2);
    expect(related[0].score).toBeGreaterThanOrEqual(related[1].score);
  });

  it('returns empty array for unknown node', () => {
    const nodes = [makeNode('a', 'A')];
    const edges: GraphEdge[] = [];
    const structure = buildGraphStructure(edges);
    const related = getRelatedNodes('unknown', nodes, structure);
    expect(related).toHaveLength(0);
  });
});
