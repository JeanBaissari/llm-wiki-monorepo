# ADR 0021: No Auto-Apply on Static-Embedding Similarity Alone

- **Status:** accepted (amended: `--apply` unblocked by ADR-0024 / LWM_025)
- **Date:** 2026-08-06
- **Context:** LWM_021 (v0.4.0 semantic link suggestion) fuses up to three candidate signals for a source page — embedding (cosine KNN over the v0.4.0 vectors), PPR (Personalized PageRank seeded at the source, numpy-free power iteration), and lexical (the existing entity/registry engine `graph/suggest.py`). A static-embedding (model2vec) similarity is a weak, similarity-only signal: auto-applying links or merges on that signal alone risks corrupting the curated wikilink structure with false positives. This is a file-mutation safety policy that lasts beyond one PRD.

## Decision

**A static-embedding similarity may NEVER be the sole justification for an auto-applied link** (or an entity merge — cross-referenced in ADR-0024):

- Only **non-static signals corroborate a link on their own**: `_NON_STATIC_SIGNALS = {"lexical", "ppr"}` (`semantic/linking.py`). `is_auto_appliable(suggestion)` returns True only when one of those corroborates the suggestion.
- **Embedding-only suggestions are suggest-only**: they are returned and tagged with their signals, but never applied.
- **`--apply`** writes a link **only** when the suggestion is auto-appliable **and** the target entity is actually mentioned in the source prose — reusing the surface-preserving `apply_suggestions` machinery, which writes `[[Canonical|surface]]` (surface form preserved). Each row is tagged with which kind it is.
- **Amendment (ADR-0024 / LWM_025):** resolved aliases of a target also count as mentions, which unblocked the semantic `--apply` path: alias mentions route to the canonical page via the `.llm-wiki/entities/aliases.jsonl` store — still only as `[[Canonical|surface]]`, surface preserved. The no-auto-apply-on-embedding-alone rule is unchanged.

## Delivered State (defe7e0)

Implemented: `is_auto_appliable` + `semantic_related` (3-signal RRF fusion) in `semantic/linking.py`; `_apply_semantic` in `graph/suggest.py` applies only auto-appliable two-signal rows whose target is mentioned in prose (alias-aware via `alias_targets`). LWM_021 shipped suggest-only in v0.4.0; the LWM_025 alias store unblocked `--apply` in v0.5.0. No remediation batch is outstanding for this ADR.

## Consequences

**Easier:** the wikilink graph stays curated — the highest-value signal (embedding) is used for ranking, while only corroborated suggestions mutate files; every applied link is `[[Canonical|surface]]` and therefore reviewable. **Harder:** embedding-only related notes require a second signal to surface in `--apply`, so some true links are not auto-applied; the distinction between suggest-only and auto-appliable must be preserved by every future signal producer.
