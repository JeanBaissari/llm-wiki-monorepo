#!/usr/bin/env python3
"""summarize.py — Opt-in community summaries (LWM_030). See ADR-0009 / ADR-0025.

``llm-wiki summarize-communities <wiki>`` makes one structured LLM call per
community per hierarchy level (via ``providers/registry.call_llm_structured``,
agent-native ``$0.00`` default) to turn anonymous integer communities into
readable themes, then writes each as a first-class ``type: community-summary``
page under ``communities/`` with ``[[member]]`` wikilinks — so summaries become
normal, searchable graph nodes.

Hierarchy (LWM_030 AC#4/AC#5): level-0 pages ``L0-{sha}.md`` are the flat
communities; level-N pages ``L{level}-{sha}.md`` are coarser parents that
summarize their child summaries; the root is ``global-summary.md`` (level:
global). ``--levels`` caps depth, ``--max-communities`` caps per level.

Hierarchy seam (B4 → B6): when the opt-in Leiden sidecar exposes
``leiden.hierarchical_levels(nodes, edges, seed=42)`` returning
``list[dict]`` bottom-up (finest first) with ``{"level": int,
"assignments": {node_id: cid}}``, those levels are consumed as-is; otherwise
level 0 is the flat engine partition and higher levels are a deterministic
agglomeration of it. An explicit ``--engine leiden`` with no hierarchy
available degrades to flat + global only.

Strictly opt-in: when the operation is not run the wiki is byte-identical.
Cost-bounded (``--dry-run`` estimates with zero calls; unchanged communities
skip via a member-set SHA; caps bound work). Faithfulness-gated: ``key_entities``
are filtered to the community's real member entities — including the global
root, whose reference is the union of member entities, never raw LLM output.
Summary page filenames are keyed on the member-set SHA only, and pages whose
member set left the current partition are removed (no orphan graph nodes).
The summarizer is injectable for deterministic offline tests.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
from pathlib import Path

from pydantic import BaseModel, Field

EXCERPT_CHARS = 280  # per-member prompt budget (char proxy keeps base install pure)
# L{level}-{sha}.md (+ legacy L0-{sha}-{slug}.md from pre-AD-12 runs).
_SUMMARY_FILE_RE = re.compile(r"^L\d+-([0-9a-f]{16})(?:-[^/]*)?\.md$")


class CommunitySummary(BaseModel):
    title: str
    summary: str
    key_entities: "list[str]" = Field(default_factory=list)


def _build_graph(pages):
    """Return (nodes: {stem:{label,linkCount}}, edges: [(a,b)]) — the wikilink graph."""
    from llm_wiki.graph.derived_edges import _wikilink_pairs

    pairs = _wikilink_pairs(pages)
    link_count = {stem: 0 for stem in pages}
    edges = []
    for key in pairs:
        a, b = key.split("|", 1)
        edges.append((a, b))
        link_count[a] = link_count.get(a, 0) + 1
        link_count[b] = link_count.get(b, 0) + 1
    nodes = {}
    for stem, (_p, _t, fm) in pages.items():
        nodes[stem] = {"label": (fm.get("title") if fm else None) or stem,
                       "linkCount": link_count.get(stem, 0)}
    return nodes, edges


def _member_entities(pages, stems) -> "set[str]":
    from llm_wiki.graph.resolve import normalize
    from llm_wiki.graph.suggest import extract_entities

    ents: set[str] = set()
    for s in stems:
        if s in pages:
            for e in extract_entities(pages[s][1]):
                ents.add(normalize(e))
    return ents


def _member_sha(stems) -> str:
    return hashlib.sha256("|".join(sorted(stems)).encode("utf-8")).hexdigest()[:16]


def _default_summarizer(provider: str, model, timeout):
    from llm_wiki.providers.registry import call_llm_structured

    def _fn(system: str, user: str):
        return call_llm_structured(system, user, CommunitySummary,
                                   provider=provider, model=model, total_timeout=timeout)
    return _fn


def _build_prompt(nodes, pages, stems, child_summaries=None) -> "tuple[str, str]":
    """Per-community prompt. Leaf communities get member excerpts; parent
    communities (level > 0) get their child summaries instead (LWM_030)."""
    system = (
        "You summarize a cluster of related wiki pages. Produce a concise title, "
        "a 2-4 sentence summary, and key_entities. Use ONLY the provided member "
        "content; draw key_entities ONLY from the members shown."
    )
    if child_summaries:
        lines = [f"- {c.title}: {c.summary}" for c in child_summaries]
        user = "Child summaries (parent level):\n" + "\n".join(lines)
    else:
        lines = []
        for s in sorted(stems):
            if s not in pages:
                continue
            label = nodes.get(s, {}).get("label", s)
            body = pages[s][1]
            excerpt = " ".join(body.split())[:EXCERPT_CHARS]
            lines.append(f"- {label}: {excerpt}")
        user = "Member pages:\n" + "\n".join(lines)
    return system, user


def _hierarchy_from_leiden(nodes, edges, engine=None):
    """B6 seam — real hierarchy levels from the opt-in Leiden sidecar.

    Contract (B6): ``leiden.hierarchical_levels(nodes, edges, seed=42)`` returns
    ``list[dict]`` bottom-up (finest level first), each with ``{"level": int,
    "assignments": {node_id: cid}}``; returns ``None`` when no hierarchy is
    computable. Returns ``None`` when unavailable — the caller degrades.
    """
    if (engine or "").lower() == "louvain":
        return None
    try:
        from llm_wiki.graph import leiden
    except ImportError:
        return None
    if not leiden.is_leiden_available():
        return None
    levels_fn = getattr(leiden, "hierarchical_levels", None)
    if levels_fn is None:
        return None
    node_list = [{"id": pid, "label": a.get("label", pid),
                  "linkCount": a.get("linkCount", 0)} for pid, a in nodes.items()]
    edge_list = [{"source": s, "target": t, "weight": 1} for s, t in edges]
    try:
        raw = levels_fn(node_list, edge_list, seed=42)
    except Exception:
        return None
    if not raw:
        return None
    levels = []
    for item in raw:
        assignments = dict(item.get("assignments", {}))
        for pid in nodes:
            assignments.setdefault(pid, len(assignments))
        levels.append(assignments)
    return levels


def _agglomerate(assignments, edges, target_k):
    """Deterministic single-level coarsening: repeatedly merge the smallest
    community (fewest members; lowest cid breaks ties) with its neighbor of
    maximum shared edges (lowest cid breaks ties) until ≤ target_k remain."""
    from collections import defaultdict

    node_comm = dict(assignments)
    comms: dict = {}
    for node, cid in assignments.items():
        comms.setdefault(cid, set()).add(node)
    while len(comms) > target_k:
        smallest = min(comms, key=lambda c: (len(comms[c]), c))
        shared: dict = defaultdict(int)
        for a, b in edges:
            ca, cb = node_comm.get(a), node_comm.get(b)
            if ca is None or cb is None or ca == cb:
                continue
            if ca == smallest:
                shared[cb] += 1
            elif cb == smallest:
                shared[ca] += 1
        if shared:
            merge = max(shared, key=lambda c: (shared[c], -c))
        else:
            cand = [c for c in comms if c != smallest]
            if not cand:
                break
            merge = min(cand, key=lambda c: (len(comms[c]), c))
        keep, drop = min(smallest, merge), max(smallest, merge)
        comms[keep] = comms[keep] | comms[drop]
        del comms[drop]
        for node in comms[keep]:
            node_comm[node] = keep
    return node_comm


def _partition_levels(nodes, edges, engine=None, max_levels: int = 1):
    """Hierarchy seam → ``(levels, source)`` with levels bottom-up.

    Each level is ``{"level": int, "assignments": {node_id: cid}}``. Level 0 is
    always the flat engine partition. Higher levels come from (1) the B6 Leiden
    hierarchy when available; (2) otherwise a deterministic agglomeration of the
    previous level; (3) an explicit ``--engine leiden`` with no hierarchy
    available caps at flat + global. ``source`` is "leiden" | "agglomerated" |
    "flat" (the hierarchy actually used — B7 gates on it).
    """
    from llm_wiki.graph.insights import detect_communities_for_insights

    flat = detect_communities_for_insights(nodes, edges, engine=engine)
    if max_levels <= 1:
        return [{"level": 0, "assignments": flat}], "flat"
    hier = _hierarchy_from_leiden(nodes, edges, engine)
    if hier is not None:
        return [{"level": i, "assignments": a} for i, a in enumerate(hier[:max_levels])], "leiden"
    if (engine or "").lower() == "leiden":
        # Leiden requested but no hierarchy source → flat + global only (AD-13).
        return [{"level": 0, "assignments": flat}], "flat"
    levels = [{"level": 0, "assignments": flat}]
    prev = flat
    for lvl in range(1, max_levels):
        n_prev = len(set(prev.values()))
        if n_prev <= 1:
            break
        merged = _agglomerate(prev, edges, max(1, (n_prev + 1) // 2))
        levels.append({"level": lvl, "assignments": merged})
        prev = merged
    return levels, "agglomerated"


def _child_summaries(level_summaries, prev_by_comm, by_comm, cid):
    """Summaries of a parent's child communities (previous level), for the
    parent prompt. A child at level N-1 is any community whose members are a
    subset of the parent's members — derivable from the assignments alone, so
    the seam works for both the agglomerated and B6 Leiden hierarchies."""
    if prev_by_comm is None:
        return None
    parent_members = frozenset(by_comm[cid])
    out = []
    for child_cid, child_members in prev_by_comm.items():
        if not child_members:
            continue
        if parent_members.issuperset(child_members):
            s = level_summaries.get(_member_sha(child_members))
            if s is not None:
                out.append(s)
    return out or None


def _summary_from_disk(path: Path) -> CommunitySummary:
    """Rehydrate a CommunitySummary from a rendered page (parent contexts)."""
    from llm_wiki.core.frontmatter import parse_frontmatter

    text = path.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    title = (fm.get("title") if fm else None) or path.stem
    body = text.split("\n---", 2)[-1] if text.startswith("---") else text
    # Keep only the prose before any section headings (e.g. "## Members").
    lines = []
    for l in body.split("\n"):
        if l.startswith("#") and not l.startswith("# "):
            continue
        if l.startswith("##"):
            break
        lines.append(l)
    return CommunitySummary(title=title, summary="\n".join(lines).strip(),
                            key_entities=[])


def summarize_communities(
    wiki_root,
    max_communities: int | None = None,
    levels: int = 1,
    provider: str = "default",
    model=None,
    force: bool = False,
    dry_run: bool = False,
    timeout: int | None = 60,
    summarizer=None,
    engine: str | None = None,
    include_derived: bool = False,
) -> dict:
    """Summarize each community at each hierarchy level into first-class pages.

    Level 0 → ``L0-{sha}.md``, level N → ``L{level}-{sha}.md`` (parents
    summarize child summaries), root → ``global-summary.md``. Filenames are
    keyed on the member-set SHA only, and stale summary pages whose member set
    is no longer in the current partition are removed (AD-12). One call per
    community per level (AC#2), capped by ``--max-communities`` / ``--levels``
    (AC#5). Returns run stats.
    """
    from llm_wiki.core.atomic import atomic_write
    from llm_wiki.core.layout import discover_layout
    from llm_wiki.graph.suggest import load_pages

    levels = max(1, int(levels or 1))
    layout = discover_layout(wiki_root)
    wiki_dir = Path(layout.pages_dir)
    if not wiki_dir.is_dir():
        return {"communities": 0, "summarized": 0, "skipped": 0, "calls": 0,
                "written": 0, "failed": 0, "dry_run": dry_run, "removed": 0,
                "levels": 0, "hierarchy": "flat"}
    skip_files = frozenset(f"{stem}.md" for stem in layout.skip_stems)
    pages = load_pages(wiki_dir, skip_files)

    # Community detection and the hierarchy agglomeration must see only real
    # pages — summary pages are excluded from membership anyway, and letting
    # them shape the partition would distort merges (AD-12/AD-13).
    member_pages = {stem: v for stem, v in pages.items()
                    if (v[2] or {}).get("type") != "community-summary"}
    nodes, edges = _build_graph(member_pages)

    # --include-derived: opt-in layer inclusion, fail-closed on the NMI+modularity
    # gate (ADR-0027 §gate). Default (flag unset) never opens the layer.
    derived_gate = None
    if include_derived:
        from llm_wiki.graph import derived_edges as _de
        derived = _de.load_derived_edges(wiki_root)
        wiki_edges = [{"source": s, "target": t, "weight": 1} for s, t in edges]
        include, derived_gate = _de.should_include_derived(nodes, wiki_edges, derived)
        if include:
            # Derived edges are keyed by page stem — summarize's id space too.
            extra = [(e["source"], e["target"]) for e in derived
                     if e.get("source") in nodes and e.get("target") in nodes]
            edges = edges + [pair for pair in extra if pair not in edges]

    partitions, hierarchy = _partition_levels(nodes, edges, engine=engine,
                                              max_levels=levels)
    out_dir = wiki_dir / "communities"
    if summarizer is None:
        summarizer = _default_summarizer(provider, model, timeout)

    stats = {"communities": 0, "summarized": 0, "skipped": 0, "calls": 0,
             "written": 0, "failed": 0, "dry_run": dry_run, "removed": 0,
             "levels": len(partitions), "hierarchy": hierarchy}
    if derived_gate is not None:
        stats["derived_gate"] = derived_gate
    existing = _existing_summary_files(out_dir)  # member_sha → page paths
    current_shas: set[str] = set()
    level_summaries: dict[str, CommunitySummary] = {}  # sha → summary (all levels)
    top_level_member_ents: set[str] = set()
    top_level_summaries: list[CommunitySummary] = []
    top_level = partitions[-1]["level"]
    level0_comm_ids = []
    prev_by_comm = None

    for lvl_info in partitions:
        level = lvl_info["level"]
        assignments = lvl_info["assignments"]

        # Group members by community, ignoring community-summary pages themselves.
        by_comm: dict = {}
        for stem, cid in assignments.items():
            if stem in pages and (pages[stem][2] or {}).get("type") == "community-summary":
                continue
            by_comm.setdefault(cid, []).append(stem)
        comm_ids = sorted(by_comm, key=lambda c: (-len(by_comm[c]), c))
        if max_communities is not None:
            comm_ids = comm_ids[:max_communities]
        stats["communities"] += len(comm_ids)
        if level == 0:
            level0_comm_ids = comm_ids

        for cid in comm_ids:
            members = by_comm[cid]
            sha = _member_sha(members)
            current_shas.add(sha)
            if level == top_level:
                top_level_member_ents |= _member_entities(pages, members)
            if not force and sha in existing:
                stats["skipped"] += 1
                level_summaries[sha] = _summary_from_disk(existing[sha][0])
                continue
            if dry_run:
                continue

            children = _child_summaries(level_summaries, prev_by_comm, by_comm, cid)
            system, user = _build_prompt(nodes, pages, members, children)
            result = summarizer(system, user)
            stats["calls"] += 1
            if result is None:
                stats["failed"] += 1
                continue  # keep any prior summary; never write a partial page

            member_ents = _member_entities(pages, members)
            kept = _faithful_entities(result.key_entities, member_ents)
            page_md = _render_summary_page(result, cid, level, members, pages,
                                           nodes, kept, sha)
            out_dir.mkdir(parents=True, exist_ok=True)
            # Filename keyed on SHA only — the same member set maps to one
            # stable page regardless of title changes (AD-12).
            atomic_write(str(out_dir / f"L{level}-{sha}.md"), page_md)
            stats["summarized"] += 1
            stats["written"] += 1
            level_summaries[sha] = result
            if level == top_level:
                top_level_summaries.append(result)

        prev_by_comm = by_comm

    # Global root over the coarsest level's summaries (whole-wiki theme).
    if not dry_run and top_level_summaries:
        gsystem = ("Summarize the whole knowledge base from these community "
                   "summaries. Title it and give key_entities drawn only from them.")
        guser = "\n".join(f"- {p.title}: {p.summary}" for p in top_level_summaries)
        groot = summarizer(gsystem, guser)
        stats["calls"] += 1
        if groot is not None:
            # AD-9: the global reference is the union of REAL member entities —
            # never the raw (unfiltered) LLM key_entities of any summary.
            kept = _faithful_entities(groot.key_entities, top_level_member_ents)
            gmd = _render_summary_page(groot, -1, "global", [], pages, nodes,
                                       kept,
                                       _member_sha([str(cid) for cid in level0_comm_ids]))
            out_dir.mkdir(parents=True, exist_ok=True)
            atomic_write(str(out_dir / "global-summary.md"), gmd)
            stats["written"] += 1

    # AD-12: remove summary pages whose member set is no longer in the current
    # partition (membership drift or re-summarization would orphan them).
    if not dry_run and existing:
        for sha, paths in existing.items():
            if sha not in current_shas:
                for path in paths:
                    path.unlink()
                    stats["removed"] += 1

    return stats


def summary_faithfulness(summaries, member_entities_by_community) -> float:
    """Faithfulness rate across rendered summaries: the fraction of summaries
    whose ``key_entities`` are all members of their community (1.0 = perfect).

    ``summaries``: iterable of ``(community, key_entities)`` pairs or dicts
    with ``community``/``key_entities`` keys (e.g. parsed summary-page
    frontmatter). ``member_entities_by_community``: {community: member entity
    surface forms}. Entities are case-normalized; empty key_entities counts as
    faithful (nothing to hallucinate); no summaries → 1.0 (vacuously). Committed
    for B7's eval gate (LWM_030 AC#7).
    """
    from llm_wiki.graph.resolve import normalize

    n = 0
    faithful = 0
    for s in summaries:
        if isinstance(s, dict):
            cid = s.get("community")
            ents = s.get("key_entities") or []
        else:
            cid, ents = s
        members = {normalize(m) for m in member_entities_by_community.get(cid, [])}
        n += 1
        if all(normalize(e) in members for e in (ents or [])):
            faithful += 1
    return faithful / n if n else 1.0


def _existing_summary_files(out_dir: Path) -> "dict[str, list[Path]]":
    """Existing community-summary pages keyed by member-set SHA (for staleness
    and AD-12 orphan cleanup). Only files matching the ``L{level}-{sha}.md``
    naming pattern AND ``type: community-summary`` frontmatter are considered —
    unrelated pages in the directory are never touched. A member set may map to
    several files (same community at two levels) — all are returned."""
    from llm_wiki.core.frontmatter import parse_frontmatter

    found: dict[str, list[Path]] = {}
    if not out_dir.is_dir():
        return found
    for p in sorted(out_dir.glob("L*.md")):
        if not _SUMMARY_FILE_RE.match(p.name):
            continue
        fm = parse_frontmatter(p.read_text(encoding="utf-8"))
        if fm and fm.get("type") == "community-summary" and fm.get("member_sha"):
            found.setdefault(fm["member_sha"], []).append(p)
    return found


def _existing_member_shas(out_dir: Path) -> "set[str]":
    """Member-set SHAs of already-written community-summary pages (all levels)."""
    return set(_existing_summary_files(out_dir))


def _faithful_entities(candidates, member_ents_normalized) -> "list[str]":
    """Keep only key_entities whose normalized form is an actual member entity."""
    from llm_wiki.graph.resolve import normalize

    out = []
    for e in candidates or []:
        if normalize(e) in member_ents_normalized or e.lower() in member_ents_normalized:
            out.append(e)
    return out


def _render_summary_page(summary, cid, level, members, pages, nodes, key_entities, sha) -> str:
    updated = time.strftime("%Y-%m-%d")
    member_titles = [nodes.get(s, {}).get("label", s) for s in sorted(members) if s in pages]
    fm_members = ", ".join(f'"{t}"' for t in member_titles)
    fm_entities = ", ".join(f'"{e}"' for e in key_entities)
    body_links = "\n".join(f"- [[{t}]]" for t in member_titles)
    lines = [
        "---",
        f"title: {summary.title}",
        "type: community-summary",
        f"community: {cid}",
        f"level: {level}",
        f"members: [{fm_members}]",
        f"key_entities: [{fm_entities}]",
        f"member_sha: {sha}",
        "generated_by: summarize-communities",
        f"updated: {updated}",
        "---",
        "",
        f"# {summary.title}",
        "",
        summary.summary,
        "",
    ]
    if body_links:
        lines += ["## Members", "", body_links, ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="llm-wiki summarize-communities",
        description="Opt-in LLM community summaries as first-class pages (LWM_030).",
    )
    parser.add_argument("wiki_root")
    parser.add_argument("--max-communities", type=int, default=None)
    parser.add_argument("--levels", type=int, default=1,
                        help="Hierarchy depth (1 = flat communities + global root)")
    parser.add_argument("--provider", default="default")
    parser.add_argument("--model", default=None)
    parser.add_argument("--engine", default=None, help="community engine: louvain|leiden")
    parser.add_argument("--force", action="store_true", help="Regenerate unchanged communities")
    parser.add_argument("--dry-run", action="store_true", help="Plan only; no LLM calls, no writes")
    parser.add_argument("--include-derived", action="store_true",
                        help="Opt in to the derived-edge layer, fail-closed on the "
                             "NMI+modularity gate (ADR-0027 §gate)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    from llm_wiki.operation import OperationContext

    with OperationContext("summarize_communities", wiki_root=args.wiki_root,
                          inputs={"dry_run": args.dry_run, "force": args.force,
                                  "levels": args.levels}) as ctx:
        stats = summarize_communities(
            args.wiki_root, max_communities=args.max_communities, levels=args.levels,
            provider=args.provider, model=args.model, force=args.force,
            dry_run=args.dry_run, engine=args.engine,
            include_derived=args.include_derived,
        )
        ctx.succeed()

    if args.include_derived and isinstance(stats.get("derived_gate"), dict):
        g = stats["derived_gate"]
        verdict = "included" if g.get("included") else "refused (fail-closed)"
        print(f"Derived layer gate: {verdict} — {g.get('reason', 'no layer')}",
              file=sys.stderr)

    if args.json:
        import json
        print(json.dumps(stats, indent=2))
    elif args.dry_run:
        print(f"Plan: {stats['communities']} communities across {stats['levels']} level(s) → "
              f"~{stats['communities'] + 1} LLM calls (0 made, dry-run). No writes.")
    else:
        print(f"Summarized {stats['summarized']} communities "
              f"({stats['skipped']} unchanged, {stats['failed']} failed, "
              f"{stats['removed']} stale removed) across {stats['levels']} level(s) → communities/. "
              f"{stats['calls']} LLM call(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
