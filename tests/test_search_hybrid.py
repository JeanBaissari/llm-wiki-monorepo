"""Tests for hybrid search: RRF fusion + keyword/hybrid query (LWM_019/020)."""

import hashlib
import json
import math
import sys

import pytest

from llm_wiki.search.index import index_wiki
from llm_wiki.search.query import hybrid_search, keyword_search
from llm_wiki.semantic.embed import embed_wiki
from llm_wiki.semantic.embedder import Embedder
from llm_wiki.semantic.fusion import reciprocal_rank_fusion, rrf_order


# ── RRF ──────────────────────────────────────────────────────────────────────

def test_rrf_prefers_items_high_in_multiple_lists():
    a = ["x", "y", "z"]
    b = ["x", "w", "y"]
    order = rrf_order([a, b])
    assert order[0] == "x"          # rank-1 in both lists
    assert set(order) == {"x", "y", "z", "w"}


def test_rrf_deterministic_tie_break():
    # two items each rank-1 in one list → tie on score → break by id
    fused = reciprocal_rank_fusion([["b"], ["a"]])
    assert [i for i, _ in fused] == ["a", "b"]


def test_rrf_empty():
    assert rrf_order([]) == []
    assert rrf_order([[], []]) == []


# ── fixtures: an indexed (and optionally embedded) tmp wiki ──────────────────

class _Fake(Embedder):
    model_id = "fake"
    revision = "r"
    normalization = "l2"
    quantization = "float32"

    @classmethod
    def is_available(cls):
        return True

    @property
    def dimension(self):
        return 6

    def embed(self, texts):
        out = []
        for t in texts:
            hb = hashlib.sha256(t.encode()).digest()[:6]
            v = [b / 255.0 for b in hb]
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out


_PAGES = {
    "neural_network.md": "A neural network learns weights via backpropagation.",
    "deep_learning.md": "Deep learning stacks many neural network layers.",
    "transformer.md": "The transformer uses attention over sequences.",
    "coffee.md": "Coffee is a brewed beverage from roasted beans.",
}


def _make_indexed_wiki(tmp_path, embed=False):
    w = tmp_path / "wiki"
    w.mkdir()
    for nm, body in _PAGES.items():
        (w / nm).write_text(
            f"---\ntitle: {nm[:-3]}\ntype: concept\n---\n\n# {nm[:-3]}\n\n{body}\n"
        )
    index_wiki(tmp_path, rebuild=True)
    if embed:
        embed_wiki(tmp_path, embedder=_Fake())
    return tmp_path


# ── keyword ──────────────────────────────────────────────────────────────────

def test_keyword_search_returns_ranked_hits(tmp_path):
    root = _make_indexed_wiki(tmp_path)
    res = keyword_search(root, "neural network", 5)
    assert res
    assert all("path" in r and "title" in r for r in res)
    # the neural-network page should rank at/near the top
    assert any("neural_network" in r["path"] for r in res[:2])


def test_keyword_search_empty_for_gibberish(tmp_path):
    root = _make_indexed_wiki(tmp_path)
    assert keyword_search(root, "zzzznonexistentqqq", 5) == []


def test_keyword_search_missing_index_is_empty(tmp_path):
    (tmp_path / "wiki").mkdir()
    assert keyword_search(tmp_path, "anything", 5) == []


# ── hybrid ───────────────────────────────────────────────────────────────────

def test_hybrid_falls_back_to_keyword_without_vectors(tmp_path):
    root = _make_indexed_wiki(tmp_path, embed=False)  # indexed, NOT embedded
    h = hybrid_search(root, "neural", 5)              # no embedder available
    k = keyword_search(root, "neural", 5)
    assert [r["path"] for r in h] == [r["path"] for r in k]  # byte-identical


def test_hybrid_fuses_when_vectors_present(tmp_path):
    root = _make_indexed_wiki(tmp_path, embed=True)
    h = hybrid_search(root, "neural", 5, embedder=_Fake())
    assert h
    assert all("path" in r for r in h)
    # results carry a provenance tag from the fusion
    assert all("matched" in r for r in h)


def test_hybrid_gibberish_with_floor_returns_empty(tmp_path):
    root = _make_indexed_wiki(tmp_path, embed=True)
    # no keyword hit + an impossible similarity floor → nothing survives
    res = hybrid_search(root, "zzzznonexistentqqq", 5, embedder=_Fake(), sim_floor=1.1)
    assert res == []


# ── CLI --set bm25 overrides on the default hybrid path (LWM_031) ────────────

def _make_tf_wiki(tmp_path):
    """3 pages: z.md has a huge tf for 'zebra'; k1=0 collapses the tf boost so
    the path tie-break flips the ranking (same fixture as the shared-BM25 test)."""
    w = tmp_path / "wiki"
    w.mkdir()
    (w / "a.md").write_text(
        "---\ntitle: Alpha\n---\n# Alpha\n\nzebra attention\n", encoding="utf-8")
    (w / "z.md").write_text(
        "---\ntitle: Zulu\n---\n# Zulu\n\n" + "zebra " * 10 + "attention\n",
        encoding="utf-8")
    (w / "m.md").write_text(
        "---\ntitle: Mike\n---\n# Mike\n\nzebra\n", encoding="utf-8")
    index_wiki(tmp_path, rebuild=True)
    return tmp_path


def _cli_search(monkeypatch, argv):
    from llm_wiki.search import query as query_mod
    monkeypatch.setattr(sys, "argv", ["llm-wiki search", *argv])
    return query_mod.main()


def test_hybrid_cli_set_bm25_override_reaches_rescorer(tmp_path, monkeypatch, capsys):
    """`llm-wiki search --set bm25.k1` (default hybrid path) must reach the
    hybrid rescorer exactly like `--keyword` does — not be silently ignored."""
    root = _make_tf_wiki(tmp_path)
    query = "zebra attention"

    # Baseline: default bm25 → z.md (huge tf) first; k1=0 flips to a.md.
    default = hybrid_search(root, query, 10)
    override = hybrid_search(root, query, 10, bm25_k1=0.0, bm25_b=0.75)
    assert [r["path"] for r in default] == ["wiki/z.md", "wiki/a.md", "wiki/m.md"]
    assert [r["path"] for r in override] == ["wiki/a.md", "wiki/z.md", "wiki/m.md"]

    code = _cli_search(monkeypatch, [str(root), query, "--set", "bm25.k1=0.0", "--json"])
    assert code == 0
    cli_tuned = json.loads(capsys.readouterr().out)
    assert [r["path"] for r in cli_tuned] == [r["path"] for r in override]

    code = _cli_search(monkeypatch, [str(root), query, "--json"])
    assert code == 0
    cli_default = json.loads(capsys.readouterr().out)
    assert [r["path"] for r in cli_default] == [r["path"] for r in default]
    assert cli_default != cli_tuned  # the override is effective, not ignored
