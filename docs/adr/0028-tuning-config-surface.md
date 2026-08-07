# ADR 0028: Tuning Constants as Config — Canonical TuningConfig Surface

- **Status:** accepted
- **Date:** 2026-08-07
- **Context:** LWM_031 (v0.5.0) — ~22 magic constants scattered across the relevance model, insights signals, community detection, hybrid retrieval, BM25, and claim health each silently steer precision, but none is justified, discoverable, or tunable. Two surfaces (`relevance.ts`, `insights.ts`) already accepted override objects but had no config surface behind them, and the Python/TS copies could drift. v0.4.0's eval harness (LWM_022 / ADR-0022) built the missing piece — this PRD closes the loop by making every constant a named, validated, documented config input **without changing a single default**.

## Decision

**One canonical `TuningConfig` in the Python core — the single source of truth** (`src/llm_wiki/core/config.py`):

- **Inventory — 22 constants in 6 sections** (defaults == today's source literals byte-for-byte):

  | Section | Constants (defaults) |
  |---------|----------------------|
  | `relevance` (4) | `directLink` 3.0, `sourceOverlap` 4.0, `commonNeighbor` 1.5, `typeAffinity` 1.0 |
  | `insights` (7) | `surpriseThreshold` 3, `sparseCohesionThreshold` 0.15, `sparseMinNodes` 3, `bridgeCommunityMin` 3, `peripheralMaxDegree` 2, `peripheralHubRatio` 0.5, `isolatedMaxDegree` 1 |
  | `community` (2) | `resolution` 1.0, `seed` 42 |
  | `retrieval` (2) | `rrfK` 60, `simFloor` 0.30 |
  | `bm25` (2) | `k1` 1.5, `b` 0.75 |
  | `claims` (5) | `penaltyStale` 2, `penaltyOpen` 10, `penaltyLowConf` 5, `penaltyContested` 3, `failBelow` 70 |

  The full inventory also includes the **5×5 type-affinity matrix** and the **insights per-signal scores** (`+3/+2/+1`).
- **Precedence: CLI > env > file > code-default.** CLI: repeatable `--set section.key=value`; env: `LLM_WIKI_TUNE__<section>__<key>`; file: `tuning.toml` at the wiki root (TOML). With no overrides present, resolution equals the code defaults byte-for-byte.
- **Fail-closed validation:** unknown keys and out-of-range values raise `ConfigError` → **CLI exit 2**; keys are type-coerced by declared field type (int fields parse as int, float as float) and validated per-key (e.g. `_unit` for ratios, `_posint` for positive ints).
- **§Eval-tuned-defaults:** a shipped default may only move with an attached eval report — re-tuned on the LWM_022 **TUNE** split (never the GATE split), per-constant annotated with the gate metric it moves.
- **Python canonical, TS consumes:** the graph-engine consumes the resolved tuning through its existing `RelevanceOptions` / `InsightsOptions` / `LouvainOptions` interfaces via `to_graph_engine_json()` — one source of truth, no TS re-derivation (v0.5.0 invariant #4).

## Delivered State (defe7e0)

`core/config.py` defines all **22 constants + validators + the CLI/env/file precedence** (fail-closed, exit 2). **Today only 2 constants are effective**: `retrieval.rrfK` and `retrieval.simFloor`, threaded through `llm-wiki search` (`--set`, `resolve_tuning`). **Remediation batch B9 threads the remaining 20 constants** (relevance weights, insights thresholds, community resolution/seed, BM25 k1/b, claims penalties) into their consumers, adds the type-affinity matrix + insights signal scores, and makes `to_graph_engine_json()` live for graph-engine consumption.

## Consequences

**Easier:** every precision-steering constant is named, validated, documented, and tunable without editing source; the Python/TS drift channel closes; re-tuning becomes an eval-driven exercise rather than a source edit. **Harder:** fail-closed validation means a typo'd key aborts with exit 2 (deliberate); until B9 lands, most constants are defined-but-inert — the config surface is ahead of its consumers.
