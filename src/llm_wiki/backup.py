#!/usr/bin/env python3
"""
backup.py — Snapshot, restore, and integrity verification for LLM wikis.

Usage:
    python3 backup.py <wiki-root> --snapshot
    python3 backup.py <wiki-root> --restore <timestamp>
    python3 backup.py <wiki-root> --list
    python3 backup.py <wiki-root> --verify
    python3 backup.py <wiki-root> --prune N
    python3 backup.py <wiki-root> --auto

Examples:
    python3 backup.py ~/wikis/ai-research --snapshot
    python3 backup.py ~/wikis/ai-research --restore 20260101-120000
    python3 backup.py ~/wikis/ai-research --list
    python3 backup.py ~/wikis/ai-research --verify
    python3 backup.py ~/wikis/ai-research --prune 5
    python3 backup.py ~/wikis/ai-research --auto

Exit codes:
    0 — success
    1 — error
"""

import argparse
import glob
import gzip
import os
import re
import subprocess
import sys
import tarfile
import time
from datetime import datetime
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from discover import discover_layout


FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")
KEEP = 10  # default number of backups to keep when pruning


def parse_frontmatter(text: str) -> dict | None:
    """Minimal YAML-ish frontmatter parser (same as lint_wiki.py)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    body = m.group(1)
    result: dict = {}
    i = 0
    lines = body.split("\n")
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if ":" not in line:
            i += 1
            continue
        key, _, rest = line.partition(":")
        key = key.strip()
        val = rest.strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            if not inner:
                result[key] = []
            else:
                parts = [p.strip() for p in inner.split(",")]
                parsed: list = []
                for p in parts:
                    if p.isdigit() or (p.startswith("-") and p[1:].isdigit()):
                        parsed.append(int(p))
                    else:
                        parsed.append(p.strip('"').strip("'"))
                result[key] = parsed
        elif val.startswith('"') and val.endswith('"'):
            result[key] = val[1:-1].replace("\\n", "\n").replace('\\"', '"')
        elif val.startswith("'") and val.endswith("'"):
            result[key] = val[1:-1]
        else:
            result[key] = val
        i += 1
    return result


def wiki_name(root: Path) -> str:
    """Derive a short wiki name from the wiki-root directory name."""
    return root.resolve().name


def backups_dir(root: Path) -> Path:
    """Return the backups directory (sibling to the wiki-root)."""
    return root.resolve().parent / "backups"


def snapshot_path(root: Path, timestamp: str | None = None) -> Path:
    """Generate the path for a backup snapshot."""
    bdir = backups_dir(root)
    name = wiki_name(root)
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return bdir / f"{name}-{timestamp}.tar.gz"


def parse_timestamp(path: Path) -> str:
    """Extract the timestamp portion from a backup filename."""
    name = path.stem
    if name.endswith(".tar"):
        name = name[:-4]
    m = re.search(r"-(\d{8}-\d{6})$", name)
    return m.group(1) if m else name


def list_backups(root: Path) -> list[Path]:
    """Return sorted list of backup files for this wiki (newest first)."""
    bdir = backups_dir(root)
    name = wiki_name(root)
    if not bdir.exists():
        return []
    pattern = str(bdir / f"{name}-*.tar.gz")
    files = [Path(f) for f in glob.glob(pattern)]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def format_size(size_bytes: int) -> str:
    """Format bytes to human-readable string."""
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def format_age(mtime: float) -> str:
    """Format a modification time to a human-readable age string."""
    seconds = time.time() - mtime
    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    elif seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    elif seconds < 2592000:
        return f"{int(seconds // 86400)}d ago"
    else:
        return f"{int(seconds // 2592000)}mo ago"


def count_files_in_tar(path: Path) -> int:
    """Count the number of files in a tar.gz archive."""
    count = 0
    with tarfile.open(str(path), "r:gz") as tar:
        for member in tar:
            if member.isfile():
                count += 1
    return count


# ── Operations ──────────────────────────────────────────────────────────────

def cmd_snapshot(root: Path) -> int:
    """Create a timestamped tar.gz snapshot of the wiki."""
    root_resolved = root.resolve()
    if not root_resolved.is_dir():
        print(f"ERROR: {root} is not a valid directory", file=sys.stderr)
        return 1

    bdir = backups_dir(root)
    bdir.mkdir(parents=True, exist_ok=True)

    dest = snapshot_path(root)
    parent_dir = root_resolved.parent
    base_name = root_resolved.name

    layout = discover_layout(root)
    include_items = [Path(layout.pages_dir).name]
    if layout.audit_dir:
        include_items.append(Path(layout.audit_dir).name)
    if layout.log_dir:
        include_items.append(Path(layout.log_dir).name)
    if layout.outputs_dir:
        include_items.append(Path(layout.outputs_dir).name)
    include_items.extend(["CLAUDE.md", "PURPOSE.md"])
    cmd = [
        "tar", "czf", str(dest),
        "--exclude", "raw",
        "--exclude", "node_modules",
        "--exclude", "dist",
    ]
    for item in include_items:
        path = root_resolved / item
        if path.exists():
            cmd.extend(["-C", str(parent_dir), f"{base_name}/{item}"])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: tar failed: {result.stderr.strip()}", file=sys.stderr)
        return 1

    size_bytes = dest.stat().st_size
    file_count = count_files_in_tar(dest)
    print(f"Snapshot created: {dest} ({format_size(size_bytes)}, {file_count} files)")
    return 0


def cmd_restore(root: Path, timestamp: str) -> int:
    """Restore wiki from a backup snapshot, with auto pre-restore backup."""
    root_resolved = root.resolve()
    dest = snapshot_path(root, timestamp)

    if not dest.exists():
        print(f"ERROR: Backup not found: {dest}", file=sys.stderr)
        return 1

    # Pre-restore snapshot
    print(f"Creating pre-restore backup...", file=sys.stderr)
    if cmd_snapshot(root) != 0:
        print("ERROR: Pre-restore backup failed — aborting restore", file=sys.stderr)
        return 1

    # Extract the archive
    cmd = ["tar", "xzf", str(dest), "-C", str(root_resolved.parent)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: Restore failed: {result.stderr.strip()}", file=sys.stderr)
        return 1

    print(f"Restored from backup: {timestamp}")
    return 0


def cmd_list(root: Path) -> int:
    """List all available backups for this wiki."""
    backups = list_backups(root)
    if not backups:
        print("No backups found")
        return 0

    print(f"Available backups for '{wiki_name(root)}':")
    for b in backups:
        ts = parse_timestamp(b)
        size = format_size(b.stat().st_size)
        age = format_age(b.stat().st_mtime)
        print(f"  {ts}  {size:>8}  {age}")
    return 0


def cmd_verify(root: Path) -> int:
    """Check wiki integrity: wikilinks, frontmatter, empty files, required files."""
    root_resolved = root.resolve()
    layout = discover_layout(root)
    wiki_dir = Path(layout.pages_dir)

    issues = 0

    # ── a. All [[wikilinks]] resolve ───────────────────────────────────────
    if wiki_dir.is_dir():
        pages: dict[str, Path] = {}
        for p in wiki_dir.rglob("*.md"):
            pages[p.stem] = p
            rel = p.relative_to(wiki_dir)
            pages[str(rel.with_suffix(""))] = p

        dead_links: list[tuple[str, str]] = []
        for md_file in wiki_dir.rglob("*.md"):
            text = md_file.read_text(encoding="utf-8")
            for link in WIKILINK_RE.findall(text):
                link = link.strip()
                if link not in pages and Path(link).stem not in pages:
                    dead_links.append((str(md_file.relative_to(root_resolved)), link))

        if dead_links:
            print(f"Dead wikilinks ({len(dead_links)}):")
            for src, lnk in dead_links:
                print(f"  {src} -> [[{lnk}]]")
            issues += len(dead_links)
    else:
        print(f"wiki/ directory not found at {wiki_dir}", file=sys.stderr)
        issues += 1

    # ── b. Valid YAML frontmatter with title/type/created ──────────────────
    if wiki_dir.is_dir():
        fm_issues: list[str] = []
        for md_file in wiki_dir.rglob("*.md"):
            text = md_file.read_text(encoding="utf-8")
            fm = parse_frontmatter(text)
            rel = md_file.relative_to(root_resolved)
            if fm is None:
                fm_issues.append(f"{rel} — no YAML frontmatter")
                continue
            if "title" not in fm:
                fm_issues.append(f"{rel} — missing 'title'")
            if "type" not in fm:
                fm_issues.append(f"{rel} — missing 'type'")
            if "created" not in fm:
                fm_issues.append(f"{rel} — missing 'created'")

        if fm_issues:
            print(f"Frontmatter issues ({len(fm_issues)}):")
            for s in fm_issues:
                print(f"  {s}")
            issues += len(fm_issues)

    # ── c. No empty files ──────────────────────────────────────────────────
    empty_issues: list[str] = []
    patterns = []
    pages_rel = Path(layout.pages_dir).relative_to(root_resolved)
    patterns.append(f"{pages_rel}/**/*.md")
    if layout.audit_dir:
        audit_rel = Path(layout.audit_dir).relative_to(root_resolved)
        patterns.append(f"{audit_rel}/**/*.md")
    if layout.log_dir:
        log_rel = Path(layout.log_dir).relative_to(root_resolved)
        patterns.append(f"{log_rel}/**/*.md")
    for pattern in patterns:
            if p.stat().st_size == 0:
                empty_issues.append(str(p.relative_to(root_resolved)))
    if empty_issues:
        print(f"Empty files ({len(empty_issues)}):")
        for s in empty_issues:
            print(f"  {s}")
        issues += len(empty_issues)

    # ── d. Schema and purpose files exist ──────────────────────────────────
    required_files = []
    if layout.schema_file:
        required_files.append(Path(layout.schema_file).name)
    if layout.purpose_file:
        required_files.append(Path(layout.purpose_file).name)
    if not required_files:
        required_files = ["CLAUDE.md", "PURPOSE.md"]
    missing_required: list[str] = []
    for fname in required_files:
        if not (root_resolved / fname).exists():
            missing_required.append(fname)
    if missing_required:
        print(f"Missing required files: {', '.join(missing_required)}")
        issues += len(missing_required)

    if issues == 0:
        print("Wiki integrity check passed")
        return 0
    else:
        print(f"{issues} issue(s) found", file=sys.stderr)
        return 1


def cmd_prune(root: Path, keep: int) -> int:
    """Keep only the N most recent backups, delete older ones."""
    backups = list_backups(root)
    if len(backups) <= keep:
        print("Nothing to prune")
        return 0

    to_delete = backups[keep:]
    for b in to_delete:
        b.unlink()
        print(f"Deleted: {b.name}")

    print(f"Pruned {len(to_delete)} backup(s), kept {keep}")
    return 0


def cmd_auto(root: Path) -> int:
    """Snapshot + prune to last 10 + verify — one-command safe state."""
    print("=== Auto: Snapshot ===")
    if cmd_snapshot(root) != 0:
        return 1

    print(f"\n=== Auto: Prune (keep {KEEP}) ===")
    cmd_prune(root, KEEP)

    print("\n=== Auto: Verify ===")
    return cmd_verify(root)


# ── Entry point ─────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backup and recovery for LLM wikis — snapshots, restoration, and integrity checks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 backup.py ~/my-wiki --snapshot\n"
            "  python3 backup.py ~/my-wiki --restore 20260101-120000\n"
            "  python3 backup.py ~/my-wiki --list\n"
            "  python3 backup.py ~/my-wiki --verify\n"
            "  python3 backup.py ~/my-wiki --prune 5\n"
            "  python3 backup.py ~/my-wiki --auto"
        ),
    )
    parser.add_argument("wiki_path", help="Path to the wiki root directory")
    parser.add_argument("--snapshot", action="store_true", help="Create a timestamped tar.gz snapshot")
    parser.add_argument("--restore", metavar="TIMESTAMP", help="Restore from a backup by timestamp")
    parser.add_argument("--list", action="store_true", help="List all available backups")
    parser.add_argument("--verify", action="store_true", help="Check wiki integrity")
    parser.add_argument("--prune", metavar="N", type=int, help="Keep only N most recent backups")
    parser.add_argument("--auto", action="store_true", help="Snapshot + prune to 10 + verify")

    args = parser.parse_args()
    root = Path(args.wiki_path).resolve()

    if not root.is_dir():
        print(f"ERROR: {args.wiki_path} is not a valid directory", file=sys.stderr)
        return 1

    action_count = sum([args.snapshot, args.restore is not None, args.list, args.verify, args.prune is not None, args.auto])
    if action_count == 0:
        parser.print_help()
        return 1
    if action_count > 1:
        print("ERROR: Specify only one action (--snapshot, --restore, --list, --verify, --prune, or --auto)",
              file=sys.stderr)
        return 1

    if args.snapshot:
        return cmd_snapshot(root)
    elif args.restore:
        return cmd_restore(root, args.restore)
    elif args.list:
        return cmd_list(root)
    elif args.verify:
        return cmd_verify(root)
    elif args.prune is not None:
        return cmd_prune(root, args.prune)
    elif args.auto:
        return cmd_auto(root)

    return 0


if __name__ == "__main__":
    sys.exit(main())
