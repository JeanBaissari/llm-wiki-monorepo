#!/usr/bin/env python3
"""query.py — Keyword and hybrid search over the FTS5 index (LWM_019/020).

Adds a Python query surface (`llm-wiki search`) — until now querying lived only
in the MCP/TS server. Two modes:

  * hybrid (default): Reciprocal-Rank-Fusion of BM25 + vector KNN. Requires the
    `[semantic]` extra + an embedded index; without either it transparently falls
    back to keyword-only (byte-identical), per LWM_013 invariant #2/#3. A cosine
    floor keeps gibberish queries returning empty.
  * keyword (`--keyword`): FTS5 native BM25 over the `.index/wiki.db` `pages` table.

Hybrid became the default in v0.5.0 once the search-eval gate proved no
keyword-recall regression on the held-out GATE split. See ADR-0020 / LWM_032.
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


def keyword_search(wiki_root, query: str, k: int = 10, k1: float | None = None,
                   b: float | None = None) -> "list[dict]":
    """FTS5/BM25 keyword results: ``[{path, title, snippet, score}]`` best-first.

    Byte-compatible default: returns ``[]`` when the index is missing/empty or
    the query has no indexable tokens.

    LWM_031 BM25 threading: FTS5's native ``bm25()`` has fixed k1/b, so when
    tuning overrides are present (non-default ``bm25.k1``/``bm25.b`` — the
    values differ from the config defaults 1.5/0.75) a deterministic
    Python-side BM25 rescoring runs over the FTS5 candidate rows with those
    parameters; with the defaults (None or the config defaults) the current
    FTS5-native path is used byte-identical. The rescoring model mirrors
    mcp-server/src/search.ts (same IDF formula, same K1/B defaults).
    """
    from llm_wiki.core.config import TuningConfig
    defaults = TuningConfig().bm25
    native = k1 is None or (k1 == defaults.k1 and b == defaults.b)
    conn = _open_ro(wiki_root)
    if conn is None:
        return []
    try:
        expr = _match_expr(query)
        if not expr:
            return []
        try:
            if native:
                rows = conn.execute(
                    "SELECT path, title, "
                    "snippet(pages, 2, '', '', ' … ', 12) AS snip, "
                    "bm25(pages) AS score "
                    "FROM pages WHERE pages MATCH ? ORDER BY score LIMIT ?",
                    (expr, int(k)),
                ).fetchall()
            else:
                rows = _bm25_rescore(conn, expr, int(k),
                                     float(k1 if k1 is not None else defaults.k1),
                                     float(b if b is not None else defaults.b))
        except sqlite3.OperationalError:
            return []  # no pages table yet
        # bm25 is negative (more negative = better); expose a positive relevance.
        return [
            {"path": p, "title": t, "snippet": snip, "score": round(-float(s), 4)}
            for p, t, snip, s in rows
        ]
    finally:
        conn.close()


def _bm25_rescore(conn: sqlite3.Connection, expr: str, k: int, k1: float, b: float):
    """Python-side BM25(k1, b) over FTS5 candidates (tuned path only).

    Deterministic: same IDF formula as mcp-server/src/search.ts
    (``log((N - df + 0.5) / (df + 0.5) + 1)``), same length normalization, ties
    broken by path so repeated runs agree. Candidate rows come from the FTS5
    MATCH (with ``snippet()``), so ranking is the only thing that changes.
    """
    import math

    stats = {}
    for key in ("doc_count", "avg_length"):
        row = conn.execute(
            "SELECT value FROM index_stats WHERE key = ?", (key,)
        ).fetchone()
        stats[key] = float(row[0]) if row and row[0] is not None else 0.0
    n_docs = int(stats["doc_count"])
    avg_length = stats["avg_length"]
    if n_docs == 0 or avg_length <= 0:
        return []

    terms = expr.replace('"', "").split(" OR ")
    idf: dict[str, float] = {}
    for term in terms:
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM pages WHERE pages MATCH ?", (term,)
            ).fetchone()
            df = row[0] if row else 0
            idf[term] = math.log((n_docs - df + 0.5) / (df + 0.5) + 1)
        except sqlite3.OperationalError:
            idf[term] = math.log((n_docs + 0.5) / 0.5 + 1)

    rows = conn.execute(
        "SELECT path, title, snippet(pages, 2, '', '', ' … ', 12) AS snip, content "
        "FROM pages WHERE pages MATCH ?",
        (expr,),
    ).fetchall()

    scored: list[tuple] = []
    for path, title, snip, content in rows:
        tokens = content.split() if content else []
        doc_len = len(tokens)
        score = 0.0
        for term in terms:
            tf = sum(1 for t in tokens if t == term)
            if tf == 0:
                continue
            denom = tf + k1 * (1 - b + b * (doc_len / avg_length))
            score += idf.get(term, 0.0) * (tf * (k1 + 1)) / denom
        if score > 0:
            # bm25 native returns negative scores; the caller negates, so the
            # rescored path mirrors that sign convention (positive relevance).
            scored.append((path, title, snip, -score))

    scored.sort(key=lambda r: (r[3], r[0]))  # ascending bm25 == best first
    return scored[:k]


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
    sim_floor: "Optional[float]" = None,
    rrf_k: "Optional[int]" = None,
    bm25_k1: "Optional[float]" = None,
    bm25_b: "Optional[float]" = None,
) -> "list[dict]":
    """RRF fusion of BM25 + vector KNN, with keyword-only fallback.

    Falls back to :func:`keyword_search` (byte-identical) when the ``[semantic]``
    extra is absent, no vectors are indexed, or the ``embed_meta`` guard fails.

    LWM_031 tuning: when the caller does not pass explicit values (e.g. the MCP
    sidecar), the wiki's resolved tuning (``tuning.toml`` at the wiki root + env
    + defaults) supplies ``retrieval.simFloor`` / ``retrieval.rrfK`` and the
    ``bm25.k1``/``bm25.b`` overrides; defaults stay byte-identical.
    """
    from llm_wiki.core.config import resolve_tuning
    from llm_wiki.semantic.embedder import get_embedder
    from llm_wiki.semantic.fusion import rrf_order
    from llm_wiki.semantic.vector_schema import open_index_db, vector_count
    from llm_wiki.semantic.vectorstore import semantic_retrieve

    if sim_floor is None or rrf_k is None or bm25_k1 is None or bm25_b is None:
        tuning = resolve_tuning(wiki_root)
        if sim_floor is None:
            sim_floor = tuning.retrieval.simFloor
        if rrf_k is None:
            rrf_k = tuning.retrieval.rrfK
        over = tuning.overridden()
        # Only non-default bm25 values switch keyword_search to Python
        # rescoring; the default path stays FTS5-native (byte-identical).
        if bm25_k1 is None:
            bm25_k1 = tuning.bm25.k1 if "bm25.k1" in over else None
        if bm25_b is None:
            bm25_b = tuning.bm25.b if "bm25.b" in over else None

    over = max(k * 3, 20)
    kw = keyword_search(wiki_root, query, over, k1=bm25_k1, b=bm25_b)
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

        fused = rrf_order([kw_ids, vec_ids], k=rrf_k)
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
        description="Search the wiki (hybrid by default; --keyword forces lexical-only). "
                    "See ADR-0020."
    )
    parser.add_argument("wiki_root", help="Path to the wiki project root")
    parser.add_argument("query", help="Search query")
    # Hybrid is the v0.5.0 default (LWM_032/ADR-0020); it degrades to keyword
    # byte-identically without the [semantic] extra. --keyword forces lexical-only.
    parser.add_argument("--keyword", action="store_true",
                        help="Force keyword-only ranking (pre-v0.5.0 default)")
    parser.add_argument("--hybrid", action="store_true",
                        help=argparse.SUPPRESS)  # back-compat no-op: hybrid is now default
    parser.add_argument("--top-k", type=int, default=10, dest="top_k",
                        help="Number of results (default: 10)")
    parser.add_argument("--set", action="append", default=[], dest="overrides",
                        metavar="section.key=value",
                        help="Tuning override, e.g. retrieval.simFloor=0.4 (LWM_031)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    layout = discover_layout(args.wiki_root)
    root = layout.root

    from llm_wiki.core.config import ConfigError, resolve_tuning
    try:
        tuning = resolve_tuning(root, cli_overrides=args.overrides)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2

    if args.keyword:
        over = tuning.overridden()
        results = keyword_search(
            root, args.query, args.top_k,
            k1=tuning.bm25.k1 if "bm25.k1" in over else None,
            b=tuning.bm25.b if "bm25.b" in over else None,
        )
    else:
        results = hybrid_search(root, args.query, args.top_k,
                                sim_floor=tuning.retrieval.simFloor,
                                rrf_k=tuning.retrieval.rrfK)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        _print_results(results, args.query)
    return 0


if __name__ == "__main__":
    sys.exit(main())
