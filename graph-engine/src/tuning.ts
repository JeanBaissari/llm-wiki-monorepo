// Graph Engine — Tuning profile loader (LWM_031 / ADR-0028)
//
// The Python core is the single source of truth for tuning constants. It emits
// the resolved profile via `llm-wiki tuning --json` (to_graph_engine_json());
// this module parses that JSON into the existing RelevanceOptions /
// InsightsOptions / LouvainOptions interfaces — no TS re-derivation, so Python
// and TS can never drift (v0.5.0 invariant #4). A missing/invalid profile falls
// back to the built-in defaults (PRD LWM_031 error table).

import { readFileSync, existsSync } from 'node:fs';
import type { RelevanceOptions } from './relevance.js';
import type { InsightsOptions } from './insights.js';
import type { LouvainOptions } from './louvain.js';

export interface TuningSignalScores {
  crossCommunity?: number;
  crossTypeStrong?: number;
  crossTypeWeak?: number;
  peripheralToHub?: number;
  lowWeight?: number;
}

export interface TuningProfile {
  relevance?: {
    weights?: {
      directLink?: number;
      sourceOverlap?: number;
      commonNeighbor?: number;
      typeAffinity?: number;
    };
    typeAffinityMatrix?: Record<string, Record<string, number>>;
  };
  insights?: {
    surpriseThreshold?: number;
    sparseCohesionThreshold?: number;
    sparseMinNodes?: number;
    bridgeCommunityMin?: number;
    peripheralMaxDegree?: number;
    peripheralHubRatio?: number;
    isolatedMaxDegree?: number;
    signalScores?: TuningSignalScores;
  };
  community?: {
    resolution?: number;
    seed?: number;
  };
  // retrieval / bm25 / claims sections are emitted by Python too; the
  // graph-engine ignores them (they feed Python consumers only).
}

/** Load a tuning profile JSON file. Returns null when absent or invalid (fail-soft). */
export function loadTuningJson(path: string | undefined | null): TuningProfile | null {
  if (!path || !existsSync(path)) return null;
  try {
    return JSON.parse(readFileSync(path, 'utf-8')) as TuningProfile;
  } catch {
    return null;
  }
}

export function toRelevanceOptions(profile: TuningProfile | null): RelevanceOptions {
  const rel = profile?.relevance;
  if (!rel) return {};
  return {
    ...(rel.weights ? { weights: rel.weights } : {}),
    ...(rel.typeAffinityMatrix ? { typeAffinityMatrix: rel.typeAffinityMatrix } : {}),
  };
}

export function toInsightsOptions(profile: TuningProfile | null): InsightsOptions {
  const ins = profile?.insights;
  if (!ins) return {};
  return {
    ...(ins.surpriseThreshold !== undefined ? { surpriseThreshold: ins.surpriseThreshold } : {}),
    ...(ins.sparseCohesionThreshold !== undefined ? { sparseCohesionThreshold: ins.sparseCohesionThreshold } : {}),
    ...(ins.sparseMinNodes !== undefined ? { sparseMinNodes: ins.sparseMinNodes } : {}),
    ...(ins.bridgeCommunityMin !== undefined ? { bridgeCommunityMin: ins.bridgeCommunityMin } : {}),
    ...(ins.peripheralMaxDegree !== undefined ? { peripheralMaxDegree: ins.peripheralMaxDegree } : {}),
    ...(ins.peripheralHubRatio !== undefined ? { peripheralHubRatio: ins.peripheralHubRatio } : {}),
    ...(ins.isolatedMaxDegree !== undefined ? { isolatedMaxDegree: ins.isolatedMaxDegree } : {}),
    ...(ins.signalScores ? { signalScores: ins.signalScores } : {}),
  };
}

export function toLouvainOptions(profile: TuningProfile | null): LouvainOptions {
  const comm = profile?.community;
  if (!comm) return {};
  return {
    ...(comm.resolution !== undefined ? { resolution: comm.resolution } : {}),
    ...(comm.seed !== undefined ? { seed: comm.seed } : {}),
  };
}
