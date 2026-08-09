# ADR 0020: Hybrid Search — RRF Ranking + Promotion to Default (Eval-Gated)

- **Status:** accepted
- **Date:** 2026-08-07
- **Context:** v0.4.0 (LWM_019/LWM_020) shipped hybrid search (BM25 + vector KNN fused by Reciprocal Rank Fusion) as **opt-in**, with the keyword default deliberately deferred "until the eval harness proves no keyword-recall regression (ADR-0020)". LWM_032 (v0.5.0) is the **one elected default change** of the v0.5.0 minor: flip hybrid to default — but only after a committed search gold set and a fail-closed eval gate prove parity on the held-out GATE split.

## Decision

**RRF ranking (LWM_019):** fused score `score(item) = Σ_lists 1/(k + rank)` (rank 1-based, k≈60, deterministic tie-break `(-score, item)`). Using ranks — not raw scores — means BM25 magnitudes and cosine similarities never need to be normalized against each other, which is why RRF is the low-risk default for hybrid (see `semantic/fusion.py`). A cosine floor (`simFloor` = 0.30) keeps gibberish queries returning empty.

**Hybrid-default promotion policy (LWM_032):** hybrid search becomes the **default** for `llm-wiki search` and the MCP `llm_wiki_search` tool **only after** the search-eval gate proves **no keyword recall/precision regression** on the held-out GATE split of a committed search gold set (`tests/eval/gold/search_goldset.json`, distinct from the v0.4.0 link-suggestion set):

- **Search gold set:** `query → relevant page-ids`, **tune ∩ gate = ∅** (asserted at load; reuse of ADR-0022 governance), adversarial gibberish negatives (`relevant: []` → must return empty).
- **Gate:** fail-closed — `hybrid.recall ≥ keyword.recall − tol` **and** `hybrid.precision@k ≥ keyword.precision@k − tol` for every k ∈ {1, 3, 5, 10} on the GATE split, with gibberish still empty. `tol = 1e-6` (`DEFAULT_TOL` in `eval/search_baseline.py`). Any regression refuses the flip.
- **Escape hatch retained:** `--keyword` (CLI) / `mode="keyword"` (MCP) forces lexical-only; `--hybrid` is kept as a suppressed back-compat no-op.
- **Byte-identical degradation:** without the `[semantic]` extra — or with no vectors / an `embed_meta` mismatch — hybrid returns exactly the keyword results (`hybrid_search` falls back to `keyword_search` byte-identically; LWM_013 invariant #2/#3).
- **§Format-compatibility:** flipping the default changes the MCP result header/provenance tags (`_matched`); the MCP result-content snapshot and `test_search_hybrid.py` are updated intentionally and reviewed — the sanctioned diff of this minor.
- **§Search-gold-set:** certified via the LWM_022 eval harness (reuses ADR-0022 tune/gate governance).

## Delivered State (defe7e0)

The gate is **green with the deterministic concept embedder** (`_ConceptEmbedder` in `tests/test_search_eval_gate.py` — reproducible offline); the default is flipped in `search/query.py` (hybrid default, `--keyword` escape) and `mcp-server/src/tools/search.ts` + `registry.ts` (`mode` default `"hybrid"`); `tests/eval/gold/search_goldset.json` and `eval/search_baseline.py` (runner + gate, tol 1e-6) are committed. **Real-embedder re-certification (the gate run with the actual model2vec `[semantic]` embedder) lands in remediation batch B8** — the ADR's acceptance contract holds; only the certifying evidence run is pending.

## Consequences

**Easier:** hybrid is the highest-leverage default precision win and is now the default on both surfaces; the gate makes the flip reversible by construction (a regression re-fails CI, and `--keyword` remains the user-facing undo). **Harder:** the default change intentionally updates the MCP result snapshot; hybrid output depends on the search gold set being representative — the real-embedder recertification (B8) must stay green at tag time.
