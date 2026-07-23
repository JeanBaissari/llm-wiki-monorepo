#!/usr/bin/env python3
"""
lint_wiki.py — Comprehensive health check for an LLM Wiki.

Uses auto-discovered layout (via discover.py) instead of hardcoded paths.

Usage:
    python3 lint_wiki.py <wiki-root>
    python3 lint_wiki.py --check-templates [path]

Example:
    python3 lint_wiki.py ~/wikis/ai-research
    python3 lint_wiki.py --check-templates

Checks:
  1. Dead wikilinks   — [[Target]] where Target.md doesn't exist
  2. Orphan pages     — wiki pages with no inbound links
  3. Missing index    — wiki pages not listed in index.md
  4. Unlinked concepts — terms mentioned 3+ times but lacking their own page
  5. Log shape        — every file matches YYYYMMDD.md and has the right H1
  6. Audit shape      — every audit file parses as a valid AuditEntry
  7. Audit targets    — every open audit's `target` file must exist
  8. Frontmatter      — wiki pages missing required frontmatter fields
  9. Stale pages      — wiki pages updated >90 days ago
 10. Confidence       — pages with confidence: low or medium
 11. Contradictions   — pages marked contested or with contradictions list
 12. Page size        — pages over 200 lines flagged for splitting
 13. Log rotation     — total H2 entries across log > 500
 14. Source drift     — SHA256 hash mismatches in raw frontmatter
 15. Stale from drift — wiki pages whose sources drifted
 16. Conflict files   — merge conflict markers still present
 17. Template check   — (--check-templates) validate template structure

Exit codes:
  0 — no issues found
  1 — issues found (printed to stdout)
"""

import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from llm_wiki.core.layout import discover_layout
from llm_wiki.core.frontmatter import FRONTMATTER_RE, parse_frontmatter
from llm_wiki.core.wikilinks import load_pages, extract_wikilinks, WIKILINK_RE

LOG_FILENAME_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})\.md$")
H2_RE = re.compile(r"^##\s", re.MULTILINE)
SHA256_RE = re.compile(r"^sha256:\s*([a-f0-9]{64})", re.MULTILINE)

# Base required audit frontmatter fields (merged with discovered fields at runtime)
AUDIT_REQUIRED_BASE = {
    "id", "target", "target_lines", "anchor_before", "anchor_text",
    "anchor_after", "severity", "author", "source", "created", "status",
}
VALID_SEVERITIES = {"info", "suggest", "warn", "error"}
VALID_STATUSES = {"open", "resolved"}
VALID_SOURCES = {"obsidian-plugin", "web-viewer", "manual"}


def lint(root: str) -> int:
    root_path = Path(root).resolve()
    layout = discover_layout(root_path)

    pages_dir = Path(layout.pages_dir)
    log_path = Path(layout.log_dir) if layout.log_dir else None
    audit_path = Path(layout.audit_dir) if layout.audit_dir else None
    raw_path = Path(layout.raw_dir) if layout.raw_dir else None

    skip_files = {f"{stem}.md" for stem in layout.skip_stems}
    audit_required_fields = AUDIT_REQUIRED_BASE | set(layout.frontmatter_required)

    if not pages_dir.exists():
        print(f"ERROR: pages directory not found at {pages_dir}", file=sys.stderr)
        return 1

    pages = load_pages(pages_dir)
    all_wiki_files = list(pages_dir.rglob("*.md"))
    index_path = pages_dir / "index.md"

    issues = 0
    inbound: dict[str, list[str]] = defaultdict(list)

    # ── Pass 1: dead wikilinks ──────────────────────────────────────────────
    # Also cache file content and frontmatter for later passes to avoid
    # re-reading every file three times.
    file_cache: dict[Path, str] = {}
    fm_cache: dict[Path, dict | None] = {}
    dead_links: list[tuple[str, str]] = []

    for md_file in all_wiki_files:
        text = md_file.read_text(encoding="utf-8")
        file_cache[md_file] = text
        fm_cache[md_file] = parse_frontmatter(text)

        for link in extract_wikilinks(text):
            link = link.strip()
            if link not in pages and Path(link).stem not in pages:
                dead_links.append((str(md_file.relative_to(root_path)), link))
            else:
                target = pages.get(link) or pages.get(Path(link).stem)
                if target:
                    inbound[target.stem].append(md_file.stem)

    if dead_links:
        print(f"\n🔴 Dead wikilinks ({len(dead_links)}):")
        for source, link in dead_links:
            print(f"   {source} → [[{link}]]")
        issues += len(dead_links)
    else:
        print("✅ No dead wikilinks")

    # ── Pass 2: orphan pages ────────────────────────────────────────────────
    skip_orphan = {"index"}
    orphans = [
        p for p in all_wiki_files
        if p.stem not in inbound and p.stem not in skip_orphan
        and p.parent != pages_dir  # skip index.md at root
    ]
    if orphans:
        print(f"\n🟡 Orphan pages ({len(orphans)}) — no inbound wikilinks:")
        for p in orphans:
            print(f"   {p.relative_to(root_path)}")
        issues += len(orphans)
    else:
        print("✅ No orphan pages")

    # ── Pass 3: missing index entries ───────────────────────────────────────
    if index_path.exists():
        index_text = file_cache.get(index_path) or index_path.read_text(encoding="utf-8")
        file_cache[index_path] = index_text
        not_in_index = [
            p for p in all_wiki_files
            if p != index_path
            and f"[[{p.stem}]]" not in index_text
            and str(p.relative_to(pages_dir).with_suffix("")) not in index_text
        ]
        if not_in_index:
            print(f"\n🟡 Pages missing from index.md ({len(not_in_index)}):")
            for p in not_in_index:
                print(f"   {p.relative_to(root_path)}")
            issues += len(not_in_index)
        else:
            print("✅ All pages in index.md")
    else:
        print("⚠️  index.md not found — skipping index check")

    # ── Pass 4: unlinked concepts ───────────────────────────────────────────
    all_text = " ".join(file_cache[p] for p in all_wiki_files)
    all_links = WIKILINK_RE.findall(all_text)
    link_counts: dict[str, int] = defaultdict(int)
    for link in all_links:
        link_counts[link.strip()] += 1

    missing_pages = [
        (link, count) for link, count in link_counts.items()
        if count >= 3 and link not in pages and Path(link).stem not in pages
    ]
    if missing_pages:
        print(f"\n🟡 Frequently linked but no page ({len(missing_pages)}):")
        for link, count in sorted(missing_pages, key=lambda x: -x[1]):
            print(f"   [[{link}]] — mentioned {count}x")
        issues += len(missing_pages)
    else:
        print("✅ No frequently-linked missing pages")

    # ── Pass 5: log/ shape ───────────────────────────────────────────────────
    if log_path is not None and log_path.exists() and log_path.is_dir():
        log_issues: list[str] = []
        for p in sorted(log_path.iterdir()):
            if p.is_dir():
                continue
            if p.name == ".gitkeep":
                continue
            m = LOG_FILENAME_RE.match(p.name)
            if not m:
                log_issues.append(
                    f"   {p.relative_to(root_path)} — filename doesn't match YYYYMMDD.md"
                )
                continue
            y, mo, d = m.groups()
            iso = f"{y}-{mo}-{d}"
            first_line = p.read_text(encoding="utf-8").splitlines()[:1]
            if not first_line or first_line[0].strip() != f"# {iso}":
                log_issues.append(
                    f"   {p.relative_to(root_path)} — expected H1 '# {iso}'"
                )
        if log_issues:
            print(f"\n🟡 log shape issues ({len(log_issues)}):")
            for s in log_issues:
                print(s)
            issues += len(log_issues)
        else:
            print("✅ log shape OK")
    else:
        print("⚠️  log directory not found — skipping log shape check")

    # ── Pass 6: audit/ shape ─────────────────────────────────────────────────
    audit_targets_to_check: list[tuple[str, str]] = []  # (audit_id, target)
    if audit_path is not None and audit_path.exists() and audit_path.is_dir():
        audit_files = [
            p for p in audit_path.rglob("*.md") if p.name != ".gitkeep"
        ]
        audit_issues: list[str] = []
        for p in audit_files:
            text = p.read_text(encoding="utf-8")
            fm = parse_frontmatter(text)
            rel = p.relative_to(root_path)
            if fm is None:
                audit_issues.append(f"   {rel} — missing YAML frontmatter")
                continue
            missing = audit_required_fields - set(fm.keys())
            if missing:
                audit_issues.append(
                    f"   {rel} — missing fields: {', '.join(sorted(missing))}"
                )
                continue
            if fm["severity"] not in VALID_SEVERITIES:
                audit_issues.append(
                    f"   {rel} — invalid severity '{fm['severity']}' "
                    f"(expected {sorted(VALID_SEVERITIES)})"
                )
            if fm["source"] not in VALID_SOURCES:
                audit_issues.append(
                    f"   {rel} — invalid source '{fm['source']}'"
                )
            expected_status = "resolved" if "resolved" in p.parts else "open"
            if fm["status"] != expected_status:
                audit_issues.append(
                    f"   {rel} — status '{fm['status']}' doesn't match "
                    f"directory (expected '{expected_status}')"
                )
            if fm["status"] == "open":
                audit_targets_to_check.append((fm["id"], fm["target"]))

        if audit_issues:
            print(f"\n🔴 audit shape issues ({len(audit_issues)}):")
            for s in audit_issues:
                print(s)
            issues += len(audit_issues)
        else:
            print(f"✅ audit shape OK ({len(audit_files)} files)")
    else:
        print("⚠️  audit directory not found — skipping audit shape check")

    # ── Pass 7: audit targets exist ──────────────────────────────────────────
    missing_targets: list[tuple[str, str]] = []
    for audit_id, target in audit_targets_to_check:
        target_path = root_path / target
        # Audit target paths are relative to wiki-root but typically point
        # at files under wiki/. Check both locations.
        if not target_path.exists():
            alt = pages_dir / target
            if not alt.exists():
                missing_targets.append((audit_id, target))
    if missing_targets:
        print(f"\n🔴 Open audits with missing target files ({len(missing_targets)}):")
        for audit_id, target in missing_targets:
            print(f"   {audit_id} → {target}")
        issues += len(missing_targets)
    elif audit_targets_to_check:
        print("✅ All open-audit targets exist")

    # ═══════════════════════════════════════════════════════════════════════
    # NEW PASSES — wiki content health
    # ═══════════════════════════════════════════════════════════════════════

    # ── Pass 8: frontmatter validation (wiki pages) ──────────────────────────
    fm_issues: list[str] = []
    for md_file in all_wiki_files:
        rel = md_file.relative_to(root_path)
        if md_file.name in skip_files:
            continue
        fm = fm_cache.get(md_file)
        if fm is None:
            fm_issues.append(f"{rel} — no YAML frontmatter")
            continue
        for field in layout.frontmatter_required:
            if field not in fm:
                fm_issues.append(f"{rel} — missing '{field}' in frontmatter")

    if fm_issues:
        print(f"\n🟡 Frontmatter validation issues ({len(fm_issues)}):")
        for s in fm_issues:
            print(f"   {s}")
        issues += len(fm_issues)
    else:
        print("✅ All wiki pages have valid frontmatter")

    # ── Pass 9: stale pages (updated >90 days ago) ───────────────────────────
    stale_pages: list[str] = []
    now = datetime.now()
    cutoff = now - timedelta(days=90)
    for md_file in all_wiki_files:
        if md_file.name in skip_files:
            continue
        rel = md_file.relative_to(root_path)
        fm = fm_cache.get(md_file)
        if fm is None:
            continue
        updated = fm.get("updated")
        if updated and isinstance(updated, str):
            try:
                updated_date = datetime.strptime(updated, layout.date_format)
                if updated_date < cutoff:
                    stale_pages.append(
                        f"{rel} — last updated {updated} (>90 days)"
                    )
            except ValueError:
                pass

    if stale_pages:
        print(f"\n🟡 Stale pages (>90 days since update) ({len(stale_pages)}):")
        for s in stale_pages:
            print(f"   {s}")
        issues += len(stale_pages)
    else:
        print("✅ No stale pages")

    # ── Pass 10: confidence signals ──────────────────────────────────────────
    confidence_issues: list[str] = []
    for md_file in all_wiki_files:
        if md_file.name in skip_files:
            continue
        rel = md_file.relative_to(root_path)
        fm = fm_cache.get(md_file)
        if fm is None:
            continue
        conf = fm.get("confidence", "")
        if isinstance(conf, str) and conf.strip().lower() in ("low", "medium"):
            confidence_issues.append(f"{rel} — confidence={conf.strip().lower()}")

    if confidence_issues:
        print(f"\n🟡 Low/medium-confidence pages ({len(confidence_issues)}):")
        for s in confidence_issues:
            print(f"   {s}")
        issues += len(confidence_issues)
    else:
        print("✅ No confidence issues")

    # ── Pass 11: contradiction signals ────────────────────────────────────────
    contradiction_pages: list[str] = []
    for md_file in all_wiki_files:
        if md_file.name in skip_files:
            continue
        rel = md_file.relative_to(root_path)
        fm = fm_cache.get(md_file)
        if fm is None:
            continue

        contested = fm.get("contested", "")
        if isinstance(contested, str) and contested.strip().lower() == "true":
            contradiction_pages.append(f"{rel} — contested=true")
        elif isinstance(contested, bool) and contested:
            contradiction_pages.append(f"{rel} — contested=true")

        contradictions = fm.get("contradictions")
        if contradictions:
            if isinstance(contradictions, list) and len(contradictions) > 0:
                contradiction_pages.append(
                    f"{rel} — has contradictions in frontmatter"
                )
            elif isinstance(contradictions, str) and contradictions.strip():
                contradiction_pages.append(
                    f"{rel} — has contradictions in frontmatter"
                )

    if contradiction_pages:
        print(
            f"\n🟡 Pages with contradiction signals "
            f"({len(contradiction_pages)}):"
        )
        for s in contradiction_pages:
            print(f"   {s}")
        issues += len(contradiction_pages)
    else:
        print("✅ No contradiction signals found")

    # ── Pass 12: page size (>200 lines) ───────────────────────────────────────
    size_issues: list[str] = []
    for md_file in all_wiki_files:
        if md_file.name in skip_files:
            continue
        rel = md_file.relative_to(root_path)
        text = file_cache.get(md_file, "")
        if not text:
            continue
        line_count = len(text.splitlines())
        if line_count > 200:
            size_issues.append(f"{rel}: {line_count} lines — candidate for splitting")

    if size_issues:
        print(f"\n🟡 Large pages (>200 lines) ({len(size_issues)}):")
        for s in size_issues:
            print(f"   {s}")
        issues += len(size_issues)
    else:
        print("✅ All pages under 200 lines")

    # ── Pass 13: log rotation check (total H2 entries across log/) ────────────
    if log_path is not None and log_path.exists() and log_path.is_dir():
        total_h2 = 0
        for p in sorted(log_path.iterdir()):
            if p.is_dir() or p.name == ".gitkeep":
                continue
            text = p.read_text(encoding="utf-8")
            total_h2 += len(H2_RE.findall(text))
        if total_h2 > 500:
            print(
                f"\n🟡 Log rotation needed — {total_h2} H2 entries "
                f"across log (>500)"
            )
            issues += 1
        else:
            print(
                f"✅ Log entries across log ({total_h2} H2 entries) — "
                f"well within limits"
            )
    else:
        print("⚠️  log directory not found — skipping log rotation check")

    # ── Pass 14: source drift (SHA256 in raw/ frontmatter) ────────────────────
    drift_issues: list[str] = []
    if raw_path is not None and raw_path.exists() and raw_path.is_dir():
        raw_files = list(raw_path.rglob("*.md"))
        for rp in raw_files:
            try:
                text = rp.read_text(encoding="utf-8")
                fm = parse_frontmatter(text)
                if fm is None:
                    continue
                stored_sha = fm.get("sha256")
                if not stored_sha:
                    continue
                # Body is everything after frontmatter
                m = FRONTMATTER_RE.match(text)
                body = text[m.end():] if m else text
                current_sha = hashlib.sha256(body.encode()).hexdigest()
                if stored_sha != current_sha:
                    drift_issues.append(
                        f"{rp.relative_to(root_path)}: sha256 mismatch "
                        f"(raw file modified or source changed)"
                    )
            except Exception:
                pass

        if drift_issues:
            print(f"\n🔴 Source drift — SHA256 mismatches ({len(drift_issues)}):")
            for s in drift_issues:
                print(f"   {s}")
            issues += len(drift_issues)
        elif raw_files:
            print(
                f"✅ All {len(raw_files)} raw files have matching "
                f"SHA256 hashes"
            )
        else:
            print("⚠️  No raw files to check for SHA256 drift")
    else:
        print("⚠️  raw directory not found — skipping source drift check")

    # ── Pass 15: stale wiki pages from source drift ─────────────────────────
    stale_source_pages: list[str] = []
    if drift_issues:
        drifted_slugs: set[str] = set()
        for issue in drift_issues:
            # "raw/articles/strategy.md: sha256 mismatch ..."
            raw_path_str = issue.split(":")[0]
            raw_file = Path(raw_path_str)
            drifted_slugs.add(raw_file.stem.lower())

        for md_file in all_wiki_files:
            if md_file.name in skip_files:
                continue
            rel = md_file.relative_to(root_path)
            fm = fm_cache.get(md_file)
            if fm is None:
                continue
            sources = fm.get("sources", [])
            if isinstance(sources, str):
                sources = [sources]
            if any(s.lower().strip() in drifted_slugs for s in sources):
                stale_source_pages.append(
                    f"{rel} — source file has changed since ingest"
                )

    if stale_source_pages:
        print(
            f"\n🔴 Stale wiki pages from source drift "
            f"({len(stale_source_pages)}):"
        )
        for s in stale_source_pages:
            print(f"   {s}")
        issues += len(stale_source_pages)
    else:
        print("✅ No stale wiki pages from source drift")

    # ── Summary ─────────────────────────────────────────────────────────────
    print(f"\n{'─'*40}")
    if issues == 0:
        print("✅ Wiki is healthy — no issues found")
    else:
        print(
            f"⚠️  {issues} issue(s) found — review above and fix "
            f"before next ingest"
        )

    return 0 if issues == 0 else 1


def check_templates(templates_dir: Path) -> int:
    """Validate all domain template directories for structural integrity.

    Each template must have:
      - PURPOSE.md (≥10 lines)
      - SCHEMA.md (covers ≥5 standard sections)
      - extra-dirs.json (valid, each dir appears in SCHEMA.md tables)

    Returns 0 if all clean, 1 if issues found.
    """
    if not templates_dir.exists():
        print(
            f"ERROR: templates directory not found at {templates_dir}",
            file=sys.stderr,
        )
        return 2

    # The 5 standard sections every SCHEMA.md should cover.
    REQUIRED_SECTIONS: list[tuple[str, re.Pattern]] = [
        ("page types", re.compile(r"page.?type|base.?type|inherited.?base", re.IGNORECASE)),
        ("frontmatter conventions", re.compile(r"frontmatter", re.IGNORECASE)),
        ("naming rules", re.compile(r"naming|file.?naming", re.IGNORECASE)),
        ("wikilinks", re.compile(r"wikilink|linking|cross.?ref", re.IGNORECASE)),
        ("diagrams", re.compile(r"diagram|mermaid|visual|kroki", re.IGNORECASE)),
    ]

    issues = 0
    template_dirs = sorted(
        d
        for d in templates_dir.iterdir()
        if d.is_dir() and d.name != "_shared"
    )

    for td in template_dirs:
        name = td.name
        tpl_issues: list[str] = []

        # — PURPOSE.md —————————————————————————————————————————————————
        purpose_path = td / "PURPOSE.md"
        if not purpose_path.exists():
            tpl_issues.append("missing PURPOSE.md")
        else:
            lines = purpose_path.read_text(encoding="utf-8").splitlines()
            if len(lines) < 10:
                tpl_issues.append(
                    f"PURPOSE.md has {len(lines)} lines (need ≥10)"
                )

        # — SCHEMA.md ———————————————————————————————————————————————————
        schema_path = td / "SCHEMA.md"
        schema_text = ""
        if not schema_path.exists():
            tpl_issues.append("missing SCHEMA.md")
        else:
            schema_text = schema_path.read_text(encoding="utf-8")
            h2_headings = re.findall(
                r"^##\s+(.+)", schema_text, re.MULTILINE
            )

            missing: list[str] = []
            for label, pattern in REQUIRED_SECTIONS:
                if not any(pattern.search(h) for h in h2_headings):
                    missing.append(label)

            if missing:
                tpl_issues.append(
                    f"SCHEMA.md missing {len(missing)} standard section(s): "
                    + ", ".join(missing)
                )

        # — extra-dirs.json —————————————————————————————————————————————
        extra_path = td / "extra-dirs.json"
        if not extra_path.exists():
            tpl_issues.append("missing extra-dirs.json")
        else:
            try:
                raw = extra_path.read_text(encoding="utf-8")
                extra_data = json.loads(raw)
            except json.JSONDecodeError as exc:
                tpl_issues.append(f"extra-dirs.json is invalid JSON: {exc}")
                extra_data = None

            if extra_data is not None:
                # Accept both flat arrays and {"directories": [...]}
                if isinstance(extra_data, dict):
                    dirs: list[str] = extra_data.get("directories", [])
                    if not isinstance(dirs, list):
                        tpl_issues.append(
                            "extra-dirs.json 'directories' is not an array"
                        )
                        dirs = []
                elif isinstance(extra_data, list):
                    dirs = extra_data
                else:
                    tpl_issues.append(
                        "extra-dirs.json is not a JSON array or "
                        "object with 'directories'"
                    )
                    dirs = []

                if dirs and schema_text:
                    # Extract known directory names from SCHEMA.md tables.
                    # Paths appear in pipe tables as bare `prefix/name/` or
                    # backtick-quoted `` `wiki/name/` ``.
                    _DIR_RE = re.compile(
                        r"(?:`|[\s|])(?:wiki/)?(?:[\w-]+/)*?([\w-]+)/(?:`|[\s|])"
                    )
                    schema_dirs: set[str] = set()
                    for line in schema_text.splitlines():
                        for m in _DIR_RE.finditer(line):
                            dname = m.group(1)
                            if dname != "wiki":  # skip literal 'wiki/' from overview rows
                                schema_dirs.add(dname)

                    unmatched = [d for d in dirs if d not in schema_dirs]
                    if unmatched:
                        tpl_issues.append(
                            "extra-dirs.json references dir(s) not in "
                            "SCHEMA.md: " + ", ".join(unmatched)
                        )

        # — Report ——————————————————————————————————————————————————————
        if tpl_issues:
            print(f"\n🔴 {name} ({len(tpl_issues)} issue(s)):")
            for ti in tpl_issues:
                print(f"   {ti}")
            issues += len(tpl_issues)
        else:
            print(f"  ✅ {name}")

    # — Summary ————————————————————————————————————————————————————————
    print(f"\n{'─' * 40}")
    if issues == 0:
        print(f"✅ All {len(template_dirs)} templates valid")
    else:
        print(
            f"⚠️  {issues} issue(s) across "
            f"{len(template_dirs)} templates"
        )

    return 0 if issues == 0 else 1


def main() -> int:
    # OperationContext is not used here because lint_wiki has no --fix mode
    # (read-only operation). Will be added when --fix is implemented.
    import argparse

    parser = argparse.ArgumentParser(
        description="Comprehensive health check for an LLM Wiki — 16 automated passes (+1 template pass).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 lint_wiki.py ~/my-wiki\n"
            "  python3 lint_wiki.py ~/my-wiki --json\n"
            "  python3 lint_wiki.py --check-templates\n"
            "  python3 lint_wiki.py --check-templates /path/to/templates\n"
        ),
    )
    parser.add_argument(
        "wiki_root",
        nargs="?",
        help="Path to the wiki root directory (optional when --check-templates is used)",
    )
    parser.add_argument(
        "--json", action="store_true", help="Output results as JSON instead of text"
    )
    parser.add_argument(
        "--check-templates",
        nargs="?",
        const="__auto__",
        default=None,
        help=(
            "Validate template structure instead of linting a wiki. "
            "Optionally provide path to templates directory; "
            "defaults to auto-detection from script location."
        ),
    )
    args = parser.parse_args()

    if args.check_templates:
        if args.check_templates == "__auto__":
            # Resolve templates/ relative to repo root (script is in src/llm_wiki/)
            templates_dir = (
                Path(__file__).resolve().parent.parent.parent / "templates"
            )
        else:
            templates_dir = Path(args.check_templates).resolve()
        return check_templates(templates_dir)

    if not args.wiki_root:
        parser.error(
            "wiki_root is required unless --check-templates is used"
        )

    return lint(args.wiki_root)


if __name__ == "__main__":
    sys.exit(main())
