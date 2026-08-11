# Tuning Configuration Reference (LWM_031 / ADR-0028)

> Every precision-steering constant in the system lives in **one canonical
> surface**: `src/llm_wiki/core/config.py` — the Python `TuningConfig`. Defaults
> equal today's source literals **byte-for-byte**, so nothing changes until a
> constant is measured and re-tuned on the LWM_022 **TUNE** split. The TypeScript
> graph-engine consumes the *same* resolved profile through
> `--tuning-json` — no TS re-derivation, so Python and TS can never drift
> (v0.5.0 invariant #4).

## The config surface

Six sections, **22 scalar constants + the 5×5 type-affinity matrix + 5 insights
signal scores** (52 settable keys in total):

| Section | Keys (defaults) | Gate metric tuned against |
|---|---|---|
| `relevance` (4) | `directLink` 3.0, `sourceOverlap` 4.0, `commonNeighbor` 1.5, `typeAffinity` 1.0 | link precision@k (LWM_022 retrieval/link eval) |
| `relevance.typeAffinityMatrix` (5×5) | `entity/concept/source/query/synthesis` × same; see matrix below | link precision@k |
| `insights` (7) | `surpriseThreshold` 3, `sparseCohesionThreshold` 0.15, `sparseMinNodes` 3, `bridgeCommunityMin` 3, `peripheralMaxDegree` 2, `peripheralHubRatio` 0.5, `isolatedMaxDegree` 1 | insights signal quality (curated review) + gap precision |
| `insights.signalScores` (5) | `crossCommunity` 3, `crossTypeStrong` 2, `crossTypeWeak` 1, `peripheralToHub` 2, `lowWeight` 1 | insights signal quality |
| `community` (2) | `resolution` 1.0, `seed` 42 | community NMI/modularity vs wikilink baseline |
| `retrieval` (2) | `rrfK` 60, `simFloor` 0.30 | retrieval precision@k / recall; gibberish→empty |
| `bm25` (2) | `k1` 1.5, `b` 0.75 | keyword retrieval precision@k / recall |
| `claims` (5) | `penaltyStale` 2, `penaltyOpen` 10, `penaltyLowConf` 5, `penaltyContested` 3, `failBelow` 70 | claim-health exit-code stability |

### Type-affinity matrix (defaults — mirrors `graph-engine/src/relevance.ts`)

```toml
[relevance.typeAffinityMatrix.entity]
concept = 1.2; entity = 0.8; source = 1.0; synthesis = 1.0; query = 0.8
[relevance.typeAffinityMatrix.concept]
entity = 1.2; concept = 0.8; source = 1.0; synthesis = 1.2; query = 1.0
[relevance.typeAffinityMatrix.source]
entity = 1.0; concept = 1.0; source = 0.5; query = 0.8; synthesis = 1.0
[relevance.typeAffinityMatrix.query]
concept = 1.0; entity = 0.8; synthesis = 1.0; source = 0.8; query = 0.5
[relevance.typeAffinityMatrix.synthesis]
concept = 1.2; entity = 1.0; source = 1.0; query = 1.0; synthesis = 0.8
```

Lookup is `affinity[source.type][target.type]`; a pair absent from the matrix
falls back to `0.5` (TS `?? 0.5`). The scalar `relevance.typeAffinity` weight
multiplies the looked-up cell, exactly as `relevance.ts` does today. Setting one
cell **merges** over the defaults — untouched cells keep their values.

### Per-constant semantics notes

- **BM25 `k1`/`b`**: FTS5's native `bm25()` has fixed k1/b. With no override
  (or values equal to the config defaults) the Python keyword path uses the
  FTS5-native scoring byte-identical; a *non-default* override switches to a
  deterministic Python-side BM25 rescoring over the FTS5 candidate rows
  (same IDF formula as `mcp-server/src/search.ts`).
- **Insights signal scores**: the five scores drive the TS signal registry
  (`graph-engine/src/insights.ts`). The Python insights scorer is a coarser
  model (no distant-pair or low-weight signals); when a signal score is
  overridden, `crossCommunity` replaces its cross-community base (1.0),
  `crossTypeWeak` its cross-type contribution (0.5) and `peripheralToHub` its
  peripheral→hub factor (0.8) — with no override the Python literals are
  unchanged.
- **`insights.surpriseThreshold` / `peripheralHubRatio`** only take effect in
  the Python insights consumer when explicitly overridden (the Python scorer
  has no threshold and uses its own 0.4 gate by default).

## Precedence

```
CLI --set section.key=value  >  LLM_WIKI_TUNE__SECTION__KEY env  >  <wiki>/tuning.toml  >  code defaults
```

With none present, the resolved value **is** the code default → byte-identical
behavior. Unknown keys and out-of-range values **fail closed** (exit 2 with the
offending key) — never a silent no-op.

## The emit surface (Python → graph-engine)

Resolve + emit the full profile as JSON (applies CLI > env > file):

```bash
# one-off profile from CLI overrides:
llm-wiki tuning ~/wikis/my-project --set relevance.directLink=5 --json
# write it for the graph-engine (wiki's tuning.toml + env apply):
llm-wiki tuning ~/wikis/my-project --emit /tmp/tuning.json
# graph-engine consumes the SAME resolved profile:
node graph-engine/dist/index.js --wiki ~/wikis/my-project --action build    --tuning-json /tmp/tuning.json
node graph-engine/dist/index.js --wiki ~/wikis/my-project --action insights --tuning-json /tmp/tuning.json
```

The emitted shape is `to_graph_engine_json()`:
`{relevance:{weights,typeAffinityMatrix}, insights:{thresholds + signalScores}, community:{resolution,seed}, retrieval, bm25, claims}`.
The graph-engine maps it into its existing `RelevanceOptions` / `InsightsOptions` /
`LouvainOptions`; a missing/invalid file falls back to built-in defaults
(byte-identical). `llm-wiki tuning` with no flags prints the resolved flat map.

## Consumers (where each constant is effective)

| Constant | Python consumer | TS consumer |
|---|---|---|
| `relevance.*` weights + matrix | emitted JSON → `--tuning-json` | `calculateRelevance` via `RelevanceOptions` (`build.ts` step 6, `relevance` action) |
| `insights.surpriseThreshold`, `sparse*`, `bridgeCommunityMin`, `peripheral*`, `isolatedMaxDegree` | `llm-wiki insights` (`compute_insights` → `find_gaps`/`score_connections`) | `findSurprisingConnections` / `detectKnowledgeGaps` via `InsightsOptions` |
| `insights.signalScores.*` | `score_connections` (override-only, see above) | the four signal functions in `insights.ts` |
| `community.resolution` / `seed` | `llm-wiki insights` (Louvain via `detect_communities`) | `detectCommunities` via `LouvainOptions` (`build.ts` step 7) |
| `community.engine` (`louvain`\|`leiden`, default `louvain`) | community-engine selector (`insights`, `summarize-communities`) — gated by the parity gate, never flips on its own | — (Python-only) |
| `retrieval.rrfK` / `simFloor` | `llm-wiki search` hybrid; MCP sidecar `hybrid_search` (auto-resolves the wiki's `tuning.toml`) | — (Python-only) |
| `bm25.k1` / `b` | `llm-wiki search --keyword` + hybrid fallback (Python rescoring on override) | — (Python-only) |
| `claims.penalty*` / `failBelow` | `llm-wiki claims redteam` (health score + exit line) | — (Python-only) |

## How to run the gate / tune split

Re-tuning is eval-gated: a default may only move with an attached eval report
showing **no GATE regression** (ADR-0028 §Eval-tuned-defaults). The harness
(LWM_022) enforces a disjoint split — tuning callers receive only the TUNE split
(`eval/goldset.py::load_tune_split`); they structurally cannot see GATE labels:

```bash
# sweep a constant on the TUNE split only (one-off, never persisted):
llm-wiki eval ~/wikis/my-project --split tune --k 5
llm-wiki search ~/wikis/my-project "query" --set retrieval.simFloor=0.45

# the GATE split is reserved for regression checks with the committed baseline:
llm-wiki eval ~/wikis/my-project --split gate --k 5
PYTHONPATH=src python3 -m pytest tests/test_search_eval_gate.py tests/test_eval_regression.py -q
```

A candidate profile is frozen in the wiki's `tuning.toml` (the only surface that
can move a shipped default, and only with the eval report attached) — it travels
with `git clone`, is diffable in review, and is picked up by every consumer that
resolves tuning from the wiki root.

## Examples

```bash
# 1. One-off sweep — CLI (highest precedence, never persisted):
llm-wiki search ~/wikis/my-project "transformer" --set bm25.k1=0.5 --set bm25.b=0.4
llm-wiki insights ~/wikis/my-project --format json --set insights.sparseCohesionThreshold=0.25

# 2. Ephemeral / CI — env vars:
LLM_WIKI_TUNE__retrieval__simFloor=0.45 \
LLM_WIKI_TUNE__community__resolution=1.3 \
  llm-wiki search ~/wikis/my-project "attention"

# nested keys use extra __ segments:
LLM_WIKI_TUNE__relevance__typeAffinityMatrix__entity__concept=1.5 \
LLM_WIKI_TUNE__insights__signalScores__crossCommunity=4 \
  llm-wiki tuning ~/wikis/my-project --json

# 3. Committable profile — <wiki-root>/tuning.toml:
#    [relevance]
#    directLink = 5.0
#    [relevance.typeAffinityMatrix.entity]
#    concept = 1.5
#    [insights.signalScores]
#    crossTypeWeak = 2
#    [community]
#    resolution = 1.2
#    [claims]
#    penaltyStale = 4

# 4. Emit + feed the graph-engine:
llm-wiki tuning ~/wikis/my-project --emit /tmp/tuning.json
node graph-engine/dist/index.js --wiki ~/wikis/my-project --action build --tuning-json /tmp/tuning.json
```

## Fail-closed behavior

| Failure mode | Response |
|---|---|
| Unknown key (typo) | `config error: unknown tuning key: ...` → exit 2 |
| Out of range (negative weight, `resolution<=0`, `simFloor∉[0,1]`, `k1<0`) | `config error: ... out of range` → exit 2 |
| Malformed `tuning.toml` / env var / `--set` | `config error: ...` → exit 2, nothing partially applied |
| No config present | code defaults (byte-identical) |
| Graph-engine tuning JSON missing/invalid | TS falls back to built-in defaults |

## Guarding tests

- `tests/test_tuning_config.py::test_all_constants_configurable` — every one of
  the 52 keys reachable via CLI + visible in the emit boundary; consumer
  wiring tests for Louvain/insights/claims/BM25.
- `tests/test_tuning_config_defaults.py` — golden snapshot
  (`tests/eval/baseline/tuning_defaults.json`): the default profile is
  **committed**; any default change fails CI. Plus partition-identity guards on
  `tests/fixtures/graphs/*.json`.
- `graph-engine/test/tuning-parity.test.ts` — a non-default profile emitted by
  Python resolves to identical options in TS; the default profile is
  byte-identical to no options (golden fixture).
