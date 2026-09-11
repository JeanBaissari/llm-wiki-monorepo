#!/usr/bin/env python3
"""Docs link checker — validates relative links and anchors in tracked Markdown.

Scans the repository's documentation surfaces (root docs, docs/, skill/, and
package READMEs) and verifies:
  * every relative link target exists on disk;
  * every ``#anchor`` (in-file or cross-file) matches a real heading slug.

Wiki content, templates, fixtures, and generated demo wikis are excluded.
External URLs are not fetched (the check is offline); only their presence in a
link is required.

Exit codes: 0 = clean, 1 = issues found.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_PREFIXES = (
    "wiki/",
    "tests/fixtures/",
    "templates/",
    "src/llm_wiki/wiki/demo_wiki/",
    "graph-engine/test/fixtures/",
    "node_modules/",
    "dist/",
    "build/",
    ".audit/",
)

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
FENCE_RE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)


def slugify(heading: str) -> str:
    """GitHub-style slug: lowercase, strip punctuation, spaces -> hyphens.

    Whitespace runs are NOT collapsed, matching GitHub's slugger: a removed
    punctuation character between two spaces (" & " -> "  ") yields a double
    hyphen in the anchor, e.g. ``#10-backup--recovery``.
    """
    text = re.sub(r"[^\w\s-]", "", heading.strip().lower())
    return re.sub(r"\s", "-", text)


def _doc_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "*.md"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        files = [REPO_ROOT / line for line in out.split() if line]
    except (subprocess.CalledProcessError, FileNotFoundError):
        files = sorted(REPO_ROOT.rglob("*.md"))
    return [
        f
        for f in files
        if f.exists()
        and not any(f.relative_to(REPO_ROOT).as_posix().startswith(p) for p in EXCLUDE_PREFIXES)
    ]


def _headings(text: str) -> set[str]:
    return {slugify(m.group(2)) for m in HEADING_RE.finditer(text)}


def check_file(path: Path) -> list[str]:
    issues: list[str] = []
    rel = path.relative_to(REPO_ROOT).as_posix()
    text = FENCE_RE.sub("", path.read_text(encoding="utf-8", errors="replace"))
    own_headings = _headings(path.read_text(encoding="utf-8", errors="replace"))

    for match in LINK_RE.finditer(text):
        target = match.group(1).strip()
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        if "<" in target and ">" in target:  # template placeholder
            continue

        if target.startswith("#"):
            anchor = target[1:]
            if anchor and slugify(anchor) not in own_headings:
                issues.append(f"{rel}: missing anchor '{target}'")
            continue

        link_path, _, anchor = target.partition("#")
        resolved = (path.parent / link_path).resolve()
        if not resolved.exists():
            issues.append(f"{rel}: missing target '{target}'")
            continue
        if anchor and resolved.suffix == ".md":
            target_headings = _headings(resolved.read_text(encoding="utf-8", errors="replace"))
            if slugify(anchor) not in target_headings:
                issues.append(f"{rel}: missing anchor '{target}'")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()

    files = _doc_files()
    issues: list[str] = []
    for path in files:
        issues.extend(check_file(path))

    if args.json:
        print(json.dumps({"ok": not issues, "files": len(files), "issues": issues}, indent=2))
    else:
        for issue in issues:
            print(issue)
        print(f"{'OK' if not issues else 'FAIL'}: {len(files)} markdown files, {len(issues)} issues")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
