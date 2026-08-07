# ADR 0022: Eval Gold-Set Tune/Gate Split Methodology

- **Status:** accepted
- **Date:** 2026-08-06
- **Context:** LWM_022 (v0.4.0 semantic eval harness) established the evidence semantics by which this repo judges retrieval and link suggestion — and therefore by which any default change is certified (reused by LWM_032/ADR-0020's search gate). The core hazard: if the set used to *tune* constants overlaps the set used to *gate* releases, every measured improvement is circular and a release can be certified by overfit.

## Decision

**The eval harness is trustworthy only if the set used to tune constants is disjoint from the set used to gate releases** — enforced structurally, not by convention:

- **Gold-set format:** JSON, versioned; every item declares a `split` of `"tune"` or `"gate"`, a `query`, `relevant` page-ids, and an optional `kind` (`positive` / `negative`; an empty `relevant` makes an item a negative — the "gibberish → empty" adversarial lane).
- **Disjointness is fail-closed:** `load_goldset` raises `GoldSetError` if any query appears in both splits (`_validate_disjoint`).
- **Tuning structurally cannot read gate labels:** constant-tuning code receives only the `tune_only()` view; the `gate_only()` view is used exclusively by the release gate (`eval/goldset.py`).
- **Absolute metrics, not just deltas:** `precision@k` (k ∈ {1, 3, 5, 10}), `recall`, and negative-pass rate are pure, stdlib-only ranking metrics (`eval/metrics.py`); absolute numbers are reported so a baseline is interpretable on its own and a low-but-non-regressing score is surfaced rather than hidden.
- **Baseline discipline:** the current lexical link-suggester is adapted onto the retrieval frame (`query → source page stem`, `relevant → correct target stems`, `predicted → ranked targets`) so one `evaluate` path scores today's lexical system and tomorrow's hybrid/semantic one without change; the committed baseline artifact (`tests/eval/baseline/eval_baseline.json`) is what the eval-regression gate (LWM_023 / ADR-0023) diffs future changes against.
- **`llm-wiki eval`** exits 0 on any successful run (absolute scores are surfaced, not hidden behind a non-zero exit); exit 2 only for usage/gold-set errors.
- **§Judge-separation / §DeepEval:** any future LLM-judged metrics must keep generator and judge model families separate; DeepEval (Apache-2.0) is an optional `[eval]` carrier — the metrics are our own, so the harness is reversible.

## Delivered State (defe7e0)

Implemented: `eval/goldset.py` (split enforcement), `eval/metrics.py`, `eval/baseline.py`, `eval/cli.py`, committed `tests/eval/baseline/eval_baseline.json`; the LWM_032 search gate reuses the same governance with its own committed search gold set (`tests/eval/gold/search_goldset.json`, tune ∩ gate = ∅). No remediation batch is outstanding for this ADR.

## Consequences

**Easier:** every tuning claim and every default flip is now testable against a held-out, never-tuned set; overfitting to the gate is structurally impossible. **Harder:** gold sets must be curated and maintained (any wiki change that invalidates labels requires a review); the tune split must be re-verified for disjointness on every load.
