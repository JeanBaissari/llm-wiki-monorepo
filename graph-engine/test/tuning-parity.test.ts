// LWM_031 / ADR-0028 — TS↔Python tuning parity + no-break defaults guard.
//
// 1. Parity: the Python core emits a NON-default profile via the `llm-wiki
//    tuning` surface (to_graph_engine_json()); the TS loader must resolve the
//    exact same option values — no TS re-derivation.
// 2. No-break: a DEFAULT profile resolved through the same loader must produce
//    byte-identical graph-engine output to no options at all (run through the
//    golden fixture wiki).
// 3. Effectiveness: a non-default profile actually changes built edge weights.

import { describe, it, expect } from 'vitest';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadTuningJson, toRelevanceOptions, toInsightsOptions, toLouvainOptions } from '../src/tuning.js';
import { buildWikiGraph } from '../src/build.js';
import { findSurprisingConnections, detectKnowledgeGaps } from '../src/insights.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, '..', '..');
const FIXTURES_DIR = join(__dirname, 'fixtures');
const WIKI_PATH = join(FIXTURES_DIR, 'wiki');

/** Spawn the Python emit surface (`llm-wiki tuning <root> --json`). */
function emitProfile(overrides: string[], env: Record<string, string> = {}): unknown {
  const tmp = mkdtempSync(join(tmpdir(), 'tuning-parity-'));
  const out = execFileSync(
    'python3',
    ['-m', 'llm_wiki.core.tuning', tmp, '--json', ...overrides.map((o) => `--set=${o}`)],
    {
      cwd: REPO_ROOT,
      env: { ...process.env, PYTHONPATH: join(REPO_ROOT, 'src'), ...env },
      encoding: 'utf-8',
    },
  );
  return JSON.parse(out);
}

describe('tuning parity — Python emits, TS consumes (LWM_031 AC#5)', () => {
  it('a non-default profile resolves to identical options on the TS side', async () => {
    const overrides = [
      'relevance.directLink=5.5',
      'relevance.sourceOverlap=2.0',
      'relevance.commonNeighbor=0.75',
      'relevance.typeAffinity=1.25',
      'relevance.typeAffinityMatrix.entity.concept=2.5',
      'relevance.typeAffinityMatrix.query.query=0.2',
      'insights.surpriseThreshold=7',
      'insights.sparseCohesionThreshold=0.05',
      'insights.sparseMinNodes=5',
      'insights.bridgeCommunityMin=2',
      'insights.peripheralMaxDegree=3',
      'insights.peripheralHubRatio=0.4',
      'insights.isolatedMaxDegree=2',
      'insights.signalScores.crossCommunity=4',
      'insights.signalScores.crossTypeStrong=3',
      'insights.signalScores.crossTypeWeak=2',
      'insights.signalScores.peripheralToHub=3',
      'insights.signalScores.lowWeight=2',
      'community.resolution=1.5',
      'community.seed=7',
    ];
    const profile = emitProfile(overrides) as {
      relevance: { weights: Record<string, number>; typeAffinityMatrix: Record<string, Record<string, number>> };
      insights: { [k: string]: unknown; signalScores: Record<string, number> };
      community: { resolution: number; seed: number };
    };

    // Write the profile to disk exactly as `llm-wiki tuning --emit` would.
    const profilePath = join(mkdtempSync(join(tmpdir(), 'tuning-parity-')), 'tuning.json');
    writeFileSync(profilePath, JSON.stringify(profile));

    const loaded = loadTuningJson(profilePath);
    expect(loaded).not.toBeNull();

    const rel = toRelevanceOptions(loaded);
    expect(rel.weights).toEqual(profile.relevance.weights);
    expect(rel.typeAffinityMatrix).toEqual(profile.relevance.typeAffinityMatrix);

    const ins = toInsightsOptions(loaded);
    for (const k of ['surpriseThreshold', 'sparseCohesionThreshold', 'sparseMinNodes',
      'bridgeCommunityMin', 'peripheralMaxDegree', 'peripheralHubRatio', 'isolatedMaxDegree'] as const) {
      expect(ins[k as keyof typeof ins]).toEqual(profile.insights[k]);
    }
    expect(ins.signalScores).toEqual(profile.insights.signalScores);

    const comm = toLouvainOptions(loaded);
    expect(comm.resolution).toEqual(profile.community.resolution);
    expect(comm.seed).toEqual(profile.community.seed);
  });

  it('env overrides flow through the same emit surface', async () => {
    const profile = emitProfile([], {
      LLM_WIKI_TUNE__retrieval__simFloor: '0.45',
      LLM_WIKI_TUNE__bm25__k1: '2.0',
      LLM_WIKI_TUNE__claims__penaltyStale: '4',
    }) as { retrieval: { simFloor: number }; bm25: { k1: number }; claims: { penaltyStale: number } };
    expect(profile.retrieval.simFloor).toBe(0.45);
    expect(profile.bm25.k1).toBe(2.0);
    expect(profile.claims.penaltyStale).toBe(4);
  });
});

describe('no-break guard — resolved defaults == no options (LWM_031 AC#1)', () => {
  it('a default profile produces byte-identical build output to no options', async () => {
    const profile = emitProfile([]);
    const profilePath = join(mkdtempSync(join(tmpdir(), 'tuning-parity-')), 'tuning.json');
    writeFileSync(profilePath, JSON.stringify(profile));

    const loaded = loadTuningJson(profilePath);
    const withDefaults = await buildWikiGraph(WIKI_PATH, {
      relevance: toRelevanceOptions(loaded),
      louvain: toLouvainOptions(loaded),
    });
    const without = await buildWikiGraph(WIKI_PATH);
    expect(JSON.stringify(withDefaults, null, 2)).toBe(JSON.stringify(without, null, 2));
  });

  it('default insights options == no options (signals + gaps byte-identical)', async () => {
    const profile = emitProfile([]);
    const loaded = loadTuningJson(profilePathFor(profile));
    const opts = toInsightsOptions(loaded);
    const graph = await buildWikiGraph(WIKI_PATH);
    expect(
      JSON.stringify(findSurprisingConnections(graph.nodes, graph.edges, graph.communities, 5, opts)),
    ).toBe(
      JSON.stringify(findSurprisingConnections(graph.nodes, graph.edges, graph.communities, 5)),
    );
    expect(
      JSON.stringify(detectKnowledgeGaps(graph.nodes, graph.edges, graph.communities, 8, opts)),
    ).toBe(
      JSON.stringify(detectKnowledgeGaps(graph.nodes, graph.edges, graph.communities, 8)),
    );
  });
});

function profilePathFor(profile: unknown): string {
  const p = join(mkdtempSync(join(tmpdir(), 'tuning-parity-')), 'tuning.json');
  writeFileSync(p, JSON.stringify(profile));
  return p;
}

describe('effectiveness — a tuned profile changes graph-engine output', () => {
  it('a non-default relevance profile changes built edge weights', async () => {
    const profile = emitProfile(['relevance.directLink=9.0']);
    const loaded = loadTuningJson(profilePathFor(profile));
    const tuned = await buildWikiGraph(WIKI_PATH, { relevance: toRelevanceOptions(loaded) });
    const base = await buildWikiGraph(WIKI_PATH);
    expect(JSON.stringify(tuned.edges)).not.toBe(JSON.stringify(base.edges));
  });

  it('a non-default insight threshold filters surprising connections', async () => {
    const profile = emitProfile(['insights.surpriseThreshold=999']);
    const loaded = loadTuningJson(profilePathFor(profile));
    const graph = await buildWikiGraph(WIKI_PATH);
    const base = findSurprisingConnections(graph.nodes, graph.edges, graph.communities);
    const filtered = findSurprisingConnections(graph.nodes, graph.edges, graph.communities, 5, toInsightsOptions(loaded));
    expect(base.length).toBeGreaterThanOrEqual(filtered.length);
    expect(filtered.length).toBe(0);
  });
});
