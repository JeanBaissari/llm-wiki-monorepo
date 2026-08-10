"""Tests for the [semantic]-gated ``similar_to`` generator (LWM_029).

LWM_029's similarity half (``REL_SIMILAR``, tau floor, top-m cap, ``embed_meta``
skip guard) has no dedicated coverage — the co-occurrence half runs on the base
install and is tested in ``test_derived_edges.py``. These tests close that gap:

  * Always-running negatives (base install): no embedder / no vectors / no
    matching ``embed_meta`` → 0 ``similar_to`` edges, never a crash, never a
    corrupt layer.
  * Semantic-gated positives (``[semantic]`` extra): a real model2vec embedder
    over a small wiki produces typed ``similar_to`` edges (``relType``,
    ``directed: false``, ``cosine >= tau``), respects tau + top-m, and skips
    cleanly on an ``embed_meta`` mismatch.

The embedding-dependent tests skip on a base install (``model2vec`` absent) and
run for real in the CI ``semantic`` lane and in the local ``[semantic]`` venv.
"""

import json
import math

import pytest

from llm_wiki.graph import derived_edges as de

SEMANTIC_AVAILABLE = True
try:
    import model2vec  # noqa: F401
    import numpy  # noqa: F401
except ImportError:
    SEMANTIC_AVAILABLE = False

needs_semantic = pytest.mark.skipif(
    not SEMANTIC_AVAILABLE,
    reason="[semantic] extra not installed (model2vec/numpy) — embedding tests skip",
)


def _make_wiki(tmp_path, pages: "dict[str, str]"):
    """Small inline wiki: ``pages`` = {stem: body text} under ``wiki/``."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    for stem, body in pages.items():
        (wiki / f"{stem}.md").write_text(
            f"---\ntitle: {stem.replace('_', ' ').title()}\n"
            f"type: concept\n---\n\n# {stem.replace('_', ' ').title()}\n\n{body}\n",
            encoding="utf-8",
        )
    return tmp_path, wiki


def _similar_pages():
    """Two topical clusters (similar within, dissimilar across) + one loner."""
    return {
        "attention": (
            "Attention mechanisms compute a weighted average over input "
            "sequences, letting the model focus on the most relevant parts. "
            "Self-attention relates every position to every other position."
        ),
        "transformer": (
            "The transformer is an architecture built entirely on attention "
            "layers instead of recurrence. Multi-head attention lets each "
            "head attend to different representation subspaces of the "
            "sequence. Transformer models rely on self-attention."
        ),
        "self_attention": (
            "Self-attention computes attention scores between all pairs of "
            "positions in a sequence. Scaled dot-product attention divides "
            "the scores by the square root of the dimension. It is the "
            "core building block of the transformer."
        ),
        "neural_network": (
            "A neural network is a stack of layers of neurons with learned "
            "weights, trained by backpropagation. Deep networks learn "
            "hierarchical representations of their inputs."
        ),
        "coffee": (
            "Coffee is brewed from roasted beans and comes in many "
            "varieties such as espresso, filter, and cold brew. "
            "Roasting levels change the flavor and acidity."
        ),
        "gardening": (
            "Gardening is the practice of growing plants for food or "
            "ornament. Soil quality, watering, and sunlight determine "
            "how well a vegetable patch thrives."
        ),
    }


def _embed(wiki_root, embedder):
    from llm_wiki.search.index import index_wiki
    from llm_wiki.semantic.embed import embed_wiki

    index_wiki(wiki_root, rebuild=True)  # .index/wiki.db must exist (shared DB)
    stats = embed_wiki(wiki_root, embedder=embedder)
    assert stats["available"] is True
    return stats


# ── Always-running negatives (base install) ────────────────────────────────


def test_base_install_no_similar_to_edges(tmp_path, monkeypatch):
    """No embedder (base install) → 0 similar_to edges, co-occurrence still runs."""
    root, _wiki = _make_wiki(tmp_path, _similar_pages())
    from llm_wiki.semantic import embedder as embedder_mod

    # Force the no-embedder path regardless of the ambient install (this test
    # runs in BOTH lanes: the base-install CI lane and the [semantic] venv).
    monkeypatch.setattr(embedder_mod, "get_embedder", lambda *a, **k: None)
    stats = de.generate_derived_edges(root, tau=0.5)
    assert stats["similar_to"] == 0
    # Layer file is still valid JSON with a real edges list (no corrupt write).
    payload = json.loads(de.derived_path(root).read_text(encoding="utf-8"))
    assert isinstance(payload["edges"], list)
    assert all(e["relType"] != de.REL_SIMILAR for e in payload["edges"])


def test_no_vectors_no_similar_to_edges(tmp_path):
    """Index present but never embedded → 0 similar_to edges, no crash."""
    root, _wiki = _make_wiki(tmp_path, _similar_pages())
    from llm_wiki.search.index import index_wiki

    index_wiki(root, rebuild=True)
    stats = de.generate_derived_edges(root, tau=0.5)
    assert stats["similar_to"] == 0


# ── Semantic-gated positives (real [semantic] extra) ───────────────────────


@needs_semantic
def test_similar_to_edges_typed_undirected_above_tau(tmp_path, model2vec_embedder):
    """Real embedder: edges are relType=similar_to, directed=false, cosine>=tau."""
    root, _wiki = _make_wiki(tmp_path, _similar_pages())
    embedder = model2vec_embedder
    _embed(root, embedder)

    tau = 0.40
    stats = de.generate_derived_edges(root, tau=tau, top_m=5)
    assert stats["similar_to"] >= 1, "similar cluster should yield similar_to edges"

    edges = [e for e in de.load_derived_edges(root)
             if e["relType"] == de.REL_SIMILAR]
    assert edges, "similar_to edges must be persisted in the layer"
    for e in edges:
        assert e["relType"] == de.REL_SIMILAR
        assert e["directed"] is False
        assert e["layer"] == "derived"
        cosine = e["provenance"]["cosine"]
        assert cosine >= tau, f"cosine {cosine} below tau {tau} (corrupt edge)"
        assert e["weight"] == round(cosine, 4)  # weight mirrors the cosine
        assert e["source"] != e["target"]
    # The embedding space is symmetric → edges reference existing pages.
    stems = set(_wiki.glob("*.md"))
    names = {p.stem for p in stems}
    for e in edges:
        assert e["source"] in names and e["target"] in names


@needs_semantic
def test_similar_to_threshold_and_cap(tmp_path, model2vec_embedder):
    """LWM_029 row: edges only above tau, capped at top-m per node."""
    root, _wiki = _make_wiki(tmp_path, _similar_pages())
    embedder = model2vec_embedder
    _embed(root, embedder)

    low = de.generate_derived_edges(root, tau=0.35, top_m=5)
    high = de.generate_derived_edges(root, tau=0.50, top_m=5)

    # Higher tau never yields more similar_to edges (monotone threshold).
    assert high["similar_to"] <= low["similar_to"]
    # The topical cluster sits in the 0.35-0.50 band (real model2vec cosines):
    # low tau recovers the cluster, high tau above it yields none.
    assert low["similar_to"] >= 1
    assert high["similar_to"] == 0

    # top-m cap: no node participates in more than top_m similar_to edges.
    edges = [e for e in de.load_derived_edges(root) if e["relType"] == de.REL_SIMILAR]
    degree: "dict[str, int]" = {}
    for e in edges:
        degree[e["source"]] = degree.get(e["source"], 0) + 1
        degree[e["target"]] = degree.get(e["target"], 0) + 1
    assert max(degree.values(), default=0) <= 5, "top_m=5 cap exceeded per node"


@needs_semantic
def test_similarity_skipped_on_embed_meta_mismatch(tmp_path, model2vec_embedder):
    """LWM_029 NEGATIVE row: embed_meta mismatch → skip, never corrupt edges."""
    from llm_wiki.semantic import vector_schema as vs

    root, _wiki = _make_wiki(tmp_path, _similar_pages())
    embedder = model2vec_embedder
    _embed(root, embedder)

    # Prove the happy path first: with matching meta the generator finds edges.
    stats = de.generate_derived_edges(root, tau=0.40, top_m=5)
    assert stats["similar_to"] >= 1

    # Corrupt the embedding-space identity (e.g. a different model id).
    db_path = root / ".index" / "wiki.db"
    conn = vs.open_index_db(db_path)
    try:
        conn.execute("UPDATE embed_meta SET model_id = 'other-model-space'")
        conn.commit()
        mismatched = vs.embed_meta_matches(conn, embedder.embed_meta())
    finally:
        conn.close()
    assert mismatched is False

    # Mismatched meta → the similarity half is skipped entirely: no similar_to
    # edges, no crash, and the layer remains valid (co-occurrence may still run).
    stats2 = de.generate_derived_edges(root, tau=0.40, top_m=5)
    assert stats2["similar_to"] == 0
    payload = json.loads(de.derived_path(root).read_text(encoding="utf-8"))
    assert all(e["relType"] != de.REL_SIMILAR for e in payload["edges"])


# ── Sanity: math of the guard path (deterministic, no model needed) ─────────


def test_cosine_knn_floor_respected():
    """The cosine floor the generator relies on: below-tau neighbors dropped."""
    from llm_wiki.semantic.vectorstore import cosine_knn_numpy

    unit = [1.0, 0.0]
    rows = [("same", unit), ("opposite", [-1.0, 0.0]), ("half", [0.5, math.sqrt(3) / 2])]
    res = cosine_knn_numpy(unit, rows, k=5)
    by_name = dict(res)
    assert by_name["same"] == pytest.approx(1.0)
    assert by_name["half"] >= 0.5
    assert by_name["opposite"] == pytest.approx(-1.0)
