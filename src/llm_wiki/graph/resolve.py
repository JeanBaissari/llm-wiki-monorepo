#!/usr/bin/env python3
"""resolve.py — Lightweight entity resolution pipeline (LWM_025).

normalize → block → score → merge. Collapses variant surface forms ("GPT-4",
"GPT 4", "gpt-4") to one canonical id. The base path is stdlib-only
(unicodedata, re, difflib); the embedding signal reuses the ``[semantic]`` extra
when present and degrades to string-similarity-only (at a raised threshold) when
absent. Splink is an optional refinement (``[entity-resolution]`` extra), never
imported here.

Merge safety (ADR-0024): a non-identical pair merges only when **two independent
signals agree** (string + embedding). With no embedder, only very-high string
similarity merges, at a conservative threshold — so a missing extra never causes
looser merging. Reversibility + persistence live in ``alias_store.py``.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from collections import defaultdict
from itertools import combinations
from pathlib import Path

from llm_wiki.graph import alias_store

RESOLVER_ID = "lightweight-v1"


def normalize(s: str) -> str:
    """NFKC + casefold + collapse separators/punctuation."""
    s = unicodedata.normalize("NFKC", s).casefold()
    s = re.sub(r"[\s\-_/]+", " ", s)
    s = re.sub(r"[^\w ]+", "", s)
    return s.strip()


def string_sim(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def _blocks(norms: "list[str]") -> "dict[str, set[int]]":
    """Block candidates by shared token / 3-char prefix to limit pair comparisons."""
    blocks: "dict[str, set[int]]" = defaultdict(set)
    for i, n in enumerate(norms):
        if not n:
            continue
        keys = set(n.split()) | {n[:3]}
        for k in keys:
            blocks[k].add(i)
    return blocks


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def resolve_entities(
    candidates: "list[str]",
    embedder=None,
    str_threshold: float = 0.85,
    cos_threshold: float = 0.80,
) -> "list[dict]":
    """Cluster variant surface forms → proposed merge dicts.

    Each merge: ``{canonical_id, canonical_label, alias, method, signals, score}``.
    The canonical per cluster is the longest surface form (tie: sorted). Identical
    normalized forms always merge (identity signal).
    """
    surfaces = list(dict.fromkeys(c.strip() for c in candidates if c and c.strip()))
    n = len(surfaces)
    if n < 2:
        return []
    norms = [normalize(s) for s in surfaces]

    vecs = None
    np = None
    if embedder is not None:
        try:
            import numpy as _np

            np = _np
            raw = _np.asarray(embedder.embed(surfaces), dtype=_np.float32)
            norms_v = _np.linalg.norm(raw, axis=1, keepdims=True)
            norms_v[norms_v == 0] = 1.0
            vecs = raw / norms_v
        except Exception:
            vecs = None

    uf = _UnionFind(n)
    scores: "dict[tuple[int, int], float]" = {}
    for _key, idxs in _blocks(norms).items():
        for a, b in combinations(sorted(idxs), 2):
            if (a, b) in scores:
                continue
            if not norms[a] or not norms[b]:
                scores[(a, b)] = 0.0
                continue
            if norms[a] == norms[b]:
                uf.union(a, b)
                scores[(a, b)] = 1.0
                continue
            ss = string_sim(norms[a], norms[b])
            if vecs is not None:
                cos = float(vecs[a] @ vecs[b])
                scores[(a, b)] = (ss + cos) / 2.0
                if ss >= str_threshold and cos >= cos_threshold:
                    uf.union(a, b)  # two independent signals agree
            else:
                scores[(a, b)] = ss
                if ss >= max(str_threshold, 0.92):  # string-only: raised bar
                    uf.union(a, b)

    clusters: "dict[int, list[int]]" = defaultdict(list)
    for i in range(n):
        clusters[uf.find(i)].append(i)

    merges: "list[dict]" = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        canon_i = sorted(members, key=lambda i: (-len(surfaces[i]), surfaces[i]))[0]
        canon_label = surfaces[canon_i]
        cid = normalize(canon_label).replace(" ", "-") or canon_label
        signals = ["embedding", "string"] if vecs is not None else ["string"]
        for i in members:
            if i == canon_i:
                continue
            pair = (min(i, canon_i), max(i, canon_i))
            merges.append({
                "canonical_id": cid,
                "canonical_label": canon_label,
                "alias": surfaces[i],
                "method": RESOLVER_ID,
                "signals": signals,
                "score": round(scores.get(pair, 1.0), 4),
            })
    return merges


def apply_resolution(
    wiki_root,
    candidates: "list[str]",
    embedder=None,
    threshold: float = 0.85,
    actor: str = "resolve",
) -> dict:
    """Run resolution, append merge events to the JSONL, rebuild the derived cache."""
    from llm_wiki.search.index import DB_FILENAME, INDEX_DIR_NAME
    from llm_wiki.semantic.vector_schema import open_index_db

    merges = resolve_entities(candidates, embedder=embedder, str_threshold=threshold)
    for m in merges:
        alias_store.append_event(wiki_root, {"event": "merge", "actor": actor, **m})

    db_path = Path(wiki_root) / INDEX_DIR_NAME / DB_FILENAME
    conn = open_index_db(db_path)
    try:
        n_aliases = alias_store.rebuild_derived(conn, wiki_root, RESOLVER_ID, threshold)
    finally:
        conn.close()

    canonicals = len({m["canonical_id"] for m in merges})
    return {"merged": len(merges), "canonicals": canonicals, "total_aliases": n_aliases}


def unmerge(wiki_root, alias: str, actor: str = "unmerge") -> bool:
    """Reverse a merge by appending an unmerge event + rebuilding. Returns True if known."""
    from llm_wiki.search.index import DB_FILENAME, INDEX_DIR_NAME
    from llm_wiki.semantic.vector_schema import open_index_db

    state = alias_store.resolve_state(alias_store.read_events(wiki_root))
    if alias not in state:
        return False
    alias_store.append_event(wiki_root, {"event": "unmerge", "alias": alias, "actor": actor})
    db_path = Path(wiki_root) / INDEX_DIR_NAME / DB_FILENAME
    conn = open_index_db(db_path)
    try:
        alias_store.rebuild_derived(conn, wiki_root, RESOLVER_ID, 0.85)
    finally:
        conn.close()
    return True


