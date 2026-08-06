#!/usr/bin/env python3
"""vectorstore.py — Vector retrieval adapter: sqlite-vec vec0 path + numpy KNN.

Single retrieval surface over the additive vector schema (LWM_014): a fast
``vec0`` KNN when the ``sqlite-vec`` extension loads, and a mandatory pure-numpy
cosine scan over the ``page_vectors`` float32 blob table when it does not. The
router is fail-open — it never emits a ``vec0`` query on a backend that cannot
load the extension, so it never raises ``no such module: vec0`` (LWM_017).

See ADR-0016 §fallback for the substrate + routing decision.

Import-safe without the ``[semantic]`` extra: numpy is imported lazily inside
the KNN functions (mirroring embedder.py), and a pure-python cosine covers the
case where numpy is somehow absent. ``knn`` degrades to an empty result rather
than raising when no vectors are present or reachable.
"""

from __future__ import annotations

import sqlite3
from typing import Iterable, Optional, Sequence, Tuple

from llm_wiki.semantic.embedder import Embedder
from llm_wiki.semantic.vector_schema import (
    embed_meta_matches,
    get_vectors,
    iter_vectors,
    pack_vector,
    try_load_sqlite_vec,
    vec0_count,
    vector_count,
)

Neighbor = Tuple[str, float]


# ── L2 normalization (numpy when present, pure-python otherwise) ─────────────

def _l2_normalize(vec: Sequence[float]) -> "list[float]":
    """Return an L2-normalized copy of ``vec``. A zero vector is returned as-is."""
    try:
        import numpy as np
    except ImportError:
        import math

        norm = math.sqrt(sum(float(x) * float(x) for x in vec))
        if norm == 0.0:
            return [float(x) for x in vec]
        return [float(x) / norm for x in vec]

    arr = np.asarray(vec, dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    if norm == 0.0:
        return [float(x) for x in vec]
    return (arr / norm).astype(np.float32).tolist()


# ── pure-python fallback (only when numpy is unavailable) ────────────────────

def _cosine_knn_python(
    query_vec: Sequence[float], rows: Iterable[Tuple[str, Sequence[float]]], k: int
) -> "list[Neighbor]":
    q = _l2_normalize(query_vec)
    dim = len(q)
    scored: "list[Neighbor]" = []
    for rel_path, vec in rows:
        if len(vec) != dim:  # dim mismatch / corrupt blob → skip this row
            continue
        scored.append((rel_path, sum(a * b for a, b in zip(q, vec))))
    scored.sort(key=lambda t: (-t[1], t[0]))
    return scored[:k]


# ── numpy cosine KNN (the always-available fallback path) ────────────────────

def cosine_knn_numpy(
    query_vec: Sequence[float],
    rows: Iterable[Tuple[str, Sequence[float]]],
    k: int,
) -> "list[Neighbor]":
    """Cosine top-k over ``rows`` (an iterable of ``(rel_path, vec)``).

    Stored vectors are assumed L2-normalized (the embedder normalizes); the
    query is L2-normalized defensively so cosine similarity is a plain dot
    product ``M @ q``. Deterministic tie-break by ``(-score, rel_path)``.

    Selection uses ``np.partition`` (O(N)) to find the k-th score, then keeps
    every row at or above that threshold — so boundary ties are all considered
    and the tie-break is exact rather than dependent on partition order.
    """
    rows = list(rows)
    if k <= 0 or not rows:
        return []

    try:
        import numpy as np
    except ImportError:
        return _cosine_knn_python(query_vec, rows, k)

    q = np.asarray(query_vec, dtype=np.float32)
    qn = float(np.linalg.norm(q))
    if qn != 0.0:
        q = q / qn
    dim = int(q.shape[0])

    paths: "list[str]" = []
    mats: "list" = []
    for rel_path, vec in rows:
        v = np.asarray(vec, dtype=np.float32)
        if v.shape[0] != dim:  # dim mismatch / corrupt blob → skip this row
            continue
        paths.append(rel_path)
        mats.append(v)
    if not paths:
        return []

    matrix = np.vstack(mats)          # (N, dim), stored vectors already L2-normalized
    scores = matrix @ q               # (N,) cosine similarities
    n = len(paths)
    kk = min(k, n)

    # k-th largest score via O(N) partition; include all rows tying it so the
    # deterministic (-score, rel_path) sort below decides the boundary.
    threshold = float(np.partition(scores, n - kk)[n - kk])
    cand = np.nonzero(scores >= threshold)[0]

    selected = [(paths[i], float(scores[i])) for i in cand]
    selected.sort(key=lambda t: (-t[1], t[0]))
    return selected[:kk]


# ── vec0 capability + KNN path ───────────────────────────────────────────────

def vec0_available(conn: sqlite3.Connection) -> bool:
    """True iff sqlite-vec loads, a ``vec_pages`` table exists, AND it is populated.

    The non-empty requirement is deliberate: an empty vec0 table (created but not
    yet populated) must NOT capture routing — an empty MATCH result is not an
    exception, so routing to it would silently return no neighbors while real
    vectors sit in ``page_vectors``. Never raises; any failure returns False so
    the caller uses the numpy fallback.
    """
    if not try_load_sqlite_vec(conn):
        return False
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='vec_pages'"
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    if row is None:
        return False
    return vec0_count(conn) > 0


def _knn_vec0(conn: sqlite3.Connection, query_vec: Sequence[float], k: int) -> "list[Neighbor]":
    """vec0 as an exact prefilter + numpy rerank → identical top-k to numpy.

    sqlite-vec's vec0 KNN is exact (brute force), so the ``over``-sized candidate
    window ordered by distance contains the true top-k and all rows tying the
    k-th score (for any realistic window). We then fetch those candidates' exact
    vectors from ``page_vectors`` and select with ``cosine_knn_numpy`` — the SAME
    threshold + ``(-score, rel_path)`` tie-break as the pure-numpy path — so the
    two backends return byte-identical results including score ties.
    """
    q = _l2_normalize(query_vec)
    blob = pack_vector(q)
    over = max(k * 4, k + 64)
    cur = conn.execute(
        "SELECT rel_path FROM vec_pages WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
        (blob, int(over)),
    )
    cand = [r[0] for r in cur]
    if not cand:
        return []
    rows = get_vectors(conn, cand)
    return cosine_knn_numpy(q, rows, k)


def knn(conn: sqlite3.Connection, query_vec: Sequence[float], k: int) -> "list[Neighbor]":
    """Return the k nearest pages as ``(rel_path, cosine_similarity)`` desc.

    Routes to the ``vec0`` prefilter+rerank when ``sqlite-vec`` loads and
    ``vec_pages`` is populated; otherwise scans the ``page_vectors`` blob table
    with ``cosine_knn_numpy``. Never raises on a missing extension/table, and
    falls through to the numpy scan if the vec0 path yields nothing while blob
    vectors exist (LWM_017 / ADR-0016).
    """
    if k <= 0:
        return []
    if vec0_available(conn):
        try:
            res = _knn_vec0(conn, query_vec, k)
            if res:
                return res
        except Exception:
            pass  # fail-open: fall through to the numpy blob scan
    return cosine_knn_numpy(query_vec, iter_vectors(conn), k)


# ── single semantic retrieval entry point ────────────────────────────────────

def semantic_retrieve(
    conn: sqlite3.Connection,
    embedder: Optional[Embedder],
    query: str,
    k: int,
) -> Optional["list[Neighbor]"]:
    """Embed ``query`` and return KNN neighbors, or ``None`` for keyword fallback.

    Returns ``None`` (caller uses keyword search) when the embedder is absent,
    no vectors are persisted, or the stored ``embed_meta`` is incompatible with
    the embedder's space (LWM_013 invariant #5). Otherwise embeds the query and
    routes through ``knn``.
    """
    if embedder is None:
        return None
    if vector_count(conn) == 0:
        return None
    if not embed_meta_matches(conn, embedder.embed_meta()):
        return None
    vecs = embedder.embed([query])
    if not vecs:
        return None
    return knn(conn, vecs[0], k)
