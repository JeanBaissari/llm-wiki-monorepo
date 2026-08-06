#!/usr/bin/env python3
"""linking.py — Semantic link-suggestion engine (LWM_021, suggest-only).

Fuses up to three ranked lists of candidate *target pages* for a source page,
via LWM_019 Reciprocal Rank Fusion (ranks-only, so a missing signal simply
contributes nothing rather than corrupting the ranking):

  1. embedding — cosine KNN of the source page's vector over the store (LWM_017)
  2. ppr       — Personalized PageRank seeded at the source over the wikilink
                 graph (numpy-free power iteration; multi-hop, HippoRAG-style)
  3. lexical   — the existing entity/registry engine (``graph/suggest.py``)

Everything is keyed on the page **stem** (e.g. ``neural_network``): vector store
rel_paths (``wiki/concepts/neural_network.md``) are mapped to stems, matching the
id space ``suggest.py`` already uses.

A static-embedding (model2vec) similarity may NEVER be the sole justification for
an auto-applied link — see ADR-0021. ``is_auto_appliable`` enforces that.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from llm_wiki.core.layout import discover_layout
from llm_wiki.core.wikilinks import WIKILINK_RE
from llm_wiki.graph.suggest import (
    build_entity_registry,
    generate_suggestions,
    load_pages,
)
from llm_wiki.search.index import DB_FILENAME, INDEX_DIR_NAME
from llm_wiki.semantic.embed import _page_text
from llm_wiki.semantic.embedder import Embedder
from llm_wiki.semantic.fusion import reciprocal_rank_fusion, rrf_order
from llm_wiki.semantic.vector_schema import (
    embed_meta_matches,
    open_index_db,
    vector_count,
)
from llm_wiki.semantic.vectorstore import knn

# Signals that corroborate a link on their own (non-static). See ADR-0021.
_NON_STATIC_SIGNALS = frozenset({"lexical", "ppr"})


# ── Personalized PageRank ─────────────────────────────────────────────────────

def personalized_pagerank(
    adj: "dict[str, set[str]]",
    seed: str,
    alpha: float = 0.85,
    iters: int = 50,
    tol: float = 1e-6,
) -> "dict[str, float]":
    """Power-iteration Personalized PageRank with the teleport vector one-hot at
    ``seed``. Deterministic (sorted node iteration), pure-python.

    Semantics:
      * ``seed`` not in ``adj`` (includes an empty ``adj``) → ``{}``.
      * an isolated ``seed`` (no out-edges) keeps all mass on itself (1.0).
      * dangling nodes redistribute their mass to the personalization vector
        (the seed), so total mass is conserved at 1.0 every iteration.
    """
    if seed not in adj:
        return {}

    # Node universe = keys ∪ every referenced neighbor (robust to asymmetric input).
    nodes = set(adj.keys())
    for nbrs in adj.values():
        nodes.update(nbrs)
    nodes = sorted(nodes)

    rank: "dict[str, float]" = {n: 0.0 for n in nodes}
    rank[seed] = 1.0

    for _ in range(iters):
        nxt: "dict[str, float]" = {n: 0.0 for n in nodes}
        dangling = 0.0
        for u in nodes:
            mass = rank[u]
            if mass == 0.0:
                continue
            nbrs = adj.get(u) or ()
            if not nbrs:
                dangling += mass  # dangling node → mass flows to teleport
            else:
                share = alpha * mass / len(nbrs)
                for v in nbrs:
                    nxt[v] += share
        # Teleport (1-alpha) + reclaimed dangling mass, both onto the seed.
        nxt[seed] += (1.0 - alpha) + alpha * dangling
        delta = sum(abs(nxt[n] - rank[n]) for n in nodes)
        rank = nxt
        if delta < tol:
            break

    return rank


# ── wikilink graph ────────────────────────────────────────────────────────────

def _title_stem_maps(pages: dict) -> "tuple[dict[str, str], dict[str, str]]":
    by_title: "dict[str, str]" = {}
    by_stem: "dict[str, str]" = {}
    for stem, (_, _, fm) in pages.items():
        by_stem[stem.lower()] = stem
        title = fm.get("title", stem) if fm else stem
        by_title[str(title).lower()] = stem
    return by_title, by_stem


def _resolve_link(link: str, by_title: dict, by_stem: dict) -> Optional[str]:
    key = link.strip().lower()
    if key in by_title:
        return by_title[key]
    if key in by_stem:
        return by_stem[key]
    stem_key = Path(link.strip()).stem.lower()  # tolerate path-style links
    return by_stem.get(stem_key)


def build_stem_graph(pages: dict) -> "dict[str, set[str]]":
    """Undirected adjacency between page stems from resolved ``[[wikilinks]]``.

    Link text is resolved to a stem via a case-insensitive title/stem map;
    self-links and links that resolve to no known page are skipped.
    """
    by_title, by_stem = _title_stem_maps(pages)
    adj: "dict[str, set[str]]" = {stem: set() for stem in pages}

    for source, (_, text, _) in pages.items():
        for link in WIKILINK_RE.findall(text):
            target = _resolve_link(link, by_title, by_stem)
            if target is None or target == source:
                continue
            adj[source].add(target)
            adj.setdefault(target, set()).add(source)  # undirected

    return adj


# ── candidate producers ───────────────────────────────────────────────────────

def _dedup(seq) -> list:
    seen: set = set()
    out: list = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _embedding_targets(
    layout, pages: dict, source_stem: str, k: int, embedder: Optional[Embedder]
) -> list:
    """Ranked target stems from vector KNN, or ``[]`` when the semantic path is
    unavailable. Skipped entirely when the embedder is absent, no vectors are
    stored, or the stored ``embed_meta`` is incompatible (LWM_013 invariant #5)."""
    if embedder is None:
        return []
    db_path = Path(layout.root) / INDEX_DIR_NAME / DB_FILENAME
    if not db_path.exists():
        return []
    conn = open_index_db(db_path)
    try:
        if vector_count(conn) == 0:
            return []
        if not embed_meta_matches(conn, embedder.embed_meta()):
            return []
        source_path = pages[source_stem][0]
        vecs = embedder.embed([_page_text(source_path)])
        if not vecs:
            return []
        neighbors = knn(conn, vecs[0], k + 1)  # +1 to absorb the source itself
    finally:
        conn.close()

    targets = []
    for rel_path, _score in neighbors:
        stem = Path(rel_path).stem
        if stem != source_stem and stem in pages:
            targets.append(stem)
    return _dedup(targets)


def _ppr_targets(pages: dict, source_stem: str) -> list:
    """Ranked target stems by Personalized PageRank seeded at ``source_stem``."""
    ppr = personalized_pagerank(build_stem_graph(pages), source_stem)
    ranked = sorted(
        ((stem, score) for stem, score in ppr.items() if stem != source_stem and score > 0.0),
        key=lambda kv: (-kv[1], kv[0]),
    )
    return [stem for stem, _ in ranked]


def _lexical_targets(pages: dict, pages_dir: Path, source_stem: str) -> list:
    """Ranked target stems from the existing lexical/entity engine."""
    registry = build_entity_registry(pages)
    if not registry:
        return []
    limit = max(1, len(pages) * len(pages))
    suggestions = generate_suggestions(pages, registry, pages_dir, limit, 0.0)
    return _dedup(
        s["target_stem"]
        for s in suggestions
        if s["source_stem"] == source_stem and s["target_stem"] != source_stem
    )


# ── public entry point ────────────────────────────────────────────────────────

def semantic_related(
    wiki_root,
    source_stem: str,
    k: int = 10,
    embedder: Optional[Embedder] = None,
) -> "list[dict]":
    """Fuse embedding + PPR + lexical candidate lists into top-``k`` related notes.

    Returns a list of ``{target_stem, rank, score, signals}`` dicts, ordered by
    the RRF fusion. ``signals`` records which of ``embedding``/``ppr``/``lexical``
    contained the target. The source page is never a target. Degrades gracefully
    to whatever signals are available and never raises when a signal is empty.
    """
    layout = discover_layout(wiki_root)
    pages_dir = Path(layout.pages_dir)
    if not pages_dir.is_dir():
        return []

    skip_files = frozenset(f"{stem}.md" for stem in layout.skip_stems)
    pages = load_pages(pages_dir, skip_files)
    if source_stem not in pages:
        return []

    emb_list = _embedding_targets(layout, pages, source_stem, k, embedder)
    ppr_list = _ppr_targets(pages, source_stem)
    lex_list = _lexical_targets(pages, pages_dir, source_stem)

    emb_set, ppr_set, lex_set = set(emb_list), set(ppr_list), set(lex_list)
    lists = [emb_list, ppr_list, lex_list]

    order = rrf_order(lists)
    scores = dict(reciprocal_rank_fusion(lists))

    results: "list[dict]" = []
    for rank, target in enumerate(order, start=1):
        signals = [
            name
            for name, members in (
                ("embedding", emb_set),
                ("ppr", ppr_set),
                ("lexical", lex_set),
            )
            if target in members
        ]
        results.append(
            {
                "target_stem": target,
                "rank": rank,
                "score": round(scores.get(target, 0.0), 6),
                "signals": signals,
            }
        )
    return results[:k]


def is_auto_appliable(suggestion: dict) -> bool:
    """True only when a non-static signal (``lexical`` or ``ppr``) corroborates the
    suggestion. Embedding-only suggestions are suggest-only (ADR-0021)."""
    return any(s in _NON_STATIC_SIGNALS for s in suggestion.get("signals", ()))
