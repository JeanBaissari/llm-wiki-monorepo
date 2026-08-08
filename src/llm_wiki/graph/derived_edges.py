#!/usr/bin/env python3
"""derived_edges.py — Quarantined derived-edge layer (LWM_029). See ADR-0027.

The graph today has edges only where a ``[[wikilink]]`` resolves. This module
*discovers* two latent edge kinds and stores them in a **separate sibling layer**
(``.index/derived-edges.json``) that no default analytics consumer reads:

  * ``similar_to``    — cosine-KNN over the v0.4.0 page vectors (cos ≥ tau, top-m
    per node). Reuses ``semantic.vectorstore``; asserts ``embed_meta`` and is
    **skipped** (never corrupted) when the ``[semantic]`` extra / vectors / meta
    are absent. Co-occurrence still runs.
  * ``co_occurs_with`` — page pairs sharing ≥ s frontmatter sources OR ≥ e
    registry entities. Pure lexical/structural — runs on the base install.

Default-exclusion is guaranteed by construction: the layer is a new artifact that
``build.ts`` / ``graph-data.json`` / ``linkCount`` / insights / community
detection never open. Inclusion is opt-in per consumer and **fail-closed** on an
NMI+modularity gate (ADR-0027 §gate) — the derived-influenced partition must
keep the curated wikilink structure (NMI(with-derived, wikilink-only) ≥ 1 − tol)
and explain it at least as well as the wikilink-only baseline (modularity ≥
baseline), else inclusion is refused (``should_include_derived``).

Edge fields are spelled camelCase on disk (``relType``, ``directed``), matching
the shared ``GraphEdge`` interface in ``packages/shared-types`` (ADR-0026).
"""

from __future__ import annotations

import json
from pathlib import Path

DERIVED_FILE = "derived-edges.json"
INDEX_DIR = ".index"

REL_SIMILAR = "similar_to"
REL_COOCCUR = "co_occurs_with"


def derived_path(wiki_root) -> Path:
    return Path(wiki_root) / INDEX_DIR / DERIVED_FILE


def _undirected_key(a: str, b: str) -> str:
    return f"{a}|{b}" if a < b else f"{b}|{a}"


def _wikilink_pairs(pages) -> "set[str]":
    """Resolved undirected wikilink pairs (sorted keys) — the canonical baseline."""
    from llm_wiki.core.wikilinks import WIKILINK_RE

    by_title = {}
    for stem, (_p, _t, fm) in pages.items():
        by_title[stem.lower()] = stem
        title = (fm.get("title") if fm else None) or stem
        by_title[title.lower()] = stem
    pairs: set[str] = set()
    for stem, (_p, text, _fm) in pages.items():
        for link in WIKILINK_RE.findall(text):
            tgt = by_title.get(link.strip().lower()) or by_title.get(Path(link.strip()).stem.lower())
            if tgt and tgt != stem:
                pairs.add(_undirected_key(stem, tgt))
    return pairs


def _cooccurrence_edges(pages, min_shared_sources: int, min_shared_entities: int) -> "list[dict]":
    from llm_wiki.graph.suggest import build_entity_registry, build_inverted_index

    stems = list(pages)
    sources = {}
    for stem, (_p, _t, fm) in pages.items():
        src = (fm or {}).get("sources") or []
        sources[stem] = {str(s) for s in src} if isinstance(src, list) else set()

    registry = build_entity_registry(pages)
    inverted = build_inverted_index(pages, registry)
    page_entities = {stem: set(ents) for stem, ents in inverted.page_to_entities.items()}

    edges: list[dict] = []
    for i in range(len(stems)):
        for j in range(i + 1, len(stems)):
            a, b = stems[i], stems[j]
            shared_src = sources.get(a, set()) & sources.get(b, set())
            shared_ent = page_entities.get(a, set()) & page_entities.get(b, set())
            weight = 0
            reasons = {}
            if len(shared_src) >= min_shared_sources and shared_src:
                weight += len(shared_src)
                reasons["shared_sources"] = len(shared_src)
            if len(shared_ent) >= min_shared_entities and shared_ent:
                weight += len(shared_ent)
                reasons["shared_entities"] = len(shared_ent)
            if weight > 0 and reasons:
                edges.append({
                    "source": a, "target": b, "weight": float(weight),
                    "relType": REL_COOCCUR, "directed": False, "layer": "derived",
                    "provenance": reasons,
                })
    return edges


def _similarity_edges(wiki_root, pages, tau: float, top_m: int) -> "list[dict]":
    """Cosine-KNN similarity edges. Returns [] when [semantic]/vectors/meta absent."""
    try:
        from llm_wiki.search.index import DB_FILENAME, INDEX_DIR_NAME
        from llm_wiki.semantic.embedder import get_embedder
        from llm_wiki.semantic.vector_schema import (
            embed_meta_matches, iter_vectors, open_index_db, vector_count,
        )
        from llm_wiki.semantic.vectorstore import cosine_knn_numpy
    except Exception:
        return []

    embedder = get_embedder()
    if embedder is None:
        return []
    db_path = Path(wiki_root) / INDEX_DIR_NAME / DB_FILENAME
    if not db_path.exists():
        return []
    conn = open_index_db(db_path)
    try:
        if vector_count(conn) == 0:
            return []
        # Guard: mismatched embedding space → skip rather than emit corrupt edges.
        if not embed_meta_matches(conn, embedder.embed_meta()):
            return []
        vectors = list(iter_vectors(conn))  # [(rel_path, vec)]
    finally:
        conn.close()

    # Map vector rel_paths to page stems present in the graph.
    stem_by_path = {}
    for stem, (p, _t, _fm) in pages.items():
        stem_by_path[Path(p).stem] = stem
    corpus = [(stem_by_path.get(Path(rp).stem, Path(rp).stem), vec) for rp, vec in vectors]

    edges: list[dict] = []
    seen: set[str] = set()
    for name, vec in corpus:
        others = [(n2, v2) for n2, v2 in corpus if n2 != name]
        if not others:
            continue
        for other, score in cosine_knn_numpy(vec, others, top_m):  # [(name, score)]
            if score < tau:
                continue
            key = _undirected_key(name, other)
            if key in seen:
                continue
            seen.add(key)
            edges.append({
                "source": name, "target": other, "weight": round(float(score), 4),
                "relType": REL_SIMILAR, "directed": False, "layer": "derived",
                "provenance": {"cosine": round(float(score), 4)},
            })
    return edges


def generate_derived_edges(
    wiki_root,
    tau: float = 0.80,
    top_m: int = 5,
    min_shared_sources: int = 1,
    min_shared_entities: int = 2,
) -> dict:
    """Build the derived-edge layer and persist it to the sibling artifact.

    Never touches ``graph-data.json`` or ``linkCount``. Derived edges duplicating
    an existing wikilink edge are dropped (the wikilink is canonical).
    """
    from llm_wiki.core.layout import discover_layout
    from llm_wiki.graph.suggest import load_pages

    layout = discover_layout(wiki_root)
    wiki_dir = Path(layout.pages_dir)
    if not wiki_dir.is_dir():
        return {"similar_to": 0, "co_occurs_with": 0, "written": 0}
    skip_files = frozenset(f"{stem}.md" for stem in layout.skip_stems)
    pages = load_pages(wiki_dir, skip_files)

    wikilink = _wikilink_pairs(pages)
    sim = _similarity_edges(wiki_root, pages, tau, top_m)
    cooc = _cooccurrence_edges(pages, min_shared_sources, min_shared_entities)

    # Drop derived edges that duplicate a canonical wikilink edge.
    def not_dupe(e):
        return _undirected_key(e["source"], e["target"]) not in wikilink

    sim = [e for e in sim if not_dupe(e)]
    cooc = [e for e in cooc if not_dupe(e)]
    all_edges = sim + cooc

    out = derived_path(wiki_root)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "generator": "derived-v1",
        "params": {"tau": tau, "top_m": top_m,
                   "min_shared_sources": min_shared_sources,
                   "min_shared_entities": min_shared_entities},
        "edges": all_edges,
    }
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return {"similar_to": len(sim), "co_occurs_with": len(cooc), "written": len(all_edges)}


def load_derived_edges(wiki_root) -> "list[dict]":
    """Load the derived layer, or [] if it has not been built."""
    p = derived_path(wiki_root)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("edges", [])
    except (json.JSONDecodeError, OSError):
        return []


def _adjacency(edges) -> "dict[str, set[str]]":
    adj: dict[str, set[str]] = {}
    for e in edges:
        s, t = e["source"], e["target"]
        if s == t:
            continue
        adj.setdefault(s, set()).add(t)
        adj.setdefault(t, set()).add(s)
    return adj


def should_include_derived(nodes, wikilink_edges, derived_edges,
                           tol: float = 1e-6) -> "tuple[bool, dict]":
    """Fail-closed NMI+modularity gate for ``--include-derived`` (ADR-0027 §gate).

    Inclusion is allowed only when BOTH halves pass (AC#5):
      1. ``NMI(with-derived partition, wikilink-only partition) ≥ 1 − tol`` —
         the derived layer must not destroy the curated community structure
         (ADR-0012 NMI/ARI machinery; ``tol`` mirrors the search-gate epsilon).
      2. ``modularity(with-derived partition, wikilink graph) ≥ modularity(
         baseline partition, wikilink graph)`` — both partitions scored on the
         SAME (wikilink) graph, apples-to-apples.
    On any degradation (or empty derived layer) inclusion is **refused**.
    Returns ``(include: bool, report: dict)``.
    """
    from llm_wiki.eval.cluster_metrics import nmi
    from llm_wiki.graph.louvain import _compute_modularity, louvain

    if not derived_edges:
        return False, {"included": False, "reason": "no derived edges",
                       "baseline_modularity": None}

    if isinstance(nodes, dict):
        node_ids = list(nodes)
    elif nodes and isinstance(nodes[0], dict):
        node_ids = [n.get("id", "") for n in nodes]
    else:
        node_ids = list(nodes)
    wiki_adj = _adjacency(wikilink_edges)
    combined = list(wikilink_edges) + list(derived_edges)

    baseline_part = louvain(wikilink_edges, nodes=node_ids, seed=42)
    with_part = louvain(combined, nodes=node_ids, seed=42)

    # NMI between the two partitions, aligned by node id (order-independent).
    baseline_labels = [baseline_part.get(nid, -1) for nid in node_ids]
    with_labels = [with_part.get(nid, -1) for nid in node_ids]
    nmi_val = nmi(baseline_labels, with_labels)

    # Both partitions scored on the SAME (wikilink) graph — apples-to-apples.
    baseline_mod = _compute_modularity(wiki_adj, baseline_part)
    with_mod = _compute_modularity(wiki_adj, with_part)

    nmi_ok = nmi_val >= 1.0 - tol
    mod_ok = with_mod >= baseline_mod
    include = nmi_ok and mod_ok

    if not include:
        if not nmi_ok and not mod_ok:
            reason = "fail-closed: NMI and modularity below baseline"
        elif not nmi_ok:
            reason = "fail-closed: NMI below baseline"
        else:
            reason = "fail-closed: modularity below baseline"
    else:
        reason = "NMI >= 1-tol and modularity >= baseline"

    report = {
        "nmi_with_vs_baseline": round(nmi_val, 6),
        "tol": tol,
        "baseline_modularity": round(baseline_mod, 6),
        "with_derived_modularity": round(with_mod, 6),
        "delta": round(with_mod - baseline_mod, 6),
        "included": include,
        "reason": reason,
    }
    return include, report


def _wikilink_edges(pages) -> "list[dict]":
    """Wikilink edges as ``{source, target, weight}`` dicts (the gate baseline)."""
    return [
        {"source": a, "target": b, "weight": 1}
        for key in sorted(_wikilink_pairs(pages))
        for a, b in [key.split("|", 1)]
    ]


def _gate_after_build(wiki_root) -> "tuple[bool, dict]":
    """Run ``should_include_derived`` over the freshly built on-disk layer."""
    from llm_wiki.core.layout import discover_layout
    from llm_wiki.graph.suggest import load_pages

    layout = discover_layout(wiki_root)
    wiki_dir = Path(layout.pages_dir)
    skip_files = frozenset(f"{stem}.md" for stem in layout.skip_stems)
    pages = load_pages(wiki_dir, skip_files)
    return should_include_derived(pages, _wikilink_edges(pages),
                                  load_derived_edges(wiki_root))


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="llm-wiki derive-edges",
        description="Build the quarantined derived-edge layer (LWM_029). "
                    "Excluded by default from all analytics; consumers opt in "
                    "via --include-derived, gated on NMI+modularity (fail-closed).",
    )
    parser.add_argument("wiki_root", help="Path to the wiki root directory")
    parser.add_argument("--tau", type=float, default=0.80, help="Cosine similarity floor")
    parser.add_argument("--top-m", type=int, default=5, help="Max similarity neighbors per node")
    parser.add_argument("--min-shared-sources", type=int, default=1)
    parser.add_argument("--min-shared-entities", type=int, default=2)
    parser.add_argument("--include-derived", action="store_true",
                        help="After building, run the NMI+modularity gate and report "
                             "whether consumers may include the layer")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    stats = generate_derived_edges(
        args.wiki_root, tau=args.tau, top_m=args.top_m,
        min_shared_sources=args.min_shared_sources,
        min_shared_entities=args.min_shared_entities,
    )
    gate_report = None
    if args.include_derived:
        _include, gate_report = _gate_after_build(args.wiki_root)
    if args.json:
        out = dict(stats)
        if gate_report is not None:
            out["gate"] = gate_report
        print(json.dumps(out, indent=2))
    else:
        print(f"Derived layer: {stats['similar_to']} similar_to + "
              f"{stats['co_occurs_with']} co_occurs_with = {stats['written']} edges "
              f"(→ {derived_path(args.wiki_root)}). Excluded from analytics by default.")
        if gate_report is not None:
            verdict = ("included" if gate_report["included"]
                       else "refused (fail-closed)")
            print(f"Gate: NMI {gate_report['nmi_with_vs_baseline']} "
                  f"(tol {gate_report['tol']}), modularity "
                  f"{gate_report['with_derived_modularity']} vs baseline "
                  f"{gate_report['baseline_modularity']} → {verdict} "
                  f"({gate_report['reason']})")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
