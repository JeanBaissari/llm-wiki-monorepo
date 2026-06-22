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
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from discover import discover_layout


WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
HEADING_RE = re.compile(r"^#{2,3}\s+(.+)$", re.MULTILINE)
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
SKIP_FILES = frozenset({"index.md", "log.md", "SCHEMA.md"})


def parse_frontmatter(text: str) -> dict | None:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    result = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            if not inner:
                result[key] = []
            else:
                result[key] = [x.strip().strip("\"'") for x in inner.split(",") if x.strip()]
        elif val.startswith(('"', "'")):
            result[key] = val[1:-1]
        else:
            result[key] = val
    return result


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


def build_entity_registry(pages: dict[str, tuple[Path, str, dict | None]]) -> dict:
    pages_by_stem_lower = {}
    pages_by_title_lower = {}
    for stem, (_, _, fm) in pages.items():
        pages_by_stem_lower[stem.lower()] = stem
        title = fm.get("title", stem) if fm else stem
        pages_by_title_lower[title.lower()] = (stem, title)

    entity_candidates = set()
    for stem, (_, text, _) in pages.items():
        for ent in extract_entities(text):
            entity_candidates.add(ent.strip())

    registry = {}
    for entity in entity_candidates:
        key = entity.lower()
        target_stem = pages_by_title_lower.get(key, (None, None))[0]
        if target_stem is None:
            target_stem = pages_by_stem_lower.get(key)
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
    pages: dict, registry: dict, wiki_dir: Path, limit: int, min_confidence: float
) -> list[dict]:
    total = len(pages)
    if total == 0:
        return []

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
            source_path.write_text(new_text, encoding="utf-8")
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
    args = parser.parse_args()

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

    registry = build_entity_registry(pages)
    if not registry:
        print("No entities found to suggest links for.", file=sys.stderr)
        return 0

    suggestions = generate_suggestions(
        pages, registry, wiki_dir, args.limit, args.min_confidence
    )

    if args.apply:
        modified = apply_suggestions(pages, suggestions)
        print(f"Applied {len(suggestions)} suggestions across {modified} page(s)")
    elif args.format == "json":
        output_json(suggestions)
    else:
        output_text(suggestions, layout.root)

    return 0


if __name__ == "__main__":
    sys.exit(main())
