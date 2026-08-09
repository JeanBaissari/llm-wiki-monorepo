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

## Delivered State (defe7e0 + B9)

`core/config.py` defines all **22 constants + the 5×5 type-affinity matrix + 5 insights signal scores + validators + the CLI/env/file precedence** (fail-closed, exit 2). Since remediation batch **B9**, **all constants are effective**: relevance weights + matrix flow to the graph-engine via `llm-wiki tuning --json` → `--tuning-json` (consumed through `RelevanceOptions`/`LouvainOptions`), insights thresholds + signal scores flow into `llm-wiki insights` (Python) and `InsightsOptions` (TS), `community.resolution/seed` into both Louvain engines, `bm25.k1/b` into the Python keyword path (Python BM25 rescoring on override), and `claims.penalty*`/`failBelow` into `llm-wiki claims redteam`. `to_graph_engine_json()` is live (emitted by `llm-wiki tuning`). Defaults remain byte-identical, pinned by `tests/eval/baseline/tuning_defaults.json` + `graph-engine/test/tuning-parity.test.ts`.

## Consequences

**Easier:** every precision-steering constant is named, validated, documented, and tunable without editing source; the Python/TS drift channel closes; re-tuning becomes an eval-driven exercise rather than a source edit. **Harder:** fail-closed validation means a typo'd key aborts with exit 2 (deliberate); until B9 lands, most constants are defined-but-inert — the config surface is ahead of its consumers.
