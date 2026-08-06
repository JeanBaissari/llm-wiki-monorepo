#!/usr/bin/env python3
"""vector_schema.py — Additive vector storage in the existing .index/wiki.db.

Adds two tables to the same SQLite file the FTS5 index already uses, WITHOUT
touching the FTS5 tables (``pages`` / ``index_meta`` / ``index_stats``) — so
keyword search stays byte-identical by construction (LWM_013 invariant #2):

  * ``page_vectors`` — the always-present fallback store: one row per page with
    the embedding as a raw little-endian float32 BLOB (numpy/sqlite-vec
    compatible). A pure-numpy KNN works over this with zero native extension
    (LWM_017 / ADR-0016).
  * ``embed_meta`` — the single-row guard (model id+revision, dimension,
    normalization, quantization, build id, schema version). Every vector reader
    asserts it and falls back to keyword on mismatch (LWM_013 invariant #5).

An optional ``vec_pages`` vec0 virtual table is created only when the sqlite-vec
extension actually loads (best-effort; the adapter in LWM_017 owns KNN and
decides which path to use). This module is stdlib-only (sqlite3 + struct) so it
always imports and runs regardless of the ``[semantic]`` extra.

Schema is purely additive (``CREATE ... IF NOT EXISTS``): no migration of
existing FTS5 data is required. See LWM_014 / ADR-0018.
"""

from __future__ import annotations

import sqlite3
import struct
from pathlib import Path
from typing import Iterator, Optional

from llm_wiki.semantic.embedder import EmbedMeta

VECTOR_SCHEMA_VERSION = 1


# ── float32 blob (numpy '<f4' / sqlite-vec compatible) ──────────────────────

def pack_vector(vec: "list[float]") -> bytes:
    return struct.pack(f"<{len(vec)}f", *vec)


def unpack_vector(blob: bytes) -> "list[float]":
    n = len(blob) // 4
    return list(struct.unpack(f"<{n}f", blob))


# ── extension probing (never raises) ────────────────────────────────────────

def can_load_extensions(conn: sqlite3.Connection) -> bool:
    """True iff this Python's sqlite3 build exposes extension loading."""
    return hasattr(conn, "enable_load_extension")


def try_load_sqlite_vec(conn: sqlite3.Connection) -> bool:
    """Best-effort load of the sqlite-vec extension. Returns True on success.

    Never raises: on a build with extension loading disabled, a missing
    ``sqlite_vec`` package, or any load error, returns False so the caller uses
    the numpy-blob fallback (or keyword-only).
    """
    if not hasattr(conn, "enable_load_extension"):
        return False
    try:
        conn.enable_load_extension(True)
    except (AttributeError, sqlite3.OperationalError):
        return False
    try:
        import sqlite_vec  # type: ignore

        sqlite_vec.load(conn)
        loaded = True
    except Exception:
        loaded = False
    finally:
        try:
            conn.enable_load_extension(False)
        except Exception:
            pass
    return loaded


# ── schema ──────────────────────────────────────────────────────────────────

def init_vector_schema(
    conn: sqlite3.Connection, dim: Optional[int] = None, *, with_vec0: bool = False
) -> None:
    """Create the additive vector tables. FTS5 tables are never touched."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS page_vectors (
            rel_path   TEXT PRIMARY KEY,
            sha256     TEXT NOT NULL,
            dim        INTEGER NOT NULL,
            vector     BLOB NOT NULL,
            indexed_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS embed_meta (
            id             INTEGER PRIMARY KEY CHECK (id = 1),
            model_id       TEXT NOT NULL,
            revision       TEXT NOT NULL,
            dimension      INTEGER NOT NULL,
            normalization  TEXT NOT NULL,
            quantization   TEXT NOT NULL,
            build_id       TEXT NOT NULL,
            schema_version INTEGER NOT NULL
        )
        """
    )
    if with_vec0 and dim:
        # Only reached when the caller has confirmed sqlite-vec is loaded.
        conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_pages "
            f"USING vec0(rel_path TEXT PRIMARY KEY, embedding float[{int(dim)}])"
        )
    conn.commit()


# ── embed_meta guard ────────────────────────────────────────────────────────

def write_embed_meta(conn: sqlite3.Connection, meta: EmbedMeta) -> None:
    conn.execute("DELETE FROM embed_meta")
    conn.execute(
        "INSERT INTO embed_meta "
        "(id, model_id, revision, dimension, normalization, quantization, build_id, schema_version) "
        "VALUES (1, ?, ?, ?, ?, ?, ?, ?)",
        (
            meta.model_id,
            meta.revision,
            meta.dimension,
            meta.normalization,
            meta.quantization,
            meta.build_id,
            VECTOR_SCHEMA_VERSION,
        ),
    )
    conn.commit()


def read_embed_meta(conn: sqlite3.Connection) -> Optional[EmbedMeta]:
    try:
        row = conn.execute(
            "SELECT model_id, revision, dimension, normalization, quantization, build_id "
            "FROM embed_meta WHERE id = 1"
        ).fetchone()
    except sqlite3.OperationalError:
        return None  # table absent → treat as no meta
    if not row:
        return None
    return EmbedMeta(*row)


def embed_meta_matches(conn: sqlite3.Connection, meta: EmbedMeta) -> bool:
    """True iff stored vectors were produced by a compatible embedding space.

    Ignores ``build_id`` (a rebuild marker); compares the identity that makes
    KNN results meaningful: model+revision, dimension, normalization,
    quantization. A False here forces the caller to keyword-only.
    """
    stored = read_embed_meta(conn)
    if stored is None:
        return False
    return (
        stored.model_id == meta.model_id
        and stored.revision == meta.revision
        and stored.dimension == meta.dimension
        and stored.normalization == meta.normalization
        and stored.quantization == meta.quantization
    )


# ── vector rows (fallback store) ────────────────────────────────────────────

def store_vector(
    conn: sqlite3.Connection,
    rel_path: str,
    sha256: str,
    vec: "list[float]",
    indexed_at: str,
) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO page_vectors (rel_path, sha256, dim, vector, indexed_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (rel_path, sha256, len(vec), pack_vector(vec), indexed_at),
    )


def delete_vector(conn: sqlite3.Connection, rel_path: str) -> None:
    conn.execute("DELETE FROM page_vectors WHERE rel_path = ?", (rel_path,))


def vector_sha256(conn: sqlite3.Connection, rel_path: str) -> Optional[str]:
    try:
        row = conn.execute(
            "SELECT sha256 FROM page_vectors WHERE rel_path = ?", (rel_path,)
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    return row[0] if row else None


def iter_vectors(conn: sqlite3.Connection) -> Iterator["tuple[str, list[float]]"]:
    try:
        cur = conn.execute("SELECT rel_path, vector FROM page_vectors")
    except sqlite3.OperationalError:
        return
    for rel_path, blob in cur:
        yield rel_path, unpack_vector(blob)


def vector_count(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT COUNT(*) FROM page_vectors").fetchone()
    except sqlite3.OperationalError:
        return 0
    return row[0] if row else 0


def open_index_db(db_path: str | Path) -> sqlite3.Connection:
    """Open the shared .index/wiki.db with the same pragmas the indexer uses."""
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn
