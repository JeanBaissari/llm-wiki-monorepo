# ADR 0030: Confidence Formula + Contradiction Review Surface

- **Status:** accepted
- **Date:** 2026-08-11
- **Context:** LWM_034 (v0.6.0) — the `confidence` / `contested` / `contradictions` frontmatter fields shipped inert since v0.2.x. Nothing computed them, so "confidence: high" on a page with one stale source was indistinguishable from one with five recent sources, and two pages asserting X and ¬X coexisted silently. The epistemic gap: evidence-derived values, not author intention, with a reviewable, reversible surface.

## Decision

**A deterministic, eval-gated epistemic layer** (`src/llm_wiki/quality/contradictions.py`) with three contracts:

- **Claim extraction:** typed rows `(subject, predicate, object/quantifier, polarity, page, span)`, grounded via the LWM_025 entity layer; deterministic on the base install (stdlib + existing modules); opt-in `--assist llm` screening degrades gracefully.
- **Contradiction detection (suggest-only):** pairs claims across pages on shared (subject, predicate) with opposing polarity, incompatible numeric values (via a **minimal base-install unit-normalization table**: KB/KiB, MB/MiB, GB/GiB, TB/TiB, ms/s, case-insensitive — so "3.2 MB" vs "3.2 MiB" is NOT false-flagged), or mutually exclusive categories. `detect` writes NOTHING; `--apply` writes the `contradictions` frontmatter field; `unapply` reverses it (round-trip tested). The `.llm-wiki/claims/` sidecar (`ClaimsManager`) is reused — idempotent batch writers, no parallel storage.
- **Confidence formula (author-overridable):** `evidence_score = 0.30·source_signal + 0.20·recency + 0.25·citation_support + 0.25·agreement`, mapped high ≥ 0.70 / medium ≥ 0.40 / low; recency anchored to the wiki's freshest `updated` (deterministic, never wall-clock); missing `sources` **or** `updated` → forced `low` (capped 0.39, never high). Author intent is never silently overwritten: an explicit author-set confidence with a non-`evidence` marker stays, and the field records `confidence_source: evidence|author`.
- **Review surface:** `llm-wiki contradictions <wiki> detect|list|apply|unapply` + a lint pass reporting detected conflicts through the existing "contradiction signals" pattern (no output-shape change for existing rules).
- **Eval-gated:** committed contradiction gold set (positives + negatives) and confidence gold set, precision/recall/accuracy vs committed baselines, `tune ∩ gate = ∅` (ADR-0022), fail-on-drop.

## Delivered State

`src/llm_wiki/quality/contradictions.py`, `src/llm_wiki/eval/contradiction_baseline.py`, `src/llm_wiki/quality/claims/storage.py` (additive idempotent batch writers), `tests/test_contradictions.py` (22 tests), `tests/eval/gold/contradiction_goldset.json` (8 items: 4 pos / 4 neg) + `confidence_goldset.json` (7 items), `tests/eval/baseline/` both baselines (gate precision/recall 1.0, confidence accuracy 1.0), `tests/test_contradiction_eval.py` + `tests/test_confidence_eval.py`, lint hook in `quality/lint/service.py`.

## Consequences

**Easier:** the wiki can say "these two pages disagree" and confidence reflects evidence; authors retain override control via `confidence_source`; all writes are reversible/apply-gated. **Harder:** lexical extraction catches numeric/polarity/exclusive-category conflicts well but misses subtle paraphrased contradictions (opt-in LLM screening); the `contradictions` field writes are frontmatter-only and single-line-format byte-restored on unapply.
