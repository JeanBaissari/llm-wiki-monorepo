# GOLD_SET.md — Search Gold Set (LWM_032 / ADR-0020)

This directory holds the **search** gold set — free-text `query → relevant
page-ids` retrieval labels — plus its split-freeze manifest. It is **distinct
from the link-suggestion gold set** (`tests/eval/fixtures/goldset_seed.json`,
which maps source-page stems → target link stems). Search labels certify
*retrieval*; link labels certify *linking*. They never blur.

## Purpose

The v0.5.0 elected default change is hybrid search. Before the default flip,
an eval gate must prove `hybrid.recall ≥ keyword.recall` and
`hybrid.precision@k ≥ keyword.precision@k` on a held-out **GATE** split
(fail-closed; the flip stays keyword if the gate is red). The gold set here is
what the gate runs on, and the committed baseline
(`tests/eval/baseline/search_eval_baseline.json`) freezes the gate's numbers.

## Files

| File | Role |
|------|------|
| `search_goldset.json` | The labels: `{version, task, items:[{query, relevant:[page_id], split, kind}]}` |
| `split_manifest.json` | Freeze: SHA256 of `search_goldset.json` + the tune/gate query lists |
| `../baseline/search_eval_baseline.json` | Committed keyword + hybrid metrics on the GATE split |

## Format

```json
{
  "version": 1,
  "task": "search-retrieval",
  "items": [
    {"query": "neural network", "relevant": ["neural_network", "deep_learning"],
     "split": "tune", "kind": "positive"},
    {"query": "zzzznonexistentqqq wut", "relevant": [],
     "split": "gate", "kind": "negative"}
  ]
}
```

- `relevant` lists **page-ids** (file stems of the deterministic gold wiki built
  by `llm_wiki.eval.search_baseline.build_search_gold_wiki`).
- `split` is `tune` or `gate` — disjoint, asserted at load
  (`load_search_goldset` raises on overlap) and by
  `tests/eval/test_search_goldset_integrity.py`.
- `kind` is `positive` (≥1 relevant page) or `negative` (gibberish →
  `relevant: []`, must return empty under both modes).

## Splits

- **tune** — exposed to threshold/weight fitting (LWM_031 sweeps).
- **gate** — held-out, loadable only by the scoring path. The committed
  baseline and the promotion gate run on this split only.

The real-wiki gate lane (`tests/eval/test_real_wiki_gate.py`) uses the
populated fixture wiki with **gate-only** labels defined inside that file —
never tuned, and only ever scored.

## Growth history

- **v1 (v0.5.0):** 6 queries (2 tune / 4 gate) — the initial hand-labeled
  batch the hybrid-default flip shipped on.
- **v2 (BKD-002, 2026-08-11):** 30 queries (14 tune / 16 gate = 13 positive +
  4 negative on the gate split). Gold wiki grown 4 → 15 pages across four
  topic lanes (ml / attn / bev / sys); the deterministic concept embedder is
  now two-signal (topic one-hot + token bag-of-words, L2-normalized) so the
  offline gate mirrors real-embedder ranking behavior. The growth exposed a
  metric-correctness issue — the search gate now uses **padded precision@k**
  (`hits/k`, `metrics.precision_at_k_padded`) instead of the min-normalized
  link-suggestion metric, which made hybrid's extra recall look like
  precision loss. This is a measurement fix, not a gate loosening: hybrid
  must still be ≥ keyword at every k, and it is (see the committed baseline).

## How to add entries

1. Edit `search_goldset.json`: add `{query, relevant, split, kind}` items.
   Keep `tune ∩ gate = ∅` and keep at least one gibberish `negative`.
2. If the label refers to a new page, add the page to
   `SEARCH_GOLD_PAGES` in `src/llm_wiki/eval/search_baseline.py` (the
   deterministic gold wiki builder) and re-verify the fixture.
3. **Re-freeze the manifest**: `sha256sum tests/eval/gold/search_goldset.json`
   → update `split_manifest.json` `sha256` and the tune/gate query lists.
   Editing the goldset without re-freezing fails
   `test_manifest_sha256_matches_goldset` closed.
4. Re-generate the baseline: `PYTHONPATH=src python3 -m
   llm_wiki.eval.search_baseline --output
   tests/eval/baseline/search_eval_baseline.json` — commit the honest new
   numbers.

## How the gate consumes it

1. `tests/test_search_baseline_reproducible.py` re-derives keyword + hybrid
   metrics on the GATE split with the deterministic concept embedder and
   asserts they match the committed baseline exactly (reproducibility +
   fail-on-drop).
2. `tests/test_search_eval_gate.py` runs the fail-closed promotion gate on the
   same split.
3. CI's `semantic` job re-certifies with the **real** [semantic] embedder via
   `tests/eval/test_real_wiki_gate.py` (model2vec on the populated fixture).
4. `scripts/release_certify.py` runs the gate as part of release
   certification (`gate_search_eval`).

## Freeze procedure

The manifest's `sha256` is the freeze. Any change to the gold set content —
intended or not — requires a deliberate manifest update. This is the reviewed
rebaseline path: a PR that changes the gold set and the baseline together is
expected; a PR that changes one without the other fails a test.

## Standing per-minor curation loop (LWM_039 §A)

The one-shot "How to add entries" flow above is the underlying primitive. The
**standing path** is a per-minor curation loop that every minor shipping a
retrieval change MUST run. It is codified in `scripts/curate_gold_set.py`; this
section is its procedure contract.

### Cadence

- **Every minor that ships a retrieval change** runs the loop once. The frozen
  `split_manifest.json` currently anchors **17 gate queries** (13 positive + 4
  negative — the committed manifest is the count of record, not the prose).
  `MIN_GATE_QUERIES = 16` (in `tests/eval/gold/growth_meta.json`) is the
  committed floor: the gate split may never drop below it.
- **Grow-or-justify rule:** each minor either adds **≥ 2 new gate queries**
  (`MIN_GROWTH_PER_MINOR`) **or** records a written justification in
  `tests/eval/gold/growth_meta.json` via `curate_gold_set.py --growth-record`.
  A minor that skips both fails the freshness gate's intent (skipped loop).
- The freshness marker is `growth_meta.json.last_grown_minor`; certify warns
  when it is older than the previous minor.

### Labeling guidance

- **Real-wiki queries stay `split:"gate"` only, never tuned** — mirrors the
  `tests/eval/test_real_wiki_gate.py` lane; the curator rejects any tune item
  that duplicates a real-wiki gate label.
- **Gibberish negatives grow proportionally** — each growth event that adds
  positives also adds ≥ 1 gibberish `negative`, keeping the gate negative
  fraction inside the ~20–30% band (the current gate is 4/17 ≈ 24%).
- **`tune ∩ gate = ∅` is asserted** — both at load (`load_search_goldset`
  raises on overlap) and by `tests/eval/test_search_goldset_integrity.py`.
- **Positives must have ≥ 1 relevant page id** that resolves to a page in
  `SEARCH_GOLD_PAGES` (the deterministic gold wiki in
  `src/llm_wiki/eval/search_baseline.py`); an ungroundable query is a negative
  or is rejected.

### Mechanics

`python3 scripts/curate_gold_set.py` is the tool (stdlib, `argparse`, exit
0 clean / 1 issues / 2 usage). Actions:

- **check** (default): validates `tune ∩ gate = ∅`, ≥ 1 gibberish `negative`
  on the gate split, `search_goldset.json` SHA256 == `split_manifest.json`
  `sha256`, and gate query count ≥ `min_gate_queries`. Exit 1 on any violation.
- **`--freeze`**: recompute the SHA256 + rewrite the manifest's tune/gate query
  lists. Idempotent: a no-op on an in-sync manifest. Run after an intentional
  gold-set edit.
- **`--rebaseline`**: regenerate `tests/eval/baseline/search_eval_baseline.json`
  via the sanctioned command only (`PYTHONPATH=src python3 -m
  llm_wiki.eval.search_baseline --output …`) and assert the regenerate is
  byte-stable against the committed baseline when nothing changed.
- **`--growth-record <minor> <note>`**: update `growth_meta.json`
  (`last_grown_at`, `last_grown_minor`, `notes`) — the grow-or-justify record.

The committed `tests/eval/gold/growth_meta.json` is the per-minor bookkeeping
record (`version`, `min_gate_queries`, `last_grown_at`, `last_grown_minor`,
`notes`). Its latest `last_grown_minor` is the freshness marker consumed by the
release-certify gate.

### Freshness gate

`scripts/release_certify.py` registers **`gate_search_goldset_fresh`**
(runnable alone via `--gate search_goldset_fresh`, or as part of the default
certify). It **fails closed** when the gold-set integrity SHA drifts from the
manifest or the gate split falls below `min_gate_queries`; it emits a **warn**
(not a failure) when `growth_meta.json.last_grown_minor` is older than the
previous minor (grow-or-justify skip), and fails when the freshness marker is
absent entirely. Real regression (search-eval red, `gate_search_eval`) already
fails the default certify on its own gate.
