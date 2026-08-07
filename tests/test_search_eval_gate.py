"""Search-eval gate + gold-set integrity (LWM_032).

Certifies the one elected default change of v0.5.0: hybrid may become the search
default only when it does not regress keyword recall/precision on the held-out
GATE split (fail-closed). Uses a deterministic concept embedder so the gate is
reproducible offline; CI re-certifies with the real [semantic] embedder.
"""

from pathlib import Path

from llm_wiki.eval.search_baseline import (
    load_search_goldset,
    run_search_baseline,
    search_eval_gate,
    split_items,
)
from llm_wiki.search.index import index_wiki
from llm_wiki.semantic.embed import embed_wiki
from llm_wiki.semantic.embedder import Embedder

GOLDSET = Path(__file__).parent / "eval" / "gold" / "search_goldset.json"

# Topic one-hot space: ml | attn | bev | none. Concept-aware so a paraphrase
# query ("deep learning model") matches the right pages that keyword misses.
_TOPICS = {
    "ml": ["neural network", "deep learning", "backpropagation", "layers"],
    "attn": ["attention", "transformer", "sequences"],
    "bev": ["coffee", "brewed", "beverage", "roasted", "beans"],
}
_DIM = {"ml": 0, "attn": 1, "bev": 2, "none": 3}


def _topic_of(text: str) -> str:
    t = text.lower()
    best, score = "none", 0
    for topic, kws in _TOPICS.items():
        hits = sum(1 for kw in kws if kw in t)
        if hits > score:
            best, score = topic, hits
    return best


class _ConceptEmbedder(Embedder):
    model_id = "concept"
    revision = "r"
    normalization = "l2"
    quantization = "float32"

    @classmethod
    def is_available(cls):
        return True

    @property
    def dimension(self):
        return 4

    def embed(self, texts):
        out = []
        for t in texts:
            v = [0.0, 0.0, 0.0, 0.0]
            v[_DIM[_topic_of(t)]] = 1.0
            out.append(v)
        return out


_PAGES = {
    "neural_network.md": "A neural network learns weights via backpropagation.",
    "deep_learning.md": "Deep learning stacks many neural network layers.",
    "transformer.md": "The transformer uses attention over sequences.",
    "coffee.md": "Coffee is a brewed beverage from roasted beans.",
}


def _make_wiki(tmp_path, embed=True):
    w = tmp_path / "wiki"
    w.mkdir()
    for nm, body in _PAGES.items():
        (w / nm).write_text(
            f"---\ntitle: {nm[:-3]}\ntype: concept\n---\n\n# {nm[:-3]}\n\n{body}\n",
            encoding="utf-8",
        )
    index_wiki(tmp_path, rebuild=True)
    if embed:
        embed_wiki(tmp_path, embedder=_ConceptEmbedder())
    return tmp_path


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
    hy = run_search_baseline(root, gate_items, "hybrid", embedder=_ConceptEmbedder())
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
