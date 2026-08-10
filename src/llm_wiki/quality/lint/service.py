"""Lint service — wiki health checks."""
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

AUDIT_REQUIRED_BASE = {
    "id", "target", "target_lines", "anchor_before", "anchor_text",
    "anchor_after", "severity", "author", "source", "created", "status",
}
VALID_SEVERITIES = {"info", "suggest", "warn", "error"}
VALID_STATUSES = {"open", "resolved"}
VALID_SOURCES = {"obsidian-plugin", "web-viewer", "manual"}



def _rel(root: Path, p: Path) -> str:
    """Portable relative path: forward slashes on every platform. Lint output
    is consumed by test seeds/validators that author paths with '/' — on
    Windows str(Path.relative_to()) yields backslashes and every
    location-based seed match would fail."""
    return str(p.relative_to(root)).replace(os.sep, "/")

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
                dead_links.append((_rel(root_path, md_file), link))
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

    skip_orphan = {"index"}
    orphans = [
        p for p in all_wiki_files
        if p.stem not in inbound and p.stem not in skip_orphan
        and p.parent != pages_dir
    ]
    if orphans:
        print(f"\n🟡 Orphan pages ({len(orphans)}) — no inbound wikilinks:")
        for p in orphans:
            print(f"   {_rel(root_path, p)}")
        issues += len(orphans)
    else:
        print("✅ No orphan pages")

    if index_path.exists():
        index_text = file_cache.get(index_path) or index_path.read_text(encoding="utf-8")
        file_cache[index_path] = index_text
        not_in_index = [
            p for p in all_wiki_files
            if p != index_path
            and f"[[{p.stem}]]" not in index_text
            and _rel(pages_dir, p.with_suffix("")) not in index_text
        ]
        if not_in_index:
            print(f"\n🟡 Pages missing from index.md ({len(not_in_index)}):")
            for p in not_in_index:
                print(f"   {_rel(root_path, p)}")
            issues += len(not_in_index)
        else:
            print("✅ All pages in index.md")
    else:
        print("⚠️  index.md not found — skipping index check")

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

    if log_path is not None and log_path.exists() and log_path.is_dir():
        log_issues: list[str] = []
        for p in sorted(log_path.iterdir()):
            if p.is_dir():
                continue
            if p.name == ".gitkeep":
                continue
            m = LOG_FILENAME_RE.match(p.name)
            if not m:
                log_issues.append(f"   {_rel(root_path, p)} — filename doesn't match YYYYMMDD.md")
                continue
            y, mo, d = m.groups()
            iso = f"{y}-{mo}-{d}"
            first_line = p.read_text(encoding="utf-8").splitlines()[:1]
            if not first_line or first_line[0].strip() != f"# {iso}":
                log_issues.append(f"   {_rel(root_path, p)} — expected H1 '# {iso}'")
        if log_issues:
            print(f"\n🟡 log shape issues ({len(log_issues)}):")
            for s in log_issues:
                print(s)
            issues += len(log_issues)
        else:
            print("✅ log shape OK")
    else:
        print("⚠️  log directory not found — skipping log shape check")

    audit_targets_to_check: list[tuple[str, str]] = []
    if audit_path is not None and audit_path.exists() and audit_path.is_dir():
        audit_files = [p for p in audit_path.rglob("*.md") if p.name != ".gitkeep"]
        audit_issues: list[str] = []
        for p in audit_files:
            text = p.read_text(encoding="utf-8")
            fm = parse_frontmatter(text)
            rel = _rel(root_path, p)
            if fm is None:
                audit_issues.append(f"   {rel} — missing YAML frontmatter")
                continue
            missing = audit_required_fields - set(fm.keys())
            if missing:
                audit_issues.append(f"   {rel} — missing fields: {', '.join(sorted(missing))}")
                continue
            if fm["severity"] not in VALID_SEVERITIES:
                audit_issues.append(f"   {rel} — invalid severity '{fm['severity']}' (expected {sorted(VALID_SEVERITIES)})")
            if fm["source"] not in VALID_SOURCES:
                audit_issues.append(f"   {rel} — invalid source '{fm['source']}'")
            expected_status = "resolved" if "resolved" in p.parts else "open"
            if fm["status"] != expected_status:
                audit_issues.append(f"   {rel} — status '{fm['status']}' doesn't match directory (expected '{expected_status}')")
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

    missing_targets: list[tuple[str, str]] = []
    for audit_id, target in audit_targets_to_check:
        target_path = root_path / target
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

    fm_issues: list[str] = []
    for md_file in all_wiki_files:
        rel = _rel(root_path, md_file)
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

    stale_pages: list[str] = []
    now = datetime.now()
    cutoff = now - timedelta(days=90)
    for md_file in all_wiki_files:
        if md_file.name in skip_files:
            continue
        fm = fm_cache.get(md_file)
        if fm and "updated" in fm:
            try:
                updated = datetime.fromisoformat(fm["updated"])
                if updated < cutoff:
                    stale_pages.append(f"{_rel(root_path, md_file)} (updated {fm['updated']})")
            except (ValueError, TypeError):
                pass
    if stale_pages:
        print(f"\n🟡 Stale pages (>90 days, {len(stale_pages)}):")
        for s in stale_pages:
            print(f"   {s}")
        issues += len(stale_pages)
    else:
        print("✅ No stale pages")

    low_conf: list[str] = []
    for md_file in all_wiki_files:
        if md_file.name in skip_files:
            continue
        fm = fm_cache.get(md_file)
        if fm and fm.get("confidence") in ("low", "medium"):
            low_conf.append(f"{_rel(root_path, md_file)} (confidence: {fm['confidence']})")
    if low_conf:
        print(f"\n🟡 Low/medium confidence pages ({len(low_conf)}):")
        for s in low_conf:
            print(f"   {s}")
        issues += len(low_conf)
    else:
        print("✅ No low-confidence pages")

    contradiction_pages: list[str] = []
    for md_file in all_wiki_files:
        if md_file.name in skip_files:
            continue
        fm = fm_cache.get(md_file)
        if fm and (fm.get("contested") == "true" or fm.get("contradictions")):
            contradiction_pages.append(_rel(root_path, md_file))
    if contradiction_pages:
        print(f"\n🔴 Pages with contradictions ({len(contradiction_pages)}):")
        for s in contradiction_pages:
            print(f"   {s}")
        issues += len(contradiction_pages)
    else:
        print("✅ No contradictions detected")

    large_pages: list[str] = []
    for md_file in all_wiki_files:
        if md_file.name in skip_files:
            continue
        text = file_cache.get(md_file, "")
        lines = text.count("\n")
        if lines > 200:
            large_pages.append(f"{_rel(root_path, md_file)} ({lines} lines)")
    if large_pages:
        print(f"\n🟡 Large pages (>{200} lines, {len(large_pages)}):")
        for s in large_pages:
            print(f"   {s}")
        issues += len(large_pages)
    else:
        print("✅ No overly large pages")

    log_h2_count = 0
    if log_path and log_path.exists() and log_path.is_dir():
        for p in sorted(log_path.iterdir()):
            if p.is_file() and p.suffix == ".md":
                log_h2_count += len(H2_RE.findall(file_cache.get(p, p.read_text(encoding="utf-8"))))
    high_water_mark = 500
    if log_h2_count > high_water_mark:
        print(f"\n🔴 Log has {log_h2_count} H2 entries (> {high_water_mark}), consider rotation")
        issues += 1
    else:
        print(f"✅ Log H2 entries ({log_h2_count}) within limits ({high_water_mark})")

    source_drift: list[str] = []
    if raw_path and raw_path.exists() and raw_path.is_dir():
        for rfile in raw_path.iterdir():
            if rfile.is_file() and rfile.suffix in {".md", ".txt", ".py", ".js", ".ts", ".json", ".yaml"}:
                content = rfile.read_text(encoding="utf-8")
                m = SHA256_RE.search(content)
                if m:
                    stored_hash = m.group(1)
                    text_to_hash = SHA256_RE.sub("", content).strip()
                    if not text_to_hash:
                        text_to_hash = content
                    actual = hashlib.sha256(text_to_hash.encode("utf-8")).hexdigest()
                    if stored_hash != actual:
                        source_drift.append(_rel(root_path, rfile))
    if source_drift:
        print(f"\n🔴 Source drift detected ({len(source_drift)} files):")
        for s in source_drift:
            print(f"   {s}")
        issues += len(source_drift)
    else:
        print("✅ No source drift detected")

    stale_from_drift: list[str] = []
    for md_file in all_wiki_files:
        if md_file.name in skip_files:
            continue
        fm = fm_cache.get(md_file)
        if fm and "source" in fm and source_drift:
            for f in source_drift:
                fname = Path(f).stem
                if fname in fm.get("sources", []):
                    stale_from_drift.append(_rel(root_path, md_file))
                    break
    if stale_from_drift:
        print(f"\n🟡 Pages whose raw sources drifted ({len(stale_from_drift)}):")
        for s in stale_from_drift:
            print(f"   {s}")

    conflict_files: list[str] = []
    for md_file in all_wiki_files:
        text = file_cache.get(md_file, "")
        if "<<<<<<< " in text or "=======" in text or ">>>>>>> " in text:
            conflict_files.append(_rel(root_path, md_file))
    if conflict_files:
        print(f"\n🔴 Merge conflict markers found ({len(conflict_files)}):")
        for s in conflict_files:
            print(f"   {s}")
        issues += len(conflict_files)
    else:
        print("✅ No merge conflict markers")

    if issues:
        plural = "issue" if issues == 1 else "issues"
        print(f"\n{'='*50}")
        print(f"{issues} {plural} found in {root}")
    else:
        print(f"\n{'='*50}")
        print(f"✅ No issues found in {root}")

    return 1 if issues > 0 else 0
