"""Tests for the additive vector schema (LWM_014 / ADR-0018).

Proves the schema coexists with FTS5 without touching it, the embed_meta guard
compares the right fields, and float32 blobs round-trip. Stdlib-only.
"""

import sqlite3

from llm_wiki.search.index import init_schema  # existing FTS5 schema
from llm_wiki.semantic.embedder import EmbedMeta
from llm_wiki.semantic.vector_schema import (
    embed_meta_matches,
    init_vector_schema,
    iter_vectors,
    pack_vector,
    read_embed_meta,
    store_vector,
    delete_vector,
    try_load_sqlite_vec,
    unpack_vector,
    vector_count,
    vector_sha256,
    write_embed_meta,
)


def _meta(dim=8, model="m", norm="l2", quant="float32"):
    return EmbedMeta(model, "r1", dim, norm, quant, "build-1")


def test_vector_schema_is_additive_to_fts5():
    conn = sqlite3.connect(":memory:")
    init_schema(conn)  # creates pages / index_meta / index_stats
    conn.execute("INSERT INTO pages (path, title, content) VALUES ('a.md','A','alpha beta')")
    conn.commit()

    init_vector_schema(conn, dim=8)  # additive

    # FTS5 content is untouched and still queryable.
    row = conn.execute("SELECT path, title FROM pages WHERE pages MATCH 'alpha'").fetchone()
    assert row == ("a.md", "A")
    # New tables exist alongside.
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"pages", "index_meta", "page_vectors", "embed_meta"} <= tables


def test_blob_roundtrip_is_float32():
    vec = [0.1, -0.2, 0.333333, 1.0]
    out = unpack_vector(pack_vector(vec))
    assert len(out) == 4
    # float32 precision tolerance
    assert all(abs(a - b) < 1e-6 for a, b in zip(out, vec))


def test_embed_meta_roundtrip_and_guard():
    conn = sqlite3.connect(":memory:")
    init_vector_schema(conn, dim=8)
    assert read_embed_meta(conn) is None
    assert embed_meta_matches(conn, _meta()) is False  # nothing stored yet

    write_embed_meta(conn, _meta(dim=8, model="m"))
    stored = read_embed_meta(conn)
    assert stored is not None and stored.dimension == 8

    assert embed_meta_matches(conn, _meta(dim=8, model="m")) is True
    # A different dimension / model / normalization must fail the guard.
    assert embed_meta_matches(conn, _meta(dim=16, model="m")) is False
    assert embed_meta_matches(conn, _meta(dim=8, model="other")) is False
    assert embed_meta_matches(conn, _meta(dim=8, model="m", norm="none")) is False


def test_embed_meta_is_single_row():
    conn = sqlite3.connect(":memory:")
    init_vector_schema(conn, dim=8)
    write_embed_meta(conn, _meta(model="first"))
    write_embed_meta(conn, _meta(model="second"))
    n = conn.execute("SELECT COUNT(*) FROM embed_meta").fetchone()[0]
    assert n == 1
    assert read_embed_meta(conn).model_id == "second"


def test_store_iter_delete_vectors_and_freshness():
    conn = sqlite3.connect(":memory:")
    init_vector_schema(conn, dim=4)
    store_vector(conn, "entities/a.md", "hash-a", [1.0, 0.0, 0.0, 0.0], "2026-08-06T00:00:00")
    store_vector(conn, "concepts/b.md", "hash-b", [0.0, 1.0, 0.0, 0.0], "2026-08-06T00:00:00")
    conn.commit()

    assert vector_count(conn) == 2
    assert vector_sha256(conn, "entities/a.md") == "hash-a"
    got = dict(iter_vectors(conn))
    assert set(got) == {"entities/a.md", "concepts/b.md"}
    assert abs(got["entities/a.md"][0] - 1.0) < 1e-6

    delete_vector(conn, "entities/a.md")
    conn.commit()
    assert vector_count(conn) == 1
    assert vector_sha256(conn, "entities/a.md") is None


def test_helpers_never_raise_on_missing_tables():
    # A bare DB with no vector schema: readers degrade quietly (keyword fallback).
    conn = sqlite3.connect(":memory:")
    assert read_embed_meta(conn) is None
    assert embed_meta_matches(conn, _meta()) is False
    assert list(iter_vectors(conn)) == []
    assert vector_count(conn) == 0
    assert vector_sha256(conn, "x.md") is None


def test_try_load_sqlite_vec_returns_bool_without_raising():
    conn = sqlite3.connect(":memory:")
    # Whether or not sqlite-vec is installed / loadable, this must be a clean bool.
    assert isinstance(try_load_sqlite_vec(conn), bool)
