#!/usr/bin/env python3
"""Scan source files for provenance markers and compare against docs/legal/provenance.md.

Searches for comments containing "ported", "adapted from", "derived from",
and GPL-related license strings. Cross-references findings against the
provenance ledger in docs/legal/provenance.md. Reports undocumented ported code.

Exit codes: 0 = clean (no undocumented findings), 1 = undocumented ported code found.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PROVENANCE_PATTERNS = {
    "ported": re.compile(
        r"\b(?:port(?:ed|ing)?\s+(?:of|from)|derived\s+from|adapted\s+from|copied\s+from)",
        re.IGNORECASE,
    ),
    "gpl_license": re.compile(
        r"\bGPL[-\s]?(?:v?[23](?:\.0)?|3\.0|2\.0)?\b",
        re.IGNORECASE,
    ),
}

SOURCE_EXTENSIONS = {".ts", ".py", ".js", ".json", ".md", ".toml"}
SKIP_DIRS = {".git", "node_modules", "dist", ".venv", "__pycache__", ".pytest_cache", "_internal"}
SKIP_FILES = {
    "package-lock.json", "uv.lock", "provenance.md", "CHANGELOG.md",
    # The scanner's own docstring enumerates the patterns it searches for, and
    # notices.md carries the project's own MIT text ("derived from this
    # software") — both are self-referential, not third-party provenance.
    "provenance_scan.py", "notices.md",
}


def find_provenance_markers(root: Path) -> list[dict]:
    findings = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for filename in filenames:
            if filename in SKIP_FILES:
                continue
            ext = os.path.splitext(filename)[1].lower()
            if ext not in SOURCE_EXTENSIONS and filename not in ("Makefile", "Dockerfile"):
                continue

            filepath = Path(dirpath) / filename
            try:
                content = filepath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            relpath = str(filepath.relative_to(root))

            for line_no, line in enumerate(content.splitlines(), 1):
                for marker_type, pattern in PROVENANCE_PATTERNS.items():
                    match = pattern.search(line)
                    if match:
                        findings.append({
                            "file": relpath,
                            "line": line_no,
                            "line_text": line.strip()[:200],
                            "marker_type": marker_type,
                            "match": match.group(0),
                        })

    return findings


TOP_LEVEL_DIRS = {
    "src", "skill", "mcp-server", "graph-engine", "packages", "extension",
    "plugins", "web-viewer", "audit-shared", "tests", "docs", "scripts",
    "templates", "graph-bridge", "reports", "schema", "graphs", "internal",
}

ROOT_DOCS = {"README.md", "CONTRIBUTING.md", "AGENTS.md", "CLAUDE.md", "LICENSE"}


def _looks_like_repo_path(tok: str) -> bool:
    """A repo-relative path cell: either contains a ``/`` (``src/llm_wiki/graph/resolve.py``,
    ``mcp-server/src/``), starts with a known top-level directory, or is a known
    root-level doc filename (``README.md``). The top-level-dir/root-doc filter keeps
    vendored/dependency names out."""
    return "/" in tok or tok.split("/", 1)[0] in TOP_LEVEL_DIRS or tok in ROOT_DOCS


def parse_third_party_entries(third_party_path: Path) -> set[str]:
    entries: set[str] = set()
    if not third_party_path.exists():
        return entries

    content = third_party_path.read_text(encoding="utf-8", errors="replace")

    for line in content.splitlines():
        line = line.strip()
        if not line or not line.startswith("|"):
            continue
        # The local-files column is not positional: the ledger's columns
        # (project | url | license | class | local files | disposition) have
        # drifted over time, so collect path-looking tokens from ANY cell.
        for cell in line.split("|"):
            cell = cell.strip().strip("`").strip("*")
            if not cell:
                continue
            for tok in re.split(r"[,;]", cell):
                tok = tok.strip().strip("`").strip("*")
                if not tok:
                    continue
                if _looks_like_repo_path(tok):
                    entries.add(tok)

    return entries


def classify_findings(findings: list[dict], third_party_entries: set[str]) -> dict:
    documented: list[dict] = []
    undocumented: list[dict] = []
    gpl_findings: list[dict] = []

    for f in findings:
        file = f["file"]
        is_known = any(file == entry or file.endswith(entry) or entry in file for entry in third_party_entries)

        if f["marker_type"] == "gpl_license":
            gpl_findings.append(f)
        elif is_known:
            documented.append(f)
        else:
            undocumented.append(f)

    return {
        "documented": documented,
        "undocumented": undocumented,
        "gpl_references": gpl_findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan for provenance markers and cross-reference with docs/legal/provenance.md")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--root", default=str(REPO_ROOT), help=f"Repo root (default: {REPO_ROOT})")
    args = parser.parse_args()

    root = Path(args.root)
    third_party_path = root / "docs" / "legal" / "provenance.md"

    findings = find_provenance_markers(root)
    third_party_entries = parse_third_party_entries(third_party_path)
    classified = classify_findings(findings, third_party_entries)

    total = len(findings)
    undocumented_count = len(classified["undocumented"])
    gpl_count = len(classified["gpl_references"])
    documented_count = len(classified["documented"])

    if args.json:
        result = {
            "ok": undocumented_count == 0,
            "total_markers": total,
            "documented": documented_count,
            "undocumented": undocumented_count,
            "gpl_references": gpl_count,
            "undocumented_items": classified["undocumented"],
        }
        print(json.dumps(result, indent=2))
    else:
        print(f"Provenance scan: {total} markers found", file=sys.stderr)
        print(f"  Documented in docs/legal/provenance.md: {documented_count}", file=sys.stderr)
        print(f"  Undocumented: {undocumented_count}", file=sys.stderr)
        print(f"  GPL references: {gpl_count}", file=sys.stderr)

        if undocumented_count > 0:
            print(file=sys.stderr)
            print("UNDOCUMENTED PORTED CODE:", file=sys.stderr)
            for item in classified["undocumented"]:
                print(f"  {item['file']}:{item['line']} — {item['line_text']}", file=sys.stderr)

    return 1 if undocumented_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
