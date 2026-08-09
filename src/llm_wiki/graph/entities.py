#!/usr/bin/env python3
"""entities.py — CLI for reversible entity resolution (LWM_025).

    llm-wiki entities resolve  <wiki-root> [--threshold 0.85] [--json]
    llm-wiki entities list     <wiki-root> [--json]
    llm-wiki entities unmerge  <wiki-root> <alias>

`resolve` gathers entity candidates from the wiki (via the active extractor —
regex by default, GLiNER under the optional `[ner]` extra), runs the two-signal
resolution pipeline, and appends merge events to the git-tracked
`.llm-wiki/entities/aliases.jsonl` source of truth (deriving the `.index/wiki.db`
lookup cache). `unmerge` appends an inverse event — reversibility is a file
operation, never a schema migration. No page prose is ever rewritten.

Exit codes: 0 = success · 1 = nothing to do / not found · 2 = usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from llm_wiki.core.layout import discover_layout
from llm_wiki.graph import alias_store
from llm_wiki.graph.extract import get_extractor
from llm_wiki.graph.resolve import RESOLVER_ID, apply_resolution, unmerge


def _gather_candidates(wiki_root: str) -> list[str]:
    """Collect deduped entity surface forms from every page via the active extractor."""
    from llm_wiki.graph.extract import RegexExtractor, get_extractor
    from llm_wiki.graph.suggest import load_pages

    layout = discover_layout(wiki_root)
    wiki_dir = Path(layout.pages_dir)
    if not wiki_dir.is_dir():
        return []
    skip_files = frozenset(f"{stem}.md" for stem in layout.skip_stems)
    pages = load_pages(wiki_dir, skip_files)

    extractor = get_extractor()
    regex_fallback = RegexExtractor()
    seen: dict[str, None] = {}
    for _stem, (_p, text, _fm) in pages.items():
        try:
            surfaces = extractor.extract_surfaces(text)
        except Exception:
            # GLiNERExtractor never raises (AD-10), but any extractor that does
            # degrades to the regex path for that page rather than crashing.
            surfaces = regex_fallback.extract_surfaces(text)
        for surface in surfaces:
            surface = surface.strip()
            if surface:
                seen.setdefault(surface, None)
    return list(seen)


def _cmd_resolve(args) -> int:
    from llm_wiki.operation import OperationContext
    from llm_wiki.semantic.embedder import get_embedder

    candidates = _gather_candidates(args.wiki_root)
    if len(candidates) < 2:
        print("No entity candidates to resolve.", file=sys.stderr)
        return 1

    embedder = get_embedder()  # None → string-similarity-only (raised threshold)
    with OperationContext(
        "entities.resolve",
        wiki_root=args.wiki_root,
        inputs={"threshold": args.threshold, "candidates": len(candidates)},
    ) as ctx:
        stats = apply_resolution(
            args.wiki_root, candidates, embedder=embedder, threshold=args.threshold
        )
        for audit_path in stats.get("audit_paths", []):
            ctx.add_artifact_ref("audit_ids", audit_path)
        ctx.succeed()

    extractor = get_extractor().name
    if args.json:
        print(json.dumps({**stats, "extractor": extractor}, indent=2))
    else:
        print(
            f"Resolved {len(candidates)} candidates → merged {stats['merged']} "
            f"aliases into {stats['canonicals']} canonical(s) "
            f"[extractor={extractor}, signal="
            f"{'embedding+string' if embedder else 'string-only'}]"
        )
    return 0


def _cmd_list(args) -> int:
    events = alias_store.read_events(args.wiki_root)
    state = alias_store.resolve_state(events)
    labels = alias_store.canonical_labels(events)
    if not state:
        print("No resolved entities.", file=sys.stderr)
        return 1

    by_canon: dict[str, list[str]] = {}
    for alias, cid in state.items():
        by_canon.setdefault(cid, []).append(alias)

    if args.json:
        print(json.dumps(
            {cid: {"label": labels.get(cid, cid), "aliases": sorted(al)}
             for cid, al in by_canon.items()},
            indent=2, sort_keys=True,
        ))
    else:
        for cid in sorted(by_canon):
            print(f"{labels.get(cid, cid)}  ({cid})")
            for alias in sorted(by_canon[cid]):
                print(f"  ← {alias}")
    return 0


def _cmd_unmerge(args) -> int:
    if unmerge(args.wiki_root, args.alias):
        print(f"Unmerged alias '{args.alias}'.")
        return 0
    print(f"Alias '{args.alias}' is not resolved; nothing to unmerge.", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="llm-wiki entities",
        description="Reversible entity resolution (canonical↔alias). "
                    f"resolver={RESOLVER_ID}",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    p_resolve = sub.add_parser("resolve", help="Resolve entity candidates into canonicals")
    p_resolve.add_argument("wiki_root", help="Path to the wiki root directory")
    p_resolve.add_argument("--threshold", type=float, default=0.85,
                           help="Merge threshold (default: 0.85)")
    p_resolve.add_argument("--json", action="store_true", help="JSON output")
    p_resolve.set_defaults(func=_cmd_resolve)

    p_list = sub.add_parser("list", help="List canonical entities and their aliases")
    p_list.add_argument("wiki_root", help="Path to the wiki root directory")
    p_list.add_argument("--json", action="store_true", help="JSON output")
    p_list.set_defaults(func=_cmd_list)

    p_unmerge = sub.add_parser("unmerge", help="Reverse a merge for one alias")
    p_unmerge.add_argument("wiki_root", help="Path to the wiki root directory")
    p_unmerge.add_argument("alias", help="Alias surface form to unmerge")
    p_unmerge.set_defaults(func=_cmd_unmerge)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
