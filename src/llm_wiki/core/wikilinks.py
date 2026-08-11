"""wikilinks.py — Wikilink regex and helpers for LLM Wiki."""

import os
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
        # Forward slashes on every platform: wikilinks are authored with "/"
        # and str(Path) yields backslashes on Windows, which would make every
        # path-style link dead. Mirrors skill/scripts/validate_fixtures.py.
        pages[str(rel.with_suffix("")).replace(os.sep, "/")] = p
    return pages
