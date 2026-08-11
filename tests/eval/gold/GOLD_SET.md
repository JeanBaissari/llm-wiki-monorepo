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
