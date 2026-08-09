#!/usr/bin/env python3
"""link_suggest.py — Suggest missing wikilinks in an LLM Wiki.

Reads all wiki pages, extracts entity/concept names from frontmatter
and headings, finds pages that mention the same entities but don't
link to each other, then suggests wikilinks.

Usage:
    python3 link_suggest.py <wiki-root>
    python3 link_suggest.py <wiki-root> --apply
    python3 link_suggest.py <wiki-root> --limit 10 --min-confidence 0.5
    python3 link_suggest.py <wiki-root> --format json

Exit codes:
    0 — run completed successfully
    1 — no wiki/ directory found
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


from llm_wiki.core.layout import discover_layout
from llm_wiki.core.wikilinks import WIKILINK_RE
from llm_wiki.core.frontmatter import FRONTMATTER_RE, parse_frontmatter
HEADING_RE = re.compile(r"^#{2,3}\s+(.+)$", re.MULTILINE)
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
SKIP_FILES = frozenset({"index.md", "log.md", "SCHEMA.md"})


@dataclass
class InvertedIndex:
    """Dual-map inverted index: entity→{page_stems}, page_stem→{entities}."""
    entity_to_pages: dict = field(default_factory=dict)
    page_to_entities: dict = field(default_factory=dict)

    @property
    def entity_count(self) -> int:
        return len(self.entity_to_pages)


def build_inverted_index(pages, registry=None) -> InvertedIndex:
    """Build an InvertedIndex from pages dict and optional entity registry."""
    fwd, rev = defaultdict(set), {}
    keys = set(registry.keys()) if registry else None
    for stem, (_, text, _) in pages.items():
        clean = text_without_wikilinks(text).lower()
        rev.setdefault(stem, set())
        if keys:
            for k in keys:
                if k in clean:
                    fwd[k].add(stem)
                    rev[stem].add(k)
    return InvertedIndex(entity_to_pages=dict(fwd), page_to_entities=rev)





def extract_entities(text: str) -> list[str]:
    fm = parse_frontmatter(text)
    entities = []
    if fm and "title" in fm and fm["title"]:
        entities.append(fm["title"])
    for m in HEADING_RE.finditer(text):
        entities.append(m.group(1).strip())
    for m in BOLD_RE.finditer(text):
        entities.append(m.group(1).strip())
    return entities


def text_without_wikilinks(text: str) -> str:
    return WIKILINK_RE.sub(" ", text)


def entity_pattern(entity: str) -> re.Pattern:
    escaped = re.escape(entity)
    if entity and entity[0].isalnum():
        escaped = r"\b" + escaped
    if entity and entity[-1].isalnum():
        escaped = escaped + r"\b"
    return re.compile(escaped, re.IGNORECASE)


def first_outside_wikilink(text: str, entity: str) -> int | None:
    pat = entity_pattern(entity)
    link_spans = [(m.start(), m.end()) for m in WIKILINK_RE.finditer(text)]
    for m in pat.finditer(text):
        pos = m.start()
        if not any(ls <= pos < le for ls, le in link_spans):
            return pos
    return None


def load_pages(wiki_dir: Path, skip_files: frozenset = SKIP_FILES) -> dict[str, tuple[Path, str, dict | None]]:
    pages = {}
    for p in sorted(wiki_dir.rglob("*.md")):
        if p.name in skip_files:
            continue
        rel = p.relative_to(wiki_dir)
        if any(part.startswith(".") or part == "node_modules" for part in rel.parts):
            continue
        text = p.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        pages[p.stem] = (p, text, fm)
    return pages


def build_entity_registry(
    pages: dict[str, tuple[Path, str, dict | None]],
    alias_targets: dict[str, str] | None = None,
) -> dict:
    """Map entity surface forms to their target page.

    ``alias_targets`` (``{alias_surface -> canonical_label}``, from the LWM_025
    resolution store) routes a mention of an alias to the canonical entity's page
    even when the alias itself matches no page title. It is empty by default, so
    the lexical path is byte-identical until ``entities resolve`` has run.
    """
    pages_by_stem_lower = {}
    pages_by_title_lower = {}
    pages_by_norm = {}  # normalized title/stem -> (stem, title), for alias routing
    for stem, (_, _, fm) in pages.items():
        pages_by_stem_lower[stem.lower()] = stem
        title = fm.get("title", stem) if fm else stem
        pages_by_title_lower[title.lower()] = (stem, title)
        if alias_targets:
            from llm_wiki.graph.resolve import normalize
            pages_by_norm.setdefault(normalize(title), (stem, title))
            pages_by_norm.setdefault(normalize(stem), (stem, title))

    entity_candidates = set()
    for stem, (_, text, _) in pages.items():
        for ent in extract_entities(text):
            entity_candidates.add(ent.strip())
    # Alias surfaces AND canonical labels are also candidates: a mention of any
    # variant ("gpt-4" / "GPT 4") should link to the canonical entity's page.
    if alias_targets:
        for alias, label in alias_targets.items():
            if alias.strip():
                entity_candidates.add(alias.strip())
            if label.strip():
                entity_candidates.add(label.strip())

    registry = {}
    for entity in entity_candidates:
        key = entity.lower()

        # Direct title/stem match (the byte-identical v0.4.0 path).
        target_stem = pages_by_title_lower.get(key, (None, None))[0]
        if target_stem is None:
            target_stem = pages_by_stem_lower.get(key)

        # Alias routing: if this surface is a known variant, resolve it to the
        # page whose normalized title/stem matches the canonical (LWM_025).
        if target_stem is None and alias_targets:
            from llm_wiki.graph.resolve import normalize
            canon_label = alias_targets.get(entity, entity)
            hit = pages_by_norm.get(normalize(canon_label)) or pages_by_norm.get(normalize(entity))
            if hit is not None:
                target_stem = hit[0]

        if target_stem is None:
            continue
        _, _, fm = pages[target_stem]
        target_title = fm.get("title", target_stem) if fm else target_stem
        target_type = fm.get("type", "") if fm else ""
        registry[key] = {
            "original": entity,
            "target_stem": target_stem,
            "target_title": target_title,
            "target_type": target_type,
        }

    return registry


def generate_suggestions(
    pages: dict, registry: dict, wiki_dir: Path, limit: int, min_confidence: float,
    inverted: Optional[InvertedIndex] = None,
) -> list[dict]:
    total = len(pages)
    if total == 0:
        return []

    if inverted is not None:
        entity_page_count: Counter = Counter({k: len(v) for k, v in inverted.entity_to_pages.items()})
    else:
        entity_page_count: Counter = Counter()
        for stem, (_, text, _) in pages.items():
            clean = text_without_wikilinks(text).lower()
            for key in registry:
                if key in clean:
                    entity_page_count[key] += 1

    suggestions = []

    for source_stem, (source_path, source_text, source_fm) in pages.items():
        source_title = source_fm.get("title", source_stem) if source_fm else source_stem
        source_type = source_fm.get("type", "") if source_fm else ""
        source_rel = source_path.relative_to(wiki_dir)

        clean = text_without_wikilinks(source_text)

        existing_stems = set()
        for link in WIKILINK_RE.findall(source_text):
            existing_stems.add(link.strip().lower())
            existing_stems.add(Path(link.strip()).stem.lower())

        for key, entry in registry.items():
            target_stem = entry["target_stem"]
            if target_stem == source_stem:
                continue
            if target_stem.lower() in existing_stems:
                continue

            pat = entity_pattern(entry["original"])
            matches = list(pat.finditer(clean))
            if not matches:
                continue

            count = len(matches)
            doc_len = len(clean)
            early_threshold = doc_len * 0.2
            early_count = sum(1 for m in matches if m.start() < early_threshold)

            freq_score = min(count, 3) / 3.0
            pos_mult = 1.5 if early_count > 0 else 1.0
            type_bonus = 0.2 if source_type and entry["target_type"] and source_type == entry["target_type"] else 0.0
            common_pages = entity_page_count.get(key, 1)
            common_penalty = min(common_pages / total * 2, 0.5) if total > 0 else 0.0

            score = freq_score * pos_mult + type_bonus - common_penalty
            score = max(0.0, min(1.0, score))

            if score < min_confidence:
                continue

            reasons = []
            reasons.append(f'"{entry["original"]}" mentioned {count}x')
            if early_count > 0:
                reasons.append("early in doc")
            if type_bonus > 0:
                reasons.append(f"same type ({source_type})")
            if common_pages > 1:
                reasons.append(f"in {common_pages} pages")

            target_path, _, _ = pages[target_stem]
            target_rel = target_path.relative_to(wiki_dir)

            suggestions.append({
                "source": str(source_rel),
                "source_stem": source_stem,
                "source_title": source_title,
                "source_type": source_type,
                "target": str(target_rel),
                "target_stem": target_stem,
                "target_title": entry["target_title"],
                "target_type": entry["target_type"],
                "entity": entry["original"],
                "score": round(score, 3),
                "reason": "; ".join(reasons),
            })

    suggestions.sort(key=lambda x: -x["score"])
    return suggestions[:limit]


def apply_suggestions(pages: dict, suggestions: list[dict]) -> int:
    by_source: dict[str, list[dict]] = defaultdict(list)
    for s in suggestions:
        by_source[s["source_stem"]].append(s)

    modified = 0
    for source_stem, page_suggestions in by_source.items():
        source_path, source_text, _ = pages[source_stem]
        replacements = []

        for s in page_suggestions:
            entity = s["entity"]
            target_title = s["target_title"]
            pos = first_outside_wikilink(source_text, entity)
            if pos is not None:
                pat = entity_pattern(entity)
                m = pat.search(source_text, pos)
                if m:
                    matched_text = m.group()
                    link = f"[[{target_title}|{matched_text}]]"
                    if matched_text.lower() == target_title.lower():
                        link = f"[[{target_title}]]"
                    replacements.append((m.start(), m.end(), link))

        if not replacements:
            continue

        replacements.sort(key=lambda x: -x[0])
        new_text = source_text
        for start, end, link in replacements:
            new_text = new_text[:start] + link + new_text[end:]

        if new_text != source_text:
            from llm_wiki.core.atomic import atomic_write
            atomic_write(str(source_path), new_text)
            modified += 1

    return modified


def output_text(suggestions: list[dict], wiki_root: str) -> None:
    print(f"# Link Suggestions for {wiki_root}")
    if not suggestions:
        print("## No suggestions found")
        return
    print("## Top Suggestions")
    print("Rank | Source Page | Target Page | Score | Reason")
    for i, s in enumerate(suggestions, 1):
        print(f"{i} | {s['source']} | {s['target']} | {s['score']} | {s['reason']}")


def output_json(suggestions: list[dict]) -> None:
    out = []
    for i, s in enumerate(suggestions, 1):
        out.append({
            "rank": i,
            "source": s["source"],
            "source_title": s["source_title"],
            "source_type": s["source_type"],
            "target": s["target"],
            "target_title": s["target_title"],
            "target_type": s["target_type"],
            "entity": s["entity"],
            "score": s["score"],
            "reason": s["reason"],
        })
    print(json.dumps(out, indent=2))


def _apply_semantic(args, results, is_auto_appliable) -> int:
    """Apply only auto-appliable (two-signal) related notes, and only where the

    target entity is actually mentioned in the source prose — reusing the
    surface-preserving `apply_suggestions` machinery. Static-embedding-only rows
    are never applied (ADR-0021/0024). Resolved aliases of a target also count as
    mentions, which is what the LWM_025 resolution store unblocks.
    """
    from llm_wiki.graph.resolve import alias_targets, normalize
    from llm_wiki.operation import OperationContext

    layout = discover_layout(args.wiki_root)
    wiki_dir = Path(layout.pages_dir)
    if not wiki_dir.is_dir():
        print("Error: pages directory not found", file=sys.stderr)
        return 1
    skip_files = frozenset(f"{stem}.md" for stem in layout.skip_stems)
    pages = load_pages(wiki_dir, skip_files)
    if args.page not in pages:
        print(f"Source page '{args.page}' not found", file=sys.stderr)
        return 1

    # Mirror build_entity_registry: resolve a canonical LABEL to the page whose
    # normalized title/stem it matches — the label ("GPT 4") can differ from the
    # page title ("GPT-4") beyond case, so aliases are keyed by normalize(title).
    pages_by_norm: dict[str, tuple[str, str]] = {}
    for stem, (_, _, fm) in pages.items():
        title = fm.get("title", stem) if fm else stem
        pages_by_norm.setdefault(normalize(title), (stem, title))
        pages_by_norm.setdefault(normalize(stem), (stem, title))

    canon_to_aliases: dict[str, list[str]] = defaultdict(list)
    for alias, label in alias_targets(args.wiki_root).items():
        hit = pages_by_norm.get(normalize(label))
        title_key = normalize(hit[1]) if hit else normalize(label)
        # the canonical LABEL is a real mention surface too (it appeared in wiki
        # prose as a candidate), mirroring build_entity_registry's label routing
        canon_to_aliases[title_key].extend([alias, label])

    pseudo: list[dict] = []
    for r in results:
        if not is_auto_appliable(r):
            continue
        target_stem = r["target_stem"]
        if target_stem not in pages or target_stem == args.page:
            continue
        _, _, fm = pages[target_stem]
        target_title = fm.get("title", target_stem) if fm else target_stem
        surfaces = [target_title] + canon_to_aliases.get(normalize(target_title), [])
        # Dedupe case-insensitively: the title ("GPT-4") and an alias ("gpt-4")
        # match the same spans under entity_pattern's IGNORECASE — applying both
        # would corrupt the page with overlapping replacements.
        seen: set[str] = set()
        surfaces = [s for s in surfaces if not (s.lower() in seen or seen.add(s.lower()))]
        for surface in surfaces:
            pseudo.append({
                "source_stem": args.page,
                "entity": surface,
                "target_title": target_title,
            })

    if not pseudo:
        print("No auto-appliable related notes mentioned in prose to apply.")
        return 0

    with OperationContext("link_suggest.semantic_apply", wiki_root=args.wiki_root,
                          inputs={"page": args.page, "limit": args.limit}) as ctx:
        modified = apply_suggestions(pages, pseudo)
        print(f"Applied auto-appliable related links across {modified} page(s)")
        ctx.succeed()
    return 0


def _run_semantic(args) -> int:
    """`link-suggest --semantic --page <stem>` — related notes.

    Fuses embedding + Personalized PageRank + lexical signals (LWM_021); falls
    back to PPR+lexical when the [semantic] extra is absent. `--apply` (LWM_025
    unblock) applies only auto-appliable (two-signal) rows whose target entity is
    actually mentioned in prose; static-embedding-only rows stay suggest-only and
    each row is tagged with which it is (ADR-0021).
    """
    if not args.page:
        print("--semantic requires --page <stem>", file=sys.stderr)
        return 2
    from llm_wiki.semantic.embedder import get_embedder
    from llm_wiki.semantic.linking import is_auto_appliable, semantic_related

    results = semantic_related(
        args.wiki_root, args.page, args.limit, embedder=get_embedder()
    )
    if args.apply:
        return _apply_semantic(args, results, is_auto_appliable)
    if args.format == "json":
        print(json.dumps(
            [{**r, "auto_appliable": is_auto_appliable(r)} for r in results],
            indent=2,
        ))
    else:
        print(f"# Semantic related notes for [[{args.page}]]")
        if not results:
            print("No related notes found.")
        for r in results:
            tag = "auto-appliable" if is_auto_appliable(r) else "suggest-only"
            print(f"{r['rank']}. {r['target_stem']}  "
                  f"signals={','.join(r['signals'])}  [{tag}]")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Suggest missing wikilinks in an LLM Wiki."
    )
    parser.add_argument("wiki_root", help="Path to the wiki root directory")
    parser.add_argument("--apply", action="store_true",
                        help="Apply suggestions by adding wikilinks to pages")
    parser.add_argument("--limit", type=int, default=20,
                        help="Maximum number of suggestions to show (default: 20)")
    parser.add_argument("--min-confidence", type=float, default=0.3,
                        help="Minimum confidence score 0.0-1.0 (default: 0.3)")
    parser.add_argument("--format", choices=["text", "json"], default="text",
                        help="Output format (default: text)")
    parser.add_argument("--semantic", action="store_true",
                        help="Semantic related-notes (embedding + PageRank + lexical, "
                             "fused via RRF); requires --page. Suggest-only.")
    parser.add_argument("--page", default=None,
                        help="Source page stem for --semantic mode")
    parser.add_argument("--resolve-entities", action="store_true",
                        help="Route alias mentions to their canonical page using "
                             "the LWM_025 resolution store (.llm-wiki/entities/). "
                             "No-op until `entities resolve` has run.")
    args = parser.parse_args()

    if args.semantic:
        return _run_semantic(args)

    layout = discover_layout(args.wiki_root)
    wiki_dir = Path(layout.pages_dir)
    if not wiki_dir.is_dir():
        print(f"Error: pages directory not found", file=sys.stderr)
        return 1

    skip_files = frozenset(f"{stem}.md" for stem in layout.skip_stems)
    pages = load_pages(wiki_dir, skip_files)
    if not pages:
        print("No wiki pages found.", file=sys.stderr)
        return 0

    alias_map = None
    if args.resolve_entities:
        from llm_wiki.graph.resolve import alias_targets
        alias_map = alias_targets(args.wiki_root) or None
    registry = build_entity_registry(pages, alias_targets=alias_map)
    if not registry:
        print("No entities found to suggest links for.", file=sys.stderr)
        return 0

    suggestions = generate_suggestions(
        pages, registry, wiki_dir, args.limit, args.min_confidence
    )

    if args.apply:
        from llm_wiki.operation import OperationContext
        with OperationContext("link_suggest.apply", wiki_root=args.wiki_root,
                               inputs={"limit": args.limit, "min_confidence": args.min_confidence}) as ctx:
            modified = apply_suggestions(pages, suggestions)
            print(f"Applied {len(suggestions)} suggestions across {modified} page(s)")
            ctx.succeed()
    elif args.format == "json":
        output_json(suggestions)
    else:
        output_text(suggestions, layout.root)

    return 0


if __name__ == "__main__":
    sys.exit(main())
