#!/usr/bin/env python3
"""query.py — Keyword and hybrid search over the FTS5 index (LWM_019/020).

Adds a Python query surface (`llm-wiki search`) — until now querying lived only
in the MCP/TS server. Two modes:

  * keyword (default): FTS5 native BM25 over the `.index/wiki.db` `pages` table.
  * hybrid (`--hybrid`, opt-in): Reciprocal-Rank-Fusion of BM25 + vector KNN.
    Requires the `[semantic]` extra + an embedded index; without either it
    transparently falls back to keyword-only (byte-identical), per LWM_013
    invariant #2/#3. A cosine floor keeps gibberish queries returning empty.

Hybrid is opt-in in v0.4.0; promoting it to the default is deferred to v0.5.0
after the eval harness proves no keyword-recall regression (ADR-0020).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Optional

from llm_wiki.core.layout import discover_layout
from llm_wiki.search.index import DB_FILENAME, INDEX_DIR_NAME, tokenize

# Vector similarity below this is treated as "not really a match", so a query
# with no lexical hits and no strong vector neighbor returns empty.
DEFAULT_SIM_FLOOR = 0.30


def _db_path(wiki_root) -> Path:
    return Path(wiki_root) / INDEX_DIR_NAME / DB_FILENAME


def _open_ro(wiki_root) -> Optional[sqlite3.Connection]:
    p = _db_path(wiki_root)
    if not p.exists():
        return None
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)


def _match_expr(query: str) -> str:
    """Build an FTS5 OR MATCH expression from the tokenized query (quoted)."""
    toks = tokenize(query)
    return " OR ".join(f'"{t}"' for t in toks)


def keyword_search(wiki_root, query: str, k: int = 10) -> "list[dict]":
    """FTS5/BM25 keyword results: ``[{path, title, snippet, score}]`` best-first.

    Byte-compatible default: returns ``[]`` when the index is missing/empty or
    the query has no indexable tokens.
    """
    conn = _open_ro(wiki_root)
    if conn is None:
        return []
    try:
        expr = _match_expr(query)
        if not expr:
            return []
        try:
            rows = conn.execute(
                "SELECT path, title, "
                "snippet(pages, 2, '', '', ' … ', 12) AS snip, "
                "bm25(pages) AS score "
                "FROM pages WHERE pages MATCH ? ORDER BY score LIMIT ?",
                (expr, int(k)),
            ).fetchall()
        except sqlite3.OperationalError:
            return []  # no pages table yet
        # bm25 is negative (more negative = better); expose a positive relevance.
        return [
            {"path": p, "title": t, "snippet": snip, "score": round(-float(s), 4)}
            for p, t, snip, s in rows
        ]
    finally:
        conn.close()


def _titles_for(conn: sqlite3.Connection, paths: "list[str]") -> "dict[str, str]":
    if not paths:
        return {}
    placeholders = ",".join("?" * len(paths))
    try:
        rows = conn.execute(
            f"SELECT path, title FROM pages WHERE path IN ({placeholders})",
            tuple(paths),
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    return {p: t for p, t in rows}


def hybrid_search(
    wiki_root,
    query: str,
    k: int = 10,
    embedder=None,
    sim_floor: float = DEFAULT_SIM_FLOOR,
) -> "list[dict]":
    """RRF fusion of BM25 + vector KNN, with keyword-only fallback.

    Falls back to :func:`keyword_search` (byte-identical) when the ``[semantic]``
    extra is absent, no vectors are indexed, or the ``embed_meta`` guard fails.
    """
    from llm_wiki.semantic.embedder import get_embedder
    from llm_wiki.semantic.fusion import rrf_order
    from llm_wiki.semantic.vector_schema import open_index_db, vector_count
    from llm_wiki.semantic.vectorstore import semantic_retrieve

    over = max(k * 3, 20)
    kw = keyword_search(wiki_root, query, over)
    kw_ids = [r["path"] for r in kw]

    p = _db_path(wiki_root)
    if not p.exists():
        return kw[:k]
    conn = open_index_db(p)
    try:
        if vector_count(conn) == 0:
            return kw[:k]  # nothing embedded → keyword-only
        emb = embedder if embedder is not None else get_embedder()
        vec = semantic_retrieve(conn, emb, query, over)
        if vec is None:
            return kw[:k]  # extra absent / meta mismatch → keyword-only

        vec_ids = [rel for rel, score in vec if score >= sim_floor]
        if not kw_ids and not vec_ids:
            return []  # no lexical hit and no strong neighbor → empty

        fused = rrf_order([kw_ids, vec_ids])
        kw_by_path = {r["path"]: r for r in kw}
        titles = _titles_for(conn, [i for i in fused if i not in kw_by_path])

        out: "list[dict]" = []
        for rank, pid in enumerate(fused[:k], start=1):
            if pid in kw_by_path:
                r = dict(kw_by_path[pid])
                r["matched"] = "both" if pid in vec_ids else "keyword"
            else:
                r = {"path": pid, "title": titles.get(pid, Path(pid).stem),
                     "snippet": "", "matched": "vector"}
            r["rank"] = rank
            out.append(r)
        return out
    finally:
        conn.close()


def _print_results(results: "list[dict]", query: str) -> None:
    print(f"# Search: {query}")
    if not results:
        print("No results.")
        return
    for i, r in enumerate(results, 1):
        tag = f" [{r['matched']}]" if "matched" in r else ""
        print(f"{i}. {r['title']}  ({r['path']}){tag}")
        if r.get("snippet"):
            print(f"     {r['snippet']}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Search the wiki (keyword by default; --hybrid adds semantic)."
    )
    parser.add_argument("wiki_root", help="Path to the wiki project root")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--hybrid", action="store_true",
                        help="Fuse keyword + semantic (requires the [semantic] extra)")
    parser.add_argument("--top-k", type=int, default=10, dest="top_k",
                        help="Number of results (default: 10)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    layout = discover_layout(args.wiki_root)
    root = layout.root

    if args.hybrid:
        results = hybrid_search(root, args.query, args.top_k)
    else:
        results = keyword_search(root, args.query, args.top_k)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        _print_results(results, args.query)
    return 0


if __name__ == "__main__":
    sys.exit(main())
