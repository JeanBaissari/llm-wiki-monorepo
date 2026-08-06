#!/usr/bin/env python3
"""embed.py — Batch-embed wiki pages into the vector store (LWM_016).

``llm-wiki embed`` computes one embedding per page and stores it in the shared
``.index/wiki.db`` (LWM_014), reusing SHA256 freshness so only changed pages
re-embed (mirrors the FTS5 indexer). Requires the optional ``[semantic]`` extra;
without it this is a **no-op** and keyword search is unaffected (LWM_013
invariant #2/#3).

The store and the FTS5 index share one file but distinct tables, so embedding
never alters keyword-search behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Optional

from llm_wiki.core.layout import discover_layout
from llm_wiki.search.index import (
    DB_FILENAME,
    FRONTMATTER_RE,
    INDEX_DIR_NAME,
    extract_title,
)
from llm_wiki.semantic import vector_schema as vs
from llm_wiki.semantic.embedder import Embedder, get_embedder


def _page_text(path: Path) -> str:
    """Title + body (frontmatter stripped) — the text we embed per page."""
    content = path.read_text(encoding="utf-8", errors="replace")
    title = extract_title(content, path)
    body = FRONTMATTER_RE.sub("", content, count=1)
    return f"{title}\n{body}".strip()


def embed_wiki(
    wiki_root, rebuild: bool = False, embedder: Optional[Embedder] = None
) -> dict:
    """Embed all pages into the vector store. No-op when no embedder is available.

    ``embedder`` may be injected (used by tests); otherwise the default from
    ``get_embedder()`` is used, which returns ``None`` when the ``[semantic]``
    extra is absent — in which case this returns ``available=False`` and touches
    nothing.
    """
    start = time.time()
    stats = {
        "embedded": 0,
        "skipped": 0,
        "deleted": 0,
        "total": 0,
        "dim": 0,
        "available": True,
        "elapsed_ms": 0,
    }

    wiki_root = Path(wiki_root).resolve()
    layout = discover_layout(str(wiki_root))
    pages_dir = Path(layout.pages_dir)
    if not pages_dir.is_dir():
        stats["available"] = False
        return stats

    if embedder is None:
        embedder = get_embedder()
    if embedder is None:
        stats["available"] = False
        return stats  # [semantic] extra absent → no-op, keyword unaffected

    dim = embedder.dimension
    stats["dim"] = dim

    db_path = wiki_root / INDEX_DIR_NAME / DB_FILENAME
    conn = vs.open_index_db(db_path)
    try:
        vec0 = vs.try_load_sqlite_vec(conn)
        vs.init_vector_schema(conn, dim=dim, with_vec0=vec0)

        meta = embedder.embed_meta(build_id=time.strftime("%Y%m%dT%H%M%S"))
        # A model/dimension change (or --rebuild) invalidates all vectors.
        if rebuild or not vs.embed_meta_matches(conn, meta):
            conn.execute("DELETE FROM page_vectors")
            conn.commit()
        vs.write_embed_meta(conn, meta)

        md_files = [
            f
            for f in pages_dir.rglob("*.md")
            if not any(p.startswith(".") for p in f.parts)
        ]
        current: set[str] = set()
        for f in md_files:
            rel = str(f.relative_to(wiki_root))
            current.add(rel)
            file_hash = hashlib.sha256(f.read_bytes()).hexdigest()
            if vs.vector_sha256(conn, rel) == file_hash:
                stats["skipped"] += 1
                continue
            vec = embedder.embed([_page_text(f)])[0]
            vs.store_vector(
                conn, rel, file_hash, vec, time.strftime("%Y-%m-%dT%H:%M:%S")
            )
            stats["embedded"] += 1

        # Drop vectors for pages that no longer exist on disk.
        for rel, _vec in list(vs.iter_vectors(conn)):
            if rel not in current:
                vs.delete_vector(conn, rel)
                stats["deleted"] += 1

        conn.commit()
        stats["total"] = vs.vector_count(conn)
    finally:
        conn.close()

    stats["elapsed_ms"] = int((time.time() - start) * 1000)
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Batch-embed wiki pages into the vector store "
        "(requires the [semantic] extra; no-op without it)."
    )
    parser.add_argument("wiki_root", help="Path to the wiki project root")
    parser.add_argument(
        "--rebuild", action="store_true", help="Re-embed every page from scratch"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output stats as JSON"
    )
    args = parser.parse_args()

    root = Path(args.wiki_root).resolve()
    if not root.is_dir():
        print(f"ERROR: '{root}' is not a directory", file=sys.stderr)
        return 2

    stats = embed_wiki(root, rebuild=args.rebuild)

    if not stats["available"]:
        print(
            "Semantic extra not installed; skipping embedding "
            "(keyword search unaffected).\n"
            "  Install with: pip install 'baissarienterprises-llm-wiki[semantic]'",
            file=sys.stderr,
        )
        if args.json:
            print(json.dumps(stats, indent=2))
        return 0

    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print(
            f"Embedded: {stats['embedded']}  Skipped: {stats['skipped']}  "
            f"Deleted: {stats['deleted']}"
        )
        print(
            f"Total vectors: {stats['total']}  Dim: {stats['dim']}  "
            f"Elapsed: {stats['elapsed_ms']}ms"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
