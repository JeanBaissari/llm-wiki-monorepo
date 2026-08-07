# Hybrid default search — operations note (v0.5.0, LWM_032 / ADR-0020)

## What changed

In v0.5.0, **hybrid** (BM25 + semantic vector KNN fused via RRF) became the
default for both `llm-wiki search` and the MCP `llm_wiki_search` tool, behind a
green search-eval gate on the held-out GATE split of the committed search gold
set (`tests/eval/gold/`, baseline in
`tests/eval/baseline/search_eval_baseline.json`).

## Operations implications

- **Search now uses the Python sidecar when `[semantic]` is present.** The MCP
  `llm_wiki_search` handler calls the sidecar's `hybrid_search` RPC; the sidecar
  embeds the query with model2vec (potion-retrieval-32M) and fuses with BM25.
- **Graceful degradation is guaranteed.** Without the `[semantic]` extra, no
  embedded index, or sidecar unavailability, the hybrid default falls through
  to the keyword path byte-identically — the base install stays lexical-only
  (proven by the `base-install-purity` CI job).
- **Vectors must exist for hybrid to help.** Run `llm-wiki embed <wiki>` once
  (requires `pip install 'baissarienterprises-llm-wiki[semantic]'`). Hybrid
  degrades to keyword if the index has no vectors.
- **Escape hatches (still supported, byte-identical to pre-flip keyword):**
  - CLI: `llm-wiki search <wiki> "query" --keyword`
  - MCP: `llm_wiki_search` with `mode: "keyword"`
- **Result formatting changed.** The hybrid path emits a
  `# Hybrid Search Results ...` header and `_[matched]_` provenance tags
  (`keyword` / `vector` / `both`) per result. This is the sanctioned v0.5.0
  output change (LWM_032 AC#4).

## Running the search-eval gate locally

```bash
# Deterministic offline gate (concept embedder — no [semantic] needed):
PYTHONPATH=src python3 -m pytest tests/test_search_eval_gate.py \
  tests/test_search_baseline_reproducible.py \
  tests/eval/test_search_goldset_integrity.py -q

# Real-embedder recert (requires the [semantic] extra; model2vec downloads a
# small model on first run):
pip install -e ".[semantic]"
PYTHONPATH=src python3 -m pytest tests/eval/test_real_wiki_gate.py -q

# Full release certification (includes the search-eval gate step):
PYTHONPATH=src python3 scripts/release_certify.py
```

## Regenerating the baseline (only with a deliberate gold-set change)

1. Edit `tests/eval/gold/search_goldset.json` (see
   `tests/eval/gold/GOLD_SET.md` for the freeze procedure).
2. Re-freeze `split_manifest.json` (SHA256).
3. `PYTHONPATH=src python3 -m llm_wiki.eval.search_baseline --output
   tests/eval/baseline/search_eval_baseline.json`
4. Commit gold set + manifest + baseline together — the integrity and
   reproducibility tests fail closed otherwise.
