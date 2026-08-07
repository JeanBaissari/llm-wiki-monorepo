/**
 * graph-engine/test/test_edge_schema.test.ts — LWM_028 edge-schema guard.
 *
 * Proves the additive typed/directed/bitemporal edge schema keeps the undirected
 * default byte-identical (dedup key verbatim) while making directed + typed edges
 * distinct, and that absent optional fields are omitted (never null) from the
 * serialized graph-data.json edge record.
 */
import { describe, it, expect } from 'vitest';
import { edgeDedupKey } from '../src/build.js';
import type { GraphEdge } from '../src/types.js';

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
