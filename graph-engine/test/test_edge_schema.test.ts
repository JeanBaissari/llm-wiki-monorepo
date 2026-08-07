/**
 * graph-engine/test/test_edge_schema.test.ts — LWM_028 edge-schema guard.
 *
 * Proves the additive typed/directed/bitemporal edge schema keeps the undirected
 * default byte-identical (dedup key verbatim) while making directed + typed edges
 * distinct, and that absent optional fields are omitted (never null) from the
 * serialized graph-data.json edge record.
 */
import { describe, it, expect } from 'vitest';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildWikiGraph, edgeDedupKey } from '../src/build.js';
import { detectCommunities } from '../src/louvain.js';
import type { GraphEdge } from '../src/types.js';

const FIXTURES_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), 'fixtures');

describe('edgeDedupKey — undirected default (byte-identical)', () => {
  it('collapses A<->B and B<->A to one sorted key', () => {
    expect(edgeDedupKey('a', 'b')).toBe('a|b');
    expect(edgeDedupKey('b', 'a')).toBe('a|b');
    expect(edgeDedupKey('a', 'b')).toBe(edgeDedupKey('b', 'a'));
  });

  it('is verbatim the pre-v0.5.0 sorted key', () => {
    const legacy = (s: string, t: string) => (s < t ? `${s}|${t}` : `${t}|${s}`);
    for (const [s, t] of [['x', 'y'], ['y', 'x'], ['m', 'm'], ['z1', 'z2']]) {
      expect(edgeDedupKey(s, t)).toBe(legacy(s, t));
    }
  });

  it('directed:false behaves as the undirected default', () => {
    expect(edgeDedupKey('a', 'b', false)).toBe('a|b');
    expect(edgeDedupKey('b', 'a', false)).toBe('a|b');
  });
});

describe('edgeDedupKey — directed opt-in (distinct edges)', () => {
  it('A->B differs from B->A when directed', () => {
    expect(edgeDedupKey('a', 'b', true)).not.toBe(edgeDedupKey('b', 'a', true));
    expect(edgeDedupKey('a', 'b', true)).toBe('a->b#');
  });

  it('relType distinguishes two directed edges with the same endpoints', () => {
    expect(edgeDedupKey('a', 'b', true, 'is-a')).not.toBe(
      edgeDedupKey('a', 'b', true, 'cites'),
    );
  });
});

describe('GraphEdge schema — optional fields', () => {
  it('a legacy {source,target,weight} edge is still type-valid', () => {
    const legacy: GraphEdge = { source: 'a', target: 'b', weight: 1 };
    expect(legacy.relType).toBeUndefined();
    expect(legacy.directed).toBeUndefined();
  });

  it('a typed/directed/bitemporal edge round-trips through JSON, omitting absent fields', () => {
    const typed: GraphEdge = {
      source: 'a',
      target: 'b',
      weight: 1,
      relType: 'cites',
      directed: true,
      validFrom: '2020-01-01T00:00:00Z',
      observedAt: '2026-08-07T00:00:00Z',
    };
    const round = JSON.parse(JSON.stringify(typed)) as GraphEdge;
    expect(round.relType).toBe('cites');
    expect(round.directed).toBe(true);
    // validTo was never set → must be absent (not null) after serialization.
    expect('validTo' in round).toBe(false);
    expect(JSON.stringify({ source: 'a', target: 'b', weight: 1 })).not.toContain('null');
  });
});

describe('golden snapshot — build-through byte-consistency (AD-15)', () => {
  it('a fresh build of the fixture wiki is byte-identical to graph-data.golden.json', async () => {
    const wikiPath = path.join(FIXTURES_DIR, 'wiki');
    const golden = fs.readFileSync(
      path.join(FIXTURES_DIR, 'graph-data.golden.json'),
      'utf-8',
    );
    const fresh = await buildWikiGraph(wikiPath);
    // Same serialization the CLI `--action build` writes to graph-data.json.
    expect(JSON.stringify(fresh, null, 2)).toBe(golden);
  });

  it('buildWikiGraph never emits directed/typed edges — undirected default at build level', async () => {
    const fresh = await buildWikiGraph(path.join(FIXTURES_DIR, 'wiki'));
    expect(fresh.edges.length).toBeGreaterThan(0);
    for (const edge of fresh.edges) {
      expect(edge.relType).toBeUndefined();
      expect(edge.directed).toBeUndefined();
      // Directed semantics live only in the dedup key, which stays private to
      // the build pipeline (the undirected sorted pair).
      expect(edgeDedupKey(edge.source, edge.target)).toBe(
        edge.source < edge.target
          ? `${edge.source}|${edge.target}`
          : `${edge.target}|${edge.source}`,
      );
    }
  });

  it('directed + relType edges flow through the build\'s community stage unchanged', async () => {
    const base = await buildWikiGraph(path.join(FIXTURES_DIR, 'wiki'));
    // Simulate a future directed/typed producer: the same topology where every
    // edge opts into directed + relType. The build's community consumer must
    // accept the full additive schema without crashing or changing partitions.
    const directed: GraphEdge[] = base.edges.map((e) => ({
      ...e,
      directed: true,
      relType: 'cites',
      validFrom: '2020-01-01T00:00:00Z',
      observedAt: '2026-08-07T00:00:00Z',
    }));
    const baseline = detectCommunities(base.nodes, base.edges).communities;
    const withDirected = detectCommunities(base.nodes, directed).communities;
    expect(withDirected).toEqual(baseline);
    // Dedup keys still separate the directed orientations + relTypes.
    for (const e of directed) {
      expect(edgeDedupKey(e.source, e.target, true, 'cites')).toBe(
        `${e.source}->${e.target}#cites`,
      );
    }
    expect(edgeDedupKey('a', 'b', true, 'is-a')).not.toBe(
      edgeDedupKey('a', 'b', true, 'cites'),
    );
    expect(edgeDedupKey('a', 'b', true)).not.toBe(edgeDedupKey('b', 'a', true));
  });
});
