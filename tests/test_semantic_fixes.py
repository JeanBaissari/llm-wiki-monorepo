"""Regression tests for defects found by the lane-A correctness audit.

Each test encodes an auditor repro so the fix can't silently regress:
  #1 embed must populate vec_pages (dual-write) so vec0 retrieval isn't empty
  #2 vec0 and numpy KNN must agree on tied top-k
  #3 the baseline must not emit duplicate targets per source
"""

import hashlib
import math
import sqlite3
from pathlib import Path

import pytest

from llm_wiki.semantic import vector_schema as vs
from llm_wiki.semantic.embed import embed_wiki
from llm_wiki.semantic.embedder import Embedder
from llm_wiki.semantic.vectorstore import (
    cosine_knn_numpy,
    knn,
    semantic_retrieve,
    vec0_available,
)


def _sqlite_vec_loads() -> bool:
    c = sqlite3.connect(":memory:")
    try:
        return vs.try_load_sqlite_vec(c)
    finally:
        c.close()


sqlite_vec_only = pytest.mark.skipif(
    not _sqlite_vec_loads(), reason="sqlite-vec extension not loadable here"
)


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
        return 4

    def embed(self, texts):
        out = []
        for t in texts:
            hb = hashlib.sha256(t.encode()).digest()[:4]
            v = [b / 255.0 for b in hb]
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out


def _norm(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


@sqlite_vec_only
def test_embed_dual_writes_vec0_and_retrieval_is_nonempty(tmp_path):
    # Defect #1: on sqlite-vec machines the vec0 table must be POPULATED, and
    # retrieval must return real neighbors — not an empty result from an empty
    # vec0 table shadowing the populated blob store.
    w = tmp_path / "wiki"
    w.mkdir()
    for nm, body in {"a.md": "cats and dogs", "b.md": "graph theory", "c.md": "cats"}.items():
        (w / nm).write_text(f"---\ntitle: {nm[:-3]}\n---\n\n# {nm[:-3]}\n\n{body}\n")

    embed_wiki(tmp_path, embedder=_Fake())
    conn = vs.open_index_db(tmp_path / ".index" / "wiki.db")
    vs.try_load_sqlite_vec(conn)  # load so vec0 table is queryable on this conn
    assert vs.vec0_count(conn) == 3            # dual-write populated vec_pages
    assert vec0_available(conn) is True        # populated → routes to vec0
    res = semantic_retrieve(conn, _Fake(), "cats", 3)
    assert res is not None and len(res) == 3   # not empty
    conn.close()


@sqlite_vec_only
def test_vec0_and_numpy_agree_on_tied_topk(tmp_path):
    # Defect #2: with several rows tied at the k-th score, the vec0 path (exact
    # prefilter + numpy rerank) must return the SAME top-k as the pure-numpy scan.
    q = [1.0, 0.0]
    tied = _norm([0.7071, 0.7071])
    for order in (
        ["TOP", "a", "b", "c", "d", "e"],
        ["e", "d", "c", "b", "a", "TOP"],
        ["c", "TOP", "e", "a", "d", "b"],
    ):
        conn = vs.open_index_db(tmp_path / f"{'-'.join(order)}.db")
        vs.try_load_sqlite_vec(conn)
        vs.init_vector_schema(conn, dim=2, with_vec0=True)
        for name in order:
            v = _norm([1.0, 0.0]) if name == "TOP" else tied
            vs.store_vector(conn, name, "h", v, "t")
            vs.upsert_vec0(conn, name, v)
        conn.commit()
        vres = [p for p, _ in knn(conn, q, 3)]
        nres = [p for p, _ in cosine_knn_numpy(q, list(vs.iter_vectors(conn)), 3)]
        assert vres == nres, f"vec0 {vres} != numpy {nres} for order {order}"
        conn.close()


def test_baseline_predictions_have_no_duplicate_targets():
    # Defect #3: predictions_for must dedupe targets per source so duplicates
    # don't inflate precision / crowd out relevant items in the baseline.
    from llm_wiki.eval.baseline import predictions_for

    fixture = Path("tests/fixtures/wikis/populated")
    if not fixture.is_dir():
        pytest.skip("populated fixture not present")
    preds = predictions_for(fixture)
    for source, targets in preds.items():
        assert len(targets) == len(set(targets)), f"duplicate targets for {source}"
