"""Search-eval gate + gold-set integrity (LWM_032 / ADR-0020).

Certifies the one elected default change of v0.5.0: hybrid may become the
search default only when it does not regress keyword recall/precision on the
held-out GATE split (fail-closed). Local runs use the deterministic concept
embedder so the gate is reproducible offline; CI's `semantic` job re-certifies
with the real [semantic] embedder (tests/eval/test_real_wiki_gate.py, which
runs only there). Base installs stay lexical-only — hybrid degrades to keyword
byte-identically.
"""

from pathlib import Path

from llm_wiki.eval.search_baseline import (
    ConceptEmbedder,
    build_search_gold_wiki,
    load_search_goldset,
    run_search_baseline,
    search_eval_gate,
    split_items,
)

GOLDSET = Path(__file__).parent / "eval" / "gold" / "search_goldset.json"


def _make_wiki(tmp_path, embed=True):
    """Deterministic gold wiki: 4 topical pages, FTS5 index, optional vectors."""
    return build_search_gold_wiki(
        tmp_path,
        embedder=ConceptEmbedder() if embed else None,
    )


# ── gold-set integrity ───────────────────────────────────────────────────────

def test_goldset_disjoint_and_query_to_pages():
    data = load_search_goldset(GOLDSET)  # raises if tune∩gate ≠ ∅
    for item in data["items"]:
        assert "query" in item and "relevant" in item  # retrieval labels, not link labels
        assert isinstance(item["relevant"], list)


def test_leaked_query_rejected(tmp_path):
    import json
    import pytest
    bad = {"items": [{"query": "dup", "split": "tune", "relevant": []},
                     {"query": "dup", "split": "gate", "relevant": []}]}
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError):
        load_search_goldset(p)


# ── the promotion gate ───────────────────────────────────────────────────────

def test_hybrid_ge_keyword_on_gate(tmp_path):
    root = _make_wiki(tmp_path, embed=True)
    gate_items = split_items(load_search_goldset(GOLDSET), "gate")
    kw = run_search_baseline(root, gate_items, "keyword")
    hy = run_search_baseline(root, gate_items, "hybrid", embedder=ConceptEmbedder())
    allow, report = search_eval_gate(kw, hy)
    assert allow is True, report
    # The paraphrase query genuinely helps: hybrid recall strictly exceeds keyword.
    assert hy["recall"] >= kw["recall"]
    assert hy["negative_pass_rate"] == 1.0  # gibberish stayed empty


def test_gate_fails_closed_on_regression():
    # Synthetic metrics where hybrid is worse → the gate must refuse the flip.
    kw = {"recall": 0.9, "precision_at_k": {1: 0.9, 3: 0.9, 5: 0.9, 10: 0.9},
          "negative_pass_rate": 1.0}
    hy = {"recall": 0.5, "precision_at_k": {1: 0.5, 3: 0.5, 5: 0.5, 10: 0.5},
          "negative_pass_rate": 1.0}
    allow, report = search_eval_gate(kw, hy)
    assert allow is False
    assert "fail-closed" in report["reason"]


def test_gate_fails_when_negatives_leak():
    kw = {"recall": 0.5, "precision_at_k": {1: 0.5, 3: 0.5, 5: 0.5, 10: 0.5},
          "negative_pass_rate": 1.0}
    hy = {"recall": 0.6, "precision_at_k": {1: 0.6, 3: 0.6, 5: 0.6, 10: 0.6},
          "negative_pass_rate": 0.5}  # hybrid returned junk for a gibberish query
    allow, _ = search_eval_gate(kw, hy)
    assert allow is False


# ── default flip + escape hatch (CLI) ─────────────────────────────────────────

def test_cli_default_is_hybrid_and_keyword_escape_hatch(tmp_path):
    import sys as _sys
    from llm_wiki.search import query as q
    from llm_wiki.search.query import keyword_search

    root = _make_wiki(tmp_path, embed=False)  # indexed, NOT embedded

    def _run(argv):
        old = _sys.argv
        try:
            _sys.argv = argv
            return q.main()
        finally:
            _sys.argv = old

    # Default (hybrid) with no vectors degrades to keyword byte-identically.
    assert _run(["llm-wiki search", str(root), "neural", "--json"]) == 0
    # Explicit --keyword also works and returns the same lexical results.
    assert _run(["llm-wiki search", str(root), "neural", "--keyword", "--json"]) == 0
    kw = keyword_search(root, "neural", 10)
    assert kw and all("path" in r for r in kw)  # keyword path intact
