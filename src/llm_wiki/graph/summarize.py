#!/usr/bin/env python3
"""summarize.py — Opt-in community summaries (LWM_030). See ADR-0009 / ADR-0025.

``llm-wiki summarize-communities <wiki>`` makes one structured LLM call per
community (via ``providers/registry.call_llm_structured``, agent-native ``$0.00``
default) to turn anonymous integer communities into readable themes, then writes
each as a first-class ``type: community-summary`` page under ``communities/`` with
``[[member]]`` wikilinks — so summaries become normal, searchable graph nodes.

Strictly opt-in: when the operation is not run the wiki is byte-identical.
Cost-bounded (``--dry-run`` estimates with zero calls; unchanged communities skip
via a member-set SHA; ``--max-communities`` caps work). Faithfulness-gated:
``key_entities`` are filtered to the community's actual member entities. The
summarizer is injectable for deterministic offline tests.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

from pydantic import BaseModel, Field

EXCERPT_CHARS = 280  # per-member prompt budget (char proxy keeps base install pure)


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


def _slug(text: str) -> str:
    import re
    s = re.sub(r"[^\w]+", "-", text.lower()).strip("-")
    return s[:40] or "community"


def _default_summarizer(provider: str, model, timeout):
    from llm_wiki.providers.registry import call_llm_structured

    def _fn(system: str, user: str):
        return call_llm_structured(system, user, CommunitySummary,
                                   provider=provider, model=model, total_timeout=timeout)
    return _fn


def _build_prompt(nodes, pages, stems) -> "tuple[str, str]":
    system = (
        "You summarize a cluster of related wiki pages. Produce a concise title, "
        "a 2-4 sentence summary, and key_entities. Use ONLY the provided member "
        "content; draw key_entities ONLY from the members shown."
    )
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


def summarize_communities(
    wiki_root,
    max_communities: int | None = None,
    provider: str = "default",
    model=None,
    force: bool = False,
    dry_run: bool = False,
    timeout: int | None = 60,
    summarizer=None,
    engine: str | None = None,
) -> dict:
    """Summarize each community into a first-class page. Returns run stats."""
    from llm_wiki.core.atomic import atomic_write
    from llm_wiki.core.layout import discover_layout
    from llm_wiki.graph.insights import detect_communities_for_insights
    from llm_wiki.graph.suggest import load_pages

    layout = discover_layout(wiki_root)
    wiki_dir = Path(layout.pages_dir)
    if not wiki_dir.is_dir():
        return {"communities": 0, "summarized": 0, "skipped": 0, "calls": 0, "written": 0}
    skip_files = frozenset(f"{stem}.md" for stem in layout.skip_stems)
    pages = load_pages(wiki_dir, skip_files)

    nodes, edges = _build_graph(pages)
    assignments = detect_communities_for_insights(nodes, edges, engine=engine)

    # Group members by community, ignoring community-summary pages themselves.
    by_comm: dict = {}
    for stem, cid in assignments.items():
        if stem in pages and (pages[stem][2] or {}).get("type") == "community-summary":
            continue
        by_comm.setdefault(cid, []).append(stem)
    comm_ids = sorted(by_comm, key=lambda c: (-len(by_comm[c]), c))
    if max_communities is not None:
        comm_ids = comm_ids[:max_communities]

    out_dir = wiki_dir / "communities"
    if summarizer is None:
        summarizer = _default_summarizer(provider, model, timeout)

    stats = {"communities": len(comm_ids), "summarized": 0, "skipped": 0,
             "calls": 0, "written": 0, "failed": 0, "dry_run": dry_run}
    produced: list[CommunitySummary] = []
    # Staleness is keyed on the member-set SHA (stable), not the volatile integer
    # community id — summary pages become graph nodes and would renumber ids.
    existing_shas = _existing_member_shas(out_dir)

    for cid in comm_ids:
        members = by_comm[cid]
        sha = _member_sha(members)
        if not force and sha in existing_shas:
            stats["skipped"] += 1
            continue
        if dry_run:
            continue

        system, user = _build_prompt(nodes, pages, members)
        result = summarizer(system, user)
        stats["calls"] += 1
        if result is None:
            stats["failed"] += 1
            continue  # keep any prior summary; never write a partial page

        member_ents = _member_entities(pages, members)
        kept = _faithful_entities(result.key_entities, member_ents)
        produced.append(result)
        page_md = _render_summary_page(result, cid, 0, members, pages, nodes, kept, sha)
        out_dir.mkdir(parents=True, exist_ok=True)
        # Filename keyed on SHA so the same member set maps to one stable page.
        atomic_write(str(out_dir / f"L0-{sha}-{_slug(result.title)}.md"), page_md)
        stats["summarized"] += 1
        stats["written"] += 1

    # Global root summary over the per-community summaries (whole-wiki theme).
    if not dry_run and produced:
        gsystem = ("Summarize the whole knowledge base from these community "
                   "summaries. Title it and give key_entities drawn only from them.")
        guser = "\n".join(f"- {p.title}: {p.summary}" for p in produced)
        groot = summarizer(gsystem, guser)
        stats["calls"] += 1
        if groot is not None:
            all_ents = set()
            for p in produced:
                all_ents.update(p.key_entities)
            kept = _faithful_entities(groot.key_entities, {e.lower() for e in all_ents})
            gmd = _render_summary_page(groot, -1, "global",
                                       [], pages, nodes, kept, _member_sha([str(cid) for cid in comm_ids]))
            out_dir.mkdir(parents=True, exist_ok=True)
            atomic_write(str(out_dir / "global-summary.md"), gmd)
            stats["written"] += 1

    return stats


def _existing_member_shas(out_dir: Path) -> "set[str]":
    """Member-set SHAs of already-written community-summary pages (for staleness)."""
    from llm_wiki.core.frontmatter import parse_frontmatter

    shas: set[str] = set()
    if not out_dir.is_dir():
        return shas
    for p in out_dir.glob("L0-*.md"):
        fm = parse_frontmatter(p.read_text(encoding="utf-8"))
        if fm and fm.get("member_sha"):
            shas.add(fm["member_sha"])
    return shas


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
    parser.add_argument("--provider", default="default")
    parser.add_argument("--model", default=None)
    parser.add_argument("--engine", default=None, help="community engine: louvain|leiden")
    parser.add_argument("--force", action="store_true", help="Regenerate unchanged communities")
    parser.add_argument("--dry-run", action="store_true", help="Plan only; no LLM calls, no writes")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    from llm_wiki.operation import OperationContext

    with OperationContext("summarize_communities", wiki_root=args.wiki_root,
                          inputs={"dry_run": args.dry_run, "force": args.force}) as ctx:
        stats = summarize_communities(
            args.wiki_root, max_communities=args.max_communities,
            provider=args.provider, model=args.model, force=args.force,
            dry_run=args.dry_run, engine=args.engine,
        )
        ctx.succeed()

    if args.json:
        import json
        print(json.dumps(stats, indent=2))
    elif args.dry_run:
        print(f"Plan: {stats['communities']} communities → "
              f"~{stats['communities'] + 1} LLM calls (0 made, dry-run). No writes.")
    else:
        print(f"Summarized {stats['summarized']} communities "
              f"({stats['skipped']} unchanged, {stats['failed']} failed) → communities/. "
              f"{stats['calls']} LLM call(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
