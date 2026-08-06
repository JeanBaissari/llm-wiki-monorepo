"""Tests for the vector retrieval adapter (LWM_017 / ADR-0016).

Covers the pure-numpy cosine KNN, the sqlite-vec ``vec0`` path, their parity on
identical data, the fail-open router (never raises ``no such module: vec0``),
the deterministic ``(-score, rel_path)`` tie-break, and the ``semantic_retrieve``
keyword-fallback contract. Runs with numpy + sqlite-vec installed.
"""

import math
import sqlite3

import pytest

from llm_wiki.semantic.embedder import Embedder, EmbedMeta
from llm_wiki.semantic import vectorstore
from llm_wiki.semantic.vectorstore import (
    cosine_knn_numpy,
    knn,
    semantic_retrieve,
    vec0_available,
)
from llm_wiki.semantic.vector_schema import (
    init_vector_schema,
    pack_vector,
    store_vector,
    try_load_sqlite_vec,
    write_embed_meta,
)

_TS = "2026-08-06T00:00:00"


# ── helpers ──────────────────────────────────────────────────────────────────

def _norm(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _sqlite_vec_loads() -> bool:
    return try_load_sqlite_vec(sqlite3.connect(":memory:"))


requires_vec0 = pytest.mark.skipif(
    not _sqlite_vec_loads(), reason="sqlite-vec extension not loadable in this env"
)


def _seed(conn, dim, data, *, with_vec0=False):
    """Store already-normalized vectors into page_vectors (+ vec_pages if asked).

    ``data`` maps rel_path -> raw (un-normalized) vector; it is L2-normalized
    here to mirror the embedder writing normalized vectors.
    """
    if with_vec0:
        try_load_sqlite_vec(conn)
    init_vector_schema(conn, dim=dim, with_vec0=with_vec0)
    for rel_path, raw in data.items():
        vec = _norm(raw)
        store_vector(conn, rel_path, "sha-" + rel_path, vec, _TS)
        if with_vec0:
            conn.execute(
                "INSERT INTO vec_pages (rel_path, embedding) VALUES (?, ?)",
                (rel_path, pack_vector(vec)),
            )
    conn.commit()


class FakeEmbedder(Embedder):
    """Deterministic, dependency-free embedder for retrieval-routing tests."""

    model_id = "fake/model"
    revision = "r1"
    normalization = "l2"
    quantization = "float32"

    def __init__(self, dim, mapping=None):
        self._dim = dim
        self._mapping = mapping or {}

    @classmethod
    def is_available(cls):
        return True

    @property
    def dimension(self):
        return self._dim

    def embed(self, texts):
        out = []
        for t in texts:
            raw = self._mapping.get(t, [1.0] + [0.0] * (self._dim - 1))
            out.append(_norm(raw))
        return out


# ── cosine_knn_numpy: ordering ───────────────────────────────────────────────

def test_cosine_knn_numpy_orders_by_cosine():
    dim = 4
    rows = [
        ("far.md", _norm([0, 0, 0, 1])),      # cos 0.0 to query
        ("mid.md", _norm([1, 1, 0, 0])),      # cos ~0.707
        ("near.md", _norm([1, 0.1, 0, 0])),   # cos ~0.995
        ("exact.md", _norm([1, 0, 0, 0])),    # cos 1.0
    ]
    q = [1.0, 0.0, 0.0, 0.0]
    got = cosine_knn_numpy(q, rows, k=3)
    assert [p for p, _ in got] == ["exact.md", "near.md", "mid.md"]
    # scores are descending true cosines
    scores = [s for _, s in got]
    assert scores == sorted(scores, reverse=True)
    assert abs(scores[0] - 1.0) < 1e-6


def test_cosine_knn_numpy_normalizes_query_defensively():
    # An un-normalized query must not change the ranking (only its magnitude).
    dim = 3
    rows = [("a.md", _norm([1, 0, 0])), ("b.md", _norm([0, 1, 0]))]
    small = cosine_knn_numpy([1.0, 0.0, 0.0], rows, k=2)
    big = cosine_knn_numpy([9.0, 0.0, 0.0], rows, k=2)
    assert [p for p, _ in small] == [p for p, _ in big] == ["a.md", "b.md"]
    assert abs(small[0][1] - big[0][1]) < 1e-6  # identical cosine after normalization


def test_cosine_knn_numpy_k_and_empty_edges():
    rows = [("a.md", _norm([1, 0]))]
    assert cosine_knn_numpy([1.0, 0.0], rows, k=0) == []
    assert cosine_knn_numpy([1.0, 0.0], [], k=5) == []
    # k larger than N returns all rows.
    assert len(cosine_knn_numpy([1.0, 0.0], rows, k=5)) == 1


# ── deterministic tie-break ──────────────────────────────────────────────────

def test_deterministic_tie_break_by_relpath():
    dim = 4
    q = [1.0, 0.0, 0.0, 0.0]
    # Three rows tie at cosine 0.0; one clear winner at cosine 1.0.
    base_rows = [
        ("m_near.md", _norm([1, 0, 0, 0])),
        ("c_tie.md", _norm([0, 1, 0, 0])),
        ("a_tie.md", _norm([0, 1, 0, 0])),
        ("b_tie.md", _norm([0, 1, 0, 0])),
    ]
    expected = ["m_near.md", "a_tie.md", "b_tie.md"]  # ties broken by rel_path asc
    # Ordering must not depend on input row order.
    for rows in (base_rows, list(reversed(base_rows)), sorted(base_rows, key=lambda r: r[1][0])):
        got = cosine_knn_numpy(q, rows, k=3)
        assert [p for p, _ in got] == expected
    # c_tie.md is the excluded boundary tie.
    assert "c_tie.md" not in [p for p, _ in cosine_knn_numpy(q, base_rows, k=3)]


# ── vec0 path ↔ numpy path parity ────────────────────────────────────────────

@requires_vec0
def test_vec0_available_true_when_table_present():
    conn = sqlite3.connect(":memory:")
    _seed(conn, 3, {"a.md": [1, 0, 0]}, with_vec0=True)
    assert vec0_available(conn) is True


@requires_vec0
def test_vec0_available_false_when_table_absent():
    conn = sqlite3.connect(":memory:")
    _seed(conn, 3, {"a.md": [1, 0, 0]}, with_vec0=False)  # no vec_pages
    assert vec0_available(conn) is False


@requires_vec0
def test_vec0_and_numpy_paths_agree(monkeypatch):
    dim = 5
    data = {
        "p1.md": [0.9, 0.1, 0.0, 0.0, 0.0],
        "p2.md": [0.2, 0.9, 0.1, 0.0, 0.0],
        "p3.md": [0.0, 0.1, 0.9, 0.2, 0.0],
        "p4.md": [0.0, 0.0, 0.1, 0.9, 0.3],
        "p5.md": [0.1, 0.0, 0.0, 0.2, 0.95],
        "p6.md": [0.3, 0.3, 0.3, 0.3, 0.3],
    }
    q = _norm([0.8, 0.2, 0.1, 0.0, 0.0])

    conn = sqlite3.connect(":memory:")
    _seed(conn, dim, data, with_vec0=True)

    # Real backend: vec0 (extension loads + vec_pages exists).
    assert vec0_available(conn) is True
    vec0_out = knn(conn, q, k=4)

    # Forced numpy path: pretend the extension will not load.
    monkeypatch.setattr(vectorstore, "try_load_sqlite_vec", lambda conn: False)
    assert vec0_available(conn) is False
    numpy_out = knn(conn, q, k=4)

    assert [p for p, _ in vec0_out] == [p for p, _ in numpy_out]
    for (_, s_vec), (_, s_np) in zip(vec0_out, numpy_out):
        assert abs(s_vec - s_np) < 1e-4  # both compute true cosine


# ── router fail-open: never raises no-such-module ────────────────────────────

@requires_vec0
def test_knn_falls_back_to_numpy_when_vec0_table_absent():
    # Extension loads, but no vec_pages table → must use numpy, must not raise.
    dim = 3
    conn = sqlite3.connect(":memory:")
    _seed(conn, dim, {"a.md": [1, 0, 0], "b.md": [0, 1, 0]}, with_vec0=False)
    out = knn(conn, [1.0, 0.0, 0.0], k=2)
    assert [p for p, _ in out] == ["a.md", "b.md"]


def test_knn_never_raises_without_extension(monkeypatch):
    # Force the no-extension world: knn must degrade to numpy silently.
    monkeypatch.setattr(vectorstore, "try_load_sqlite_vec", lambda conn: False)
    conn = sqlite3.connect(":memory:")
    _seed(conn, 3, {"a.md": [1, 0, 0], "b.md": [0, 1, 0]}, with_vec0=False)
    out = knn(conn, [0.0, 1.0, 0.0], k=1)
    assert out[0][0] == "b.md"


def test_knn_on_bare_db_returns_empty():
    # No vector schema at all → no rows reachable → [] (caller uses keyword).
    conn = sqlite3.connect(":memory:")
    assert knn(conn, [1.0, 0.0, 0.0], k=3) == []


def test_knn_k_zero_returns_empty():
    conn = sqlite3.connect(":memory:")
    _seed(conn, 2, {"a.md": [1, 0]}, with_vec0=False)
    assert knn(conn, [1.0, 0.0], k=0) == []


# ── semantic_retrieve routing ────────────────────────────────────────────────

def test_semantic_retrieve_none_when_embedder_missing():
    conn = sqlite3.connect(":memory:")
    _seed(conn, 4, {"a.md": [1, 0, 0, 0]}, with_vec0=False)
    write_embed_meta(conn, EmbedMeta("fake/model", "r1", 4, "l2", "float32", ""))
    assert semantic_retrieve(conn, None, "anything", k=3) is None


def test_semantic_retrieve_none_when_no_vectors():
    conn = sqlite3.connect(":memory:")
    init_vector_schema(conn, dim=4)  # schema present, zero vectors
    write_embed_meta(conn, EmbedMeta("fake/model", "r1", 4, "l2", "float32", ""))
    emb = FakeEmbedder(dim=4)
    assert semantic_retrieve(conn, emb, "query", k=3) is None


def test_semantic_retrieve_none_when_embed_meta_mismatches():
    conn = sqlite3.connect(":memory:")
    _seed(conn, 8, {"a.md": [1] + [0] * 7}, with_vec0=False)
    # Stored space is dim 8; the embedder's space is dim 4 → guard fails.
    write_embed_meta(conn, EmbedMeta("fake/model", "r1", 8, "l2", "float32", ""))
    emb = FakeEmbedder(dim=4)
    assert semantic_retrieve(conn, emb, "query", k=3) is None


def test_semantic_retrieve_returns_neighbors_on_match():
    dim = 4
    conn = sqlite3.connect(":memory:")
    _seed(
        conn,
        dim,
        {
            "cat.md": [1, 0, 0, 0],
            "dog.md": [0, 1, 0, 0],
            "car.md": [0, 0, 1, 0],
        },
        with_vec0=False,
    )
    write_embed_meta(conn, EmbedMeta("fake/model", "r1", dim, "l2", "float32", ""))
    emb = FakeEmbedder(dim=dim, mapping={"feline": [0.9, 0.1, 0.0, 0.0]})
    out = semantic_retrieve(conn, emb, "feline", k=2)
    assert out is not None
    assert [p for p, _ in out] == ["cat.md", "dog.md"]
    assert abs(out[0][1] - 1.0) < 0.2  # nearest is strongly aligned with cat.md
