# ADR 0029: Ask Surface + Grounded-Citation Faithfulness Contract

- **Status:** accepted
- **Date:** 2026-08-11
- **Context:** LWM_033 (v0.6.0) — community summaries existed (LWM_030) and hybrid retrieval was the certified default (LWM_032), but the wiki was retrieval-shaped, not question-shaped. The ask surface answers natural-language questions grounded in the wiki; the risk is ungrounded hallucination and unbounded LLM cost. LWM_030 already established the `summary_faithfulness` discipline (key entities ⊆ member entities); this ADR extends that discipline to the ask surface and pins the contract.

## Decision

**One grounded `llm-wiki ask` operation with a faithfulness contract** (`src/llm_wiki/graph/ask.py`):

- **Retrieval:** hybrid search (LWM_032 path; `--keyword` forces lexical; without `[semantic]` it degrades byte-identically to keyword+summaries) + a deterministic **summary-aware rerank**: tier 0 = community-summary pages (located by `type: community-summary` frontmatter, never by directory) whose member set/key entities overlap the query's genuinely-relevant top hits; tier 1 = their member pages; tier 2 = remaining raw hits in rank order.
- **Synthesis:** exactly **one** structured LLM call via `providers/registry.py::call_llm_structured` with `provider="default"` (the agent-native `$0.00` path, ADR-0009) unless overridden; output `{answer, citations: [page stems], confidence, faithfulness}`.
- **Faithfulness contract:** answer entities ⊆ cited-page entities ⊆ retrieved-context entities (inherits the LWM_030 filter). Citations must be real, retrieved page stems. Hallucinated entities are rejected.
- **Deterministic offline mode:** `--no-llm` makes ZERO LLM calls and returns the grounded passages (CI-pinned via the response-file/injection path); `--dry-run` prints the retrieval plan without calling the LLM.
- **Graceful degradation:** no `community-summary` pages present → flat retrieval with a "no summaries yet — flat retrieval" note; never auto-runs `summarize-communities` (summaries stay opt-in).
- **Eval-gated:** committed ask gold set (`tests/eval/gold/ask_goldset.json`) scored by citation precision@k on the deterministic retrieval path, `tune ∩ gate = ∅` (ADR-0022), baseline `tests/eval/baseline/ask_baseline.json` fail-on-drop; the gold set grows per-minor via the standing curation procedure (LWM_039 §A).
- **MCP:** `llm_wiki_ask` mirrors the `handleSearch` sidecar pattern — graph/search logic stays in the Python sidecar (v0.6.0 invariant 4); no sidecar → graceful error.

## Delivered State

`src/llm_wiki/graph/ask.py`, `src/llm_wiki/eval/ask_baseline.py`, `tests/test_ask.py` (6 evidence-matrix tests incl. `test_hallucinated_entity_rejected`, `test_no_llm_passes_only`, `test_agent_native_zero_apikey`), `tests/eval/gold/ask_goldset.json` (12 items, 6 tune/6 gate, hybrid baseline precision@1 = 1.0), `tests/test_ask_eval.py`, `mcp-server/src/tools/ask.ts` + `registry.ts` (`llm_wiki_ask`), `skill/scripts/sidecar.py` ask RPC.

## Consequences

**Easier:** the wiki answers questions with citations; the summaries LWM_030 produces are consumable; cost is bounded (one call, optional). **Harder:** faithfulness is enforced at the entity level — paraphrased-but-unsupported answers still pass unless the retrieval + filter catch them; the surface is single-shot (multi-hop agentic RAG is explicitly deferred to a later wave).
