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

# Pairs scoring at/above this floor (string + embedding) but below the merge
# thresholds are ambiguous near-misses: surfaced as `entity-merge` review rows
# for a human decision, never auto-merged (LWM_025 AC#6 / error handling).
NEAR_MISS_FLOOR = 0.5


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


def _near_miss(surface_a: str, surface_b: str, ss: float, cos: "float | None") -> dict:
    """One ambiguous/near-miss pair dict (single-signal → review row, never a merge)."""
    if len(surface_a) >= len(surface_b):
        label, alias = surface_a, surface_b
    else:
        label, alias = surface_b, surface_a
    cid = normalize(label).replace(" ", "-") or label
    return {
        "event": "near-miss",
        "canonical_id": cid,
        "canonical_label": label,
        "alias": alias,
        "method": RESOLVER_ID,
        "signals": ["embedding", "string"] if cos is not None else ["string"],
        "ss": round(ss, 4),
        "cos": round(cos, 4) if cos is not None else None,
        "score": round((ss + cos) / 2.0 if cos is not None else ss, 4),
    }


def resolve_entities(
    candidates: "list[str]",
    embedder=None,
    str_threshold: float = 0.85,
    cos_threshold: float = 0.80,
    near_miss_sink: "list[dict] | None" = None,
) -> "list[dict]":
    """Cluster variant surface forms → proposed merge dicts.

    Each merge: ``{canonical_id, canonical_label, alias, method, signals, score}``.
    The canonical per cluster is the longest surface form (tie: sorted). Identical
    normalized forms always merge (identity signal).

    When ``near_miss_sink`` is given, ambiguous pairs (both signals below the
    merge thresholds but at/above ``NEAR_MISS_FLOOR``, or string-only pairs in
    that band) are appended as review-row dicts instead of silently dropping
    them (LWM_025 AC#6). ``None`` keeps the legacy behavior exactly.
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
            # numpy absent (base install) → fall back to the pure-Python dot
            # below, so an explicitly-provided embedder still feeds the
            # two-signal path (LWM_025) instead of silently degrading to
            # string-only. Never leave a half-built numpy vecs behind.
            vecs = None
            np = None

    if vecs is None and embedder is not None:
        # Pure-Python fallback: L2-normalized dense vectors, cosine via dot.
        try:
            rows = [list(map(float, v)) for v in embedder.embed(surfaces)]
            if rows and all(len(r) == len(rows[0]) for r in rows):
                dim = len(rows[0])
                normed = []
                for r in rows:
                    norm = sum(x * x for x in r) ** 0.5
                    normed.append([x / norm for x in r] if norm else [0.0] * dim)
                vecs = normed
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
                # numpy arrays and pure-Python lists both support dot product
                # (list @ list fails, so fall back to a manual dot for the
                # numpy-free base-install path).
                try:
                    cos = float(vecs[a] @ vecs[b])
                except TypeError:
                    cos = sum(x * y for x, y in zip(vecs[a], vecs[b]))
                scores[(a, b)] = (ss + cos) / 2.0
                if ss >= str_threshold and cos >= cos_threshold:
                    uf.union(a, b)  # two independent signals agree
                elif (
                    near_miss_sink is not None
                    and ss >= NEAR_MISS_FLOOR
                    and cos >= NEAR_MISS_FLOOR
                ):
                    near_miss_sink.append(_near_miss(surfaces[a], surfaces[b], ss, cos))
            else:
                scores[(a, b)] = ss
                if ss >= max(str_threshold, 0.92):  # string-only: raised bar
                    uf.union(a, b)
                elif near_miss_sink is not None and ss >= NEAR_MISS_FLOOR:
                    near_miss_sink.append(_near_miss(surfaces[a], surfaces[b], ss, None))

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


def _write_review_rows(wiki_root, near_misses: "list[dict]", actor: str) -> "list[str]":
    """Emit one ``entity-merge`` audit review row per ambiguous near-miss pair.

    LWM_025 AC#6 / error-handling contract: single-signal and ambiguous
    candidates surface as human-review rows instead of silently dropping (and
    never auto-merge). Rows are written only when near-misses exist — a run
    with none creates no audit files (no regression for existing wikis).
    """
    from llm_wiki.core.layout import discover_layout
    from llm_wiki.quality.audit.writer import AuditWriter

    layout = discover_layout(wiki_root)
    audit_dir = layout.audit_dir or str(Path(wiki_root) / "audit")
    writer = AuditWriter(audit_dir, wiki_root)
    paths: "list[str]" = []
    for nm in near_misses:
        detail = {
            "canonical_id": nm["canonical_id"],
            "canonical_label": nm["canonical_label"],
            "alias": nm["alias"],
            "string_sim": nm["ss"],
            "embedding_cos": nm["cos"],
            "signals": ",".join(nm["signals"]),
            "method": nm["method"],
        }
        body = "\n".join(f"- {k}: {v}" for k, v in detail.items())
        p = writer.write_unanchored(
            target=f"entity-merge: {nm['canonical_label']} ↔ {nm['alias']}",
            target_kind="wiki",
            target_reason=(
                "Ambiguous entity pair left unmerged by entities resolve: at/above "
                "the near-miss floor but below the two-signal merge thresholds — "
                "needs a human decision (LWM_025 AC#6)."
            ),
            severity="suggest",
            author=actor,
            source="agent",
            body=body,
        )
        if p:
            paths.append(p)
    return paths


def apply_resolution(
    wiki_root,
    candidates: "list[str]",
    embedder=None,
    threshold: float = 0.85,
    actor: str = "resolve",
) -> dict:
    """Run resolution, append merge events to the JSONL, rebuild the derived cache.

    Ambiguous/near-miss pairs (LWM_025 AC#6) are emitted as ``entity-merge``
    audit review rows (stats keys ``review_rows`` + ``audit_paths``) — only when
    such pairs exist; a clean run creates no audit files.
    """
    from llm_wiki.search.index import DB_FILENAME, INDEX_DIR_NAME
    from llm_wiki.semantic.vector_schema import open_index_db

    near_misses: "list[dict]" = []
    merges = resolve_entities(
        candidates,
        embedder=embedder,
        str_threshold=threshold,
        near_miss_sink=near_misses,
    )
    for m in merges:
        alias_store.append_event(wiki_root, {"event": "merge", "actor": actor, **m})

    db_path = Path(wiki_root) / INDEX_DIR_NAME / DB_FILENAME
    conn = open_index_db(db_path)
    try:
        n_aliases = alias_store.rebuild_derived(conn, wiki_root, RESOLVER_ID, threshold)
    finally:
        conn.close()

    audit_paths = _write_review_rows(wiki_root, near_misses, actor) if near_misses else []
    canonicals = len({m["canonical_id"] for m in merges})
    return {
        "merged": len(merges),
        "canonicals": canonicals,
        "total_aliases": n_aliases,
        "review_rows": len(audit_paths),
        "audit_paths": audit_paths,
    }


def alias_targets(wiki_root) -> "dict[str, str]":
    """``{alias_surface -> canonical_label}`` from the JSONL source of truth.

    Lets ``link_suggest`` route a mention of an alias ("gpt-4") to the canonical
    entity's page ("GPT-4"). Empty when no resolution has run — so the default
    lexical path stays byte-identical.
    """
    events = alias_store.read_events(wiki_root)
    state = alias_store.resolve_state(events)
    labels = alias_store.canonical_labels(events)
    return {alias: labels.get(cid, cid) for alias, cid in state.items()}


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


