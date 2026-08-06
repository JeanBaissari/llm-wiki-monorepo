"""Tests for the semantic link-suggestion engine (LWM_021).

Covers: Personalized PageRank, the wikilink stem graph, the fused
``semantic_related`` entry point (with and without the [semantic] embedding
path), and the ADR-0021 auto-apply guard.
"""

import hashlib
import math
from pathlib import Path

import pytest

from llm_wiki.search.index import index_wiki
from llm_wiki.semantic.embed import embed_wiki
from llm_wiki.semantic.embedder import Embedder
from llm_wiki.semantic.linking import (
    build_stem_graph,
    is_auto_appliable,
    personalized_pagerank,
    semantic_related,
)


# ── deterministic fake embedder (mirrors tests/test_search_hybrid.py::_Fake) ──

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


# ── indexed (+ optionally embedded) tmp wiki with real wikilinks ──────────────

_PAGES = {
    "neural_network.md": (
        "Neural Network",
        "A neural network learns weights via [[Backpropagation]]. See [[Deep Learning]].",
    ),
    "deep_learning.md": (
        "Deep Learning",
        "Deep learning stacks many [[Neural Network]] layers, trained by [[Backpropagation]].",
    ),
    "backpropagation.md": (
        "Backpropagation",
        "Backpropagation is how a [[Neural Network]] updates its weights.",
    ),
    "transformer.md": (
        "Transformer",
        "The transformer applies [[Attention]] across a sequence.",
    ),
    "attention.md": (
        "Attention",
        "Attention lets a [[Transformer]] weigh tokens.",
    ),
    "coffee.md": (
        "Coffee",
        "Coffee is a brewed beverage from roasted beans.",
    ),
}


def _make_wiki(tmp_path, embed=False):
    w = tmp_path / "wiki"
    w.mkdir()
    for nm, (title, body) in _PAGES.items():
        (w / nm).write_text(
            f"---\ntitle: {title}\ntype: concept\n---\n\n# {title}\n\n{body}\n",
            encoding="utf-8",
        )
    index_wiki(tmp_path, rebuild=True)
    if embed:
        embed_wiki(tmp_path, embedder=_Fake())
    return tmp_path


# ── Personalized PageRank ─────────────────────────────────────────────────────

_PPR_ADJ = {
    "seed": {"a", "b"},
    "a": {"seed", "c"},
    "b": {"seed"},
    "c": {"a"},  # 2 hops from seed
}


def test_ppr_seed_highest_and_neighbors_outrank_distant():
    ppr = personalized_pagerank(_PPR_ADJ, "seed")
    # seed retains the most mass
    assert ppr["seed"] == max(ppr.values())
    # direct neighbors (a, b) outrank the distant node (c)
    assert ppr["a"] > ppr["c"]
    assert ppr["b"] > ppr["c"]
    # mass is conserved
    assert sum(ppr.values()) == pytest.approx(1.0)


def test_ppr_isolated_seed_keeps_all_mass():
    ppr = personalized_pagerank({"lonely": set(), "x": {"y"}, "y": {"x"}}, "lonely")
    assert ppr["lonely"] == pytest.approx(1.0)
    assert ppr["x"] == pytest.approx(0.0)
    assert ppr["y"] == pytest.approx(0.0)


def test_ppr_unknown_seed_is_empty():
    assert personalized_pagerank({"a": {"b"}, "b": {"a"}}, "zzz") == {}


def test_ppr_empty_graph_is_empty():
    assert personalized_pagerank({}, "seed") == {}


def test_ppr_deterministic():
    assert personalized_pagerank(_PPR_ADJ, "seed") == personalized_pagerank(_PPR_ADJ, "seed")


# ── wikilink stem graph ───────────────────────────────────────────────────────

def test_build_stem_graph_resolves_undirected_no_self_loops():
    pages = {
        "neural_network": (
            Path("neural_network.md"),
            "Links to [[Deep Learning]] and [[Backpropagation]].",
            {"title": "Neural Network"},
        ),
        "deep_learning": (
            Path("deep_learning.md"),
            "Links back to [[Neural Network]].",
            {"title": "Deep Learning"},
        ),
        "backpropagation": (
            Path("backpropagation.md"),
            "Self [[Backpropagation]], stem link [[neural_network]], and [[Nonexistent Page]].",
            {"title": "Backpropagation"},
        ),
    }
    g = build_stem_graph(pages)

    # link text resolved to stems (via title AND lowercase-stem maps)
    assert "deep_learning" in g["neural_network"]
    assert "backpropagation" in g["neural_network"]
    assert "neural_network" in g["backpropagation"]  # resolved from [[neural_network]]

    # undirected: the reverse edge exists even though deep_learning only linked one way
    assert "neural_network" in g["deep_learning"]

    # self-links are skipped
    assert "backpropagation" not in g["backpropagation"]

    # unresolved links contribute no node/edge
    assert all("nonexistent" not in n for nbrs in g.values() for n in nbrs)


# ── semantic_related (fused) ──────────────────────────────────────────────────

def test_semantic_related_with_embedder(tmp_path):
    root = _make_wiki(tmp_path, embed=True)
    res = semantic_related(root, "neural_network", k=5, embedder=_Fake())

    assert res
    valid = {"embedding", "ppr", "lexical"}
    for r in res:
        # never suggests the source page back to itself
        assert r["target_stem"] != "neural_network"
        assert set(r.keys()) == {"target_stem", "rank", "score", "signals"}
        assert r["signals"]  # every row is backed by at least one signal
        assert set(r["signals"]) <= valid

    # ranks are contiguous and 1-based
    assert [r["rank"] for r in res] == list(range(1, len(res) + 1))

    # both the graph (ppr) and vector (embedding) signals fire on this fixture
    assert any("ppr" in r["signals"] for r in res)
    assert any("embedding" in r["signals"] for r in res)

    # wikilink neighbors surface as related notes
    stems = {r["target_stem"] for r in res}
    assert {"backpropagation", "deep_learning"} & stems

    # deterministic across repeated runs
    assert res == semantic_related(root, "neural_network", k=5, embedder=_Fake())


def test_semantic_related_without_embedder_degrades(tmp_path):
    # No embedding path at all (mirrors a base install without the [semantic] extra).
    root = _make_wiki(tmp_path, embed=False)
    res = semantic_related(root, "neural_network", k=5, embedder=None)

    assert res  # lexical + PPR still produce results
    for r in res:
        assert "embedding" not in r["signals"]  # embedding signal absent
        assert r["signals"]  # backed by ppr/lexical only
        assert set(r["signals"]) <= {"ppr", "lexical"}

    stems = {r["target_stem"] for r in res}
    assert {"backpropagation", "deep_learning"} & stems


def test_semantic_related_unknown_source_is_empty(tmp_path):
    root = _make_wiki(tmp_path, embed=False)
    assert semantic_related(root, "does_not_exist", k=5, embedder=None) == []


# ── ADR-0021 auto-apply guard ─────────────────────────────────────────────────

def test_is_auto_appliable_requires_non_static_signal():
    assert is_auto_appliable({"signals": ["lexical"]}) is True
    assert is_auto_appliable({"signals": ["ppr"]}) is True
    assert is_auto_appliable({"signals": ["embedding", "ppr"]}) is True
    assert is_auto_appliable({"signals": ["embedding", "lexical"]}) is True
    # embedding-only (static similarity) is suggest-only — never auto-applied
    assert is_auto_appliable({"signals": ["embedding"]}) is False
    assert is_auto_appliable({"signals": []}) is False
    assert is_auto_appliable({}) is False
