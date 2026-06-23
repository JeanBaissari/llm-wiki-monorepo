#!/usr/bin/env python3
"""discover.py — Auto-discover wiki structure for the llm-wiki-monorepo.

Scans a project root directory and detects:
  - Content page locations (wiki/, content/, pages/, or flat)
  - Source document locations (raw/, sources/, input/)
  - Log and audit directories
  - Page type taxonomy (subdirectories with >=2 .md files)
  - Frontmatter conventions (sampled from existing pages)

Usage:
    python3 discover.py <project-root>              # human-readable output
    python3 discover.py <project-root> --json       # JSON for TS tools
    python3 discover.py <project-root> --show       # verbose detection trace

Exit codes:
    0 — discovery completed (even if low confidence)
    1 — root not a directory
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path


# ── Logging helpers (prints to stderr so --json output stays clean) ────

TRACE: list[str] = []

def trace(msg: str):
    TRACE.append(msg)

def fmt_trace() -> str:
    return "\n".join(f"  {t}" for t in TRACE)


# ── Frontmatter parser (matches lint_wiki.py's implementation) ─────────

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)

def parse_frontmatter(text: str) -> dict:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
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
            result[key] = [x.strip().strip("\"'") for x in inner.split(",") if x.strip()] if inner else []
        elif val.startswith(('"', "'")):
            result[key] = val[1:-1]
        else:
            result[key] = val
    return result


# ── Date format detection ─────────────────────────────────────────────

DATE_PATTERNS = [
    ("%Y-%m-%d", re.compile(r"^\d{4}-\d{2}-\d{2}$")),
    ("%Y-%m-%dT%H:%M:%S", re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")),
    ("%Y/%m/%d", re.compile(r"^\d{4}/\d{2}/\d{2}$")),
    ("%d-%m-%Y", re.compile(r"^\d{2}-\d{2}-\d{4}$")),
    ("%m/%d/%Y", re.compile(r"^\d{2}/\d{2}/\d{4}$")),
]

def detect_date_format(values: list[str]) -> str:
    counts: Counter = Counter()
    for v in values:
        for fmt, pat in DATE_PATTERNS:
            if pat.match(v):
                try:
                    datetime.strptime(v, fmt)
                    counts[fmt] += 1
                except ValueError:
                    pass
    return counts.most_common(1)[0][0] if counts else "%Y-%m-%d"


# ── The WikiLayout dataclass ──────────────────────────────────────────

@dataclass
class WikiLayout:
    root: str
    pages_dir: str
    raw_dir: str | None = None
    log_dir: str | None = None
    audit_dir: str | None = None
    outputs_dir: str | None = None
    index_file: str | None = None
    schema_file: str | None = None
    purpose_file: str | None = None
    page_type_dirs: list[str] = field(default_factory=list)
    page_types: dict[str, str] = field(default_factory=dict)
    frontmatter_required: list[str] = field(default_factory=list)
    frontmatter_optional: list[str] = field(default_factory=list)
    date_format: str = "%Y-%m-%d"
    skip_stems: set[str] = field(default_factory=lambda: {"index", "log", "overview"})
    structural_types: set[str] = field(default_factory=lambda: {"index", "log", "overview"})
    discovery_method: str = "defaults"
    confidence: float = 0.0


# ── Directory candidate lists (tried in order) ────────────────────────

PAGES_DIR_CANDIDATES = ["wiki", "content", "pages", "notes"]
RAW_DIR_CANDIDATES = ["raw", "sources", "input", "src", "documents"]
LOG_DIR_CANDIDATES = ["log", "logs", "journal", "changelog"]
AUDIT_DIR_CANDIDATES = ["audit", "reviews", "feedback", "quality"]
OUTPUTS_DIR_CANDIDATES = ["outputs", "out", "results", "generated"]

LOG_FILENAME_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})\.md$")
LOG_DASHED_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\.md$")


# ── Core detection logic ──────────────────────────────────────────────

def find_first_dir(root: Path, candidates: list[str]) -> Path | None:
    for name in candidates:
        p = root / name
        if p.is_dir() and not p.name.startswith("."):
            trace(f"  Found '{name}/' directory")
            return p
    return None


def find_first_file(root: Path, candidates: list[str]) -> Path | None:
    for name in candidates:
        p = root / name
        if p.is_file():
            trace(f"  Found '{name}' file")
            return p
    return None


def classify_page_dirs(pages_dir: Path) -> tuple[list[str], dict[str, str]]:
    """Detect page type subdirectories (subdirs with >=2 .md files)."""
    dirs: list[str] = []
    types: dict[str, str] = {}
    if not pages_dir.is_dir():
        return dirs, types
    for entry in sorted(pages_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        md_count = len(list(entry.rglob("*.md")))
        if md_count >= 2:
            dirs.append(entry.name)
            types[entry.name] = entry.name.replace("_", " ").replace("-", " ").title()
            trace(f"  Page type: '{entry.name}' ({md_count} pages)")
    return dirs, types


def detect_log_format(log_dir: Path) -> tuple[int, str]:
    """Check if log files are YYYYMMDD.md or YYYY-MM-DD.md format."""
    compact = 0
    dashed = 0
    for p in log_dir.iterdir():
        if p.is_file() and LOG_FILENAME_RE.match(p.name):
            compact += 1
        elif p.is_file() and LOG_DASHED_RE.match(p.name):
            dashed += 1
    if compact > dashed:
        return compact, "compact"  # YYYYMMDD.md
    return dashed, "dashed"  # YYYY-MM-DD.md


SKIP_FM_KEYS = {"wiki_config", "wiki-index", "config", "layout"}

def sample_frontmatter(pages_dir: Path, sample_size: int = 30) -> tuple[list[str], list[str], str]:
    """Sample pages to infer frontmatter conventions."""
    files = list(pages_dir.rglob("*.md"))[:sample_size]
    if not files:
        return ["title", "type", "created"], [], "%Y-%m-%d"

    field_counts: Counter = Counter()
    date_values: list[str] = []

    for f in files:
        fm = parse_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        if fm:
            clean = {k: v for k, v in fm.items() if k not in SKIP_FM_KEYS}
            field_counts.update(clean.keys())
            for date_key in ("created", "updated", "date"):
                if date_key in fm and isinstance(fm[date_key], str):
                    date_values.append(fm[date_key])

    n = len([f for f in files if parse_frontmatter(f.read_text(encoding="utf-8", errors="replace"))])
    total = max(n, 1)

    required = sorted(k for k, v in field_counts.most_common() if v >= total * 0.8)
    optional = sorted(k for k, v in field_counts.most_common() if v < total * 0.8 and v > 0)
    date_fmt = detect_date_format(date_values) if date_values else "%Y-%m-%d"

    return required, optional, date_fmt


def detect_skip_stems(pages_dir: Path) -> set[str]:
    """Detect structural page stems by looking for common non-content files."""
    stems: set[str] = set()
    candidates = {"index", "log", "overview", "readme", "toc", "glossary", "summary"}
    for stem in candidates:
        for p in pages_dir.rglob(f"{stem}.md"):
            stems.add(stem)
            break
    return stems or {"index", "log", "overview"}


def discover_layout(root: str | Path) -> WikiLayout:
    """Auto-discover the wiki structure at the given project root."""
    global TRACE
    TRACE = []

    root_path = Path(root).resolve()
    root_str = str(root_path)
    layout = WikiLayout(root=root_str, pages_dir=root_str)

    if not root_path.is_dir():
        trace(f"ERROR: '{root}' is not a directory")
        layout.confidence = 0.0
        return layout

    # ── 1. Pages directory ────────────────────────────────────────────
    trace(f"Scanning: {root_path}")
    pages_dir = find_first_dir(root_path, PAGES_DIR_CANDIDATES)

    if pages_dir:
        md_files = list(pages_dir.rglob("*.md"))
        if md_files:
            layout.pages_dir = str(pages_dir)
            layout.discovery_method = f"{pages_dir.name}/"
            trace(f"  Pages: {pages_dir.name}/ ({len(md_files)} .md files)")
        else:
            # Dir exists but empty — still use it but note it
            layout.pages_dir = str(pages_dir)
            layout.discovery_method = f"{pages_dir.name}/ (empty)"
            trace(f"  Pages: {pages_dir.name}/ (empty directory)")
    else:
        # Fall back to root — check if root has .md files
        root_md = list(root_path.glob("*.md"))
        if root_md:
            layout.pages_dir = root_str
            layout.discovery_method = "flat"
            trace(f"  Pages: root (flat, {len(root_md)} .md files)")
        else:
            # Check subdirectories one level deep
            for entry in sorted(root_path.iterdir()):
                if entry.is_dir() and not entry.name.startswith("."):
                    sub_md = list(entry.rglob("*.md"))
                    if sub_md:
                        layout.pages_dir = str(entry)
                        layout.discovery_method = f"flat/{entry.name}/"
                        trace(f"  Pages: {entry.name}/ ({len(sub_md)} .md files, guessed)")
                        break
            else:
                layout.pages_dir = root_str
                layout.discovery_method = "flat (no pages found)"
                trace(f"  Pages: root (no .md files found anywhere)")

    pages_path = Path(layout.pages_dir)

    # ── 2. Key files ──────────────────────────────────────────────────
    idx = pages_path / "index.md"
    if idx.is_file():
        layout.index_file = str(idx)
        trace(f"  Index: {idx.relative_to(root_path)}")

    schema = find_first_file(root_path, ["CLAUDE.md", "SCHEMA.md"])
    if schema:
        layout.schema_file = str(schema)

    purpose = find_first_file(root_path, ["PURPOSE.md"])
    if purpose:
        layout.purpose_file = str(purpose)

    # ── 3. Raw / sources directory ────────────────────────────────────
    raw = find_first_dir(root_path, RAW_DIR_CANDIDATES)
    if raw:
        layout.raw_dir = str(raw)
        nested = list(raw.rglob("*"))
        nested_count = len([x for x in nested if x.is_file() and x.name != ".gitkeep"])
        if nested_count:
            trace(f"  Sources: {raw.name}/ ({nested_count} files)")
        else:
            trace(f"  Sources: {raw.name}/ (empty directory)")

    # ── 4. Log directory ──────────────────────────────────────────────
    log_dir = find_first_dir(root_path, LOG_DIR_CANDIDATES)
    if log_dir:
        layout.log_dir = str(log_dir)
        log_files = [p for p in log_dir.iterdir() if p.is_file() and p.name != ".gitkeep"]
        if log_files:
            count, fmt = detect_log_format(log_dir)
            trace(f"  Logs: {log_dir.name}/ ({len(log_files)} files, {fmt} format)")
        else:
            trace(f"  Logs: {log_dir.name}/ (empty directory)")

    # Legacy single-file log
    legacy_log = find_first_file(root_path, ["log.md"])
    if legacy_log and not layout.log_dir:
        layout.log_dir = str(legacy_log.parent)
        trace(f"  Logs: log.md (legacy single-file)")

    # ── 5. Audit directory ────────────────────────────────────────────
    audit = find_first_dir(root_path, AUDIT_DIR_CANDIDATES)
    if audit:
        layout.audit_dir = str(audit)
        audit_files = list(audit.rglob("*.md"))
        has_resolved = (audit / "resolved").is_dir()
        if audit_files:
            trace(f"  Audits: {audit.name}/ ({len(audit_files)} files, resolved/{'yes' if has_resolved else 'no'})")
        else:
            trace(f"  Audits: {audit.name}/ (empty, resolved/{'yes' if has_resolved else 'no'})")

    # ── 6. Outputs directory ──────────────────────────────────────────
    outputs = find_first_dir(root_path, OUTPUTS_DIR_CANDIDATES)
    if outputs:
        layout.outputs_dir = str(outputs)

    # ── 7. Page type discovery ────────────────────────────────────────
    ptype_dirs, ptype_map = classify_page_dirs(pages_path)
    layout.page_type_dirs = ptype_dirs
    layout.page_types = ptype_map

    # ── 8. Frontmatter sampling ───────────────────────────────────────
    fm_req, fm_opt, date_fmt = sample_frontmatter(pages_path)
    layout.frontmatter_required = fm_req
    layout.frontmatter_optional = fm_opt
    layout.date_format = date_fmt
    if fm_req:
        trace(f"  Frontmatter requires: {fm_req}")
    if fm_opt:
        trace(f"  Frontmatter optional: {fm_opt}")
    if date_fmt != "%Y-%m-%d":
        trace(f"  Date format: {date_fmt}")

    # ── 9. Skip stems ─────────────────────────────────────────────────
    layout.skip_stems = detect_skip_stems(pages_path)
    if layout.skip_stems != {"index", "log", "overview"}:
        trace(f"  Skip stems: {sorted(layout.skip_stems)}")

    # ── 10. Confidence scoring ────────────────────────────────────────
    signals = 0
    total_signals = 7

    # Signal 1: pages_dir has content
    pages_md = list(pages_path.rglob("*.md"))
    if pages_md:
        signals += 1

    # Signal 2: has raw_dir with content
    if layout.raw_dir:
        signals += 1

    # Signal 3: has log_dir with content
    if layout.log_dir:
        signals += 1

    # Signal 4: has audit_dir with content
    if layout.audit_dir:
        signals += 1

    # Signal 5: has index file
    if layout.index_file:
        signals += 1

    # Signal 6: has schema or purpose
    if layout.schema_file or layout.purpose_file:
        signals += 1

    # Signal 7: has page type directories
    if layout.page_type_dirs:
        signals += 1

    layout.confidence = round(signals / total_signals, 2)

    # Adjust for canonical structure bonus
    if (pages_dir and pages_dir.name == "wiki" and layout.raw_dir and
            layout.log_dir and layout.audit_dir):
        layout.confidence = min(layout.confidence + 0.15, 1.0)
        trace(f"  Canonical structure detected (+0.15 bonus)")

    trace(f"  Confidence: {layout.confidence} ({signals}/{total_signals} signals)")

    return layout


# ── Output formatters ─────────────────────────────────────────────────

def format_human(layout: WikiLayout) -> str:
    lines = [
        f"Wiki Layout Discovery: {layout.root}",
        f"  Method:     {layout.discovery_method}",
        f"  Confidence: {layout.confidence}",
        "",
        "Directories:",
        f"  Pages:      {layout.pages_dir or '(not found)'}",
        f"  Sources:    {layout.raw_dir or '(not found)'}",
        f"  Logs:       {layout.log_dir or '(not found)'}",
        f"  Audits:     {layout.audit_dir or '(not found)'}",
        f"  Outputs:    {layout.outputs_dir or '(not found)'}",
        "",
        "Key Files:",
        f"  Index:      {layout.index_file or '(not found)'}",
        f"  Schema:     {layout.schema_file or '(not found)'}",
        f"  Purpose:    {layout.purpose_file or '(not found)'}",
        "",
        "Page Types:",
    ]
    if layout.page_type_dirs:
        for d in layout.page_type_dirs:
            label = layout.page_types.get(d, d)
            lines.append(f"  - {d}/  ({label})")
    else:
        lines.append("  (none detected)")

    lines.extend([
        "",
        f"Frontmatter Required:  {layout.frontmatter_required or '(none)'}",
        f"Frontmatter Optional:  {layout.frontmatter_optional or '(none)'}",
        f"Date Format:           {layout.date_format}",
        f"Skip Stems:            {sorted(layout.skip_stems)}",
    ])

    if TRACE:
        lines.extend(["", "Detection Trace:", fmt_trace()])

    return "\n".join(lines)


def format_json(layout: WikiLayout) -> str:
    d = asdict(layout)
    d["skip_stems"] = sorted(d["skip_stems"])
    d["structural_types"] = sorted(d["structural_types"])
    d["_trace"] = TRACE
    return json.dumps(d, indent=2, default=str)


# ── CLI entry point ───────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Auto-discover wiki structure for the llm-wiki-monorepo."
    )
    parser.add_argument("wiki_root", help="Path to the wiki project root")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON (for TS tool integration)")
    parser.add_argument("--show", action="store_true",
                        help="Show verbose detection trace")

    args = parser.parse_args()

    layout = discover_layout(args.wiki_root)

    if args.json:
        print(format_json(layout))
    else:
        print(format_human(layout))

    return 0


if __name__ == "__main__":
    sys.exit(main())
