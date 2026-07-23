"""wikilinks.py — Wikilink regex and helpers for LLM Wiki."""

import re
from pathlib import Path


WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")


def extract_wikilinks(text: str) -> list[str]:
    return WIKILINK_RE.findall(text)


def load_pages(wiki_dir: Path) -> dict[str, Path]:
    """Build a lookup dict mapping stem -> Path and relative-path -> Path."""
    pages: dict[str, Path] = {}
    for p in wiki_dir.rglob("*.md"):
        pages[p.stem] = p
        rel = p.relative_to(wiki_dir)
        pages[str(rel.with_suffix(""))] = p
    return pages
