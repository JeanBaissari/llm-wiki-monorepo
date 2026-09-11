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
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path


from llm_wiki.core.layout import discover_layout
from llm_wiki.core.frontmatter import FRONTMATTER_RE, parse_frontmatter
from llm_wiki.core.wikilinks import WIKILINK_RE

KEEP = 10  # default number of backups to keep when pruning
DIGEST_SUFFIX = ".sha256"


def wiki_name(root: Path) -> str:
    """Derive a short wiki name from the wiki-root directory name."""
    return root.resolve().name


def backups_dir(root: Path) -> Path:
    """Return the backups directory (sibling to the wiki-root)."""
    return root.resolve().parent / "backups"


def snapshot_path(root: Path, timestamp: str | None = None) -> Path:
    """Generate a collision-proof path for a backup snapshot.

    Names keep the recognizable ``<wiki>-<YYYYmmdd-HHMMSS>.tar.gz`` shape and
    add microseconds plus the PID so two snapshots in the same second (or two
    concurrent snapshotters) can never clobber each other.
    """
    bdir = backups_dir(root)
    name = wiki_name(root)
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        return bdir / f"{name}-{timestamp}-{os.getpid()}.tar.gz"
    return bdir / f"{name}-{timestamp}.tar.gz"


def parse_timestamp(path: Path) -> str:
    """Extract the full timestamp handle from a backup filename.

    Returns ``YYYYmmdd-HHMMSS`` for legacy names and the complete
    ``YYYYmmdd-HHMMSS-ffffff[-pid]`` handle for new ones, so callers can round
    trip a listing back into a ``--restore`` argument unambiguously.
    """
    name = path.name
    if name.endswith(".tar.gz"):
        name = name[: -len(".tar.gz")]
    elif name.endswith(".tar"):
        name = name[:-4]
    m = re.search(r"(\d{8}-\d{6}(?:-\d{6})?(?:-\d+)?)$", name)
    return m.group(1) if m else name


def find_backup(root: Path, timestamp: str) -> Path:
    """Resolve a restore timestamp to a concrete backup archive.

    Prefers an exact filename match, then the newest archive whose name starts
    with the requested timestamp prefix (legacy second-granularity timestamps
    keep selecting the newest snapshot in that second).
    """
    bdir = backups_dir(root)
    name = wiki_name(root)
    exact = bdir / f"{name}-{timestamp}.tar.gz"
    if exact.exists():
        return exact
    candidates = [
        Path(p) for p in glob.glob(str(bdir / f"{name}-{timestamp}*.tar.gz"))
    ]
    if candidates:
        return max(candidates, key=lambda p: p.stat().st_mtime)
    return exact


def digest_path(archive: Path) -> Path:
    """Return the sidecar digest path for a snapshot archive."""
    return archive.with_name(archive.name + DIGEST_SUFFIX)


def _sha256_file(path: Path) -> str:
    """Compute the SHA256 digest of a file without loading it all in memory."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_digest(archive: Path, digest: str) -> None:
    """Persist the archive digest atomically next to the archive."""
    sidecar = digest_path(archive)
    tmp = sidecar.with_name(f".{sidecar.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}")
    try:
        tmp.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
        os.replace(tmp, sidecar)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


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
    """Create a timestamped tar.gz snapshot of the wiki.

    The archive is built in the backups directory under a temp name and then
    atomically renamed into place (``os.replace``), so a crash can never
    leave a half-written archive under a valid backup name. A ``.sha256``
    sidecar digest is persisted for later verification.
    """
    root_resolved = root.resolve()
    if not root_resolved.is_dir():
        print(f"ERROR: {root} is not a valid directory", file=sys.stderr)
        return 1

    bdir = backups_dir(root)
    bdir.mkdir(parents=True, exist_ok=True)

    dest = snapshot_path(root)
    tmp_dest = bdir / (
        f".{dest.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}"
    )
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
        "tar", "czf", str(tmp_dest),
        "--exclude", "raw",
        "--exclude", "node_modules",
        "--exclude", "dist",
    ]
    for item in include_items:
        path = root_resolved / item
        if path.exists():
            cmd.extend(["-C", str(parent_dir), f"{base_name}/{item}"])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"ERROR: tar failed: {result.stderr.strip()}", file=sys.stderr)
            return 1

        digest = _sha256_file(tmp_dest)
        os.replace(tmp_dest, dest)
    finally:
        if tmp_dest.exists():
            try:
                tmp_dest.unlink()
            except OSError:
                pass

    try:
        _write_digest(dest, digest)
    except OSError as e:
        print(f"ERROR: Could not write integrity digest for {dest.name}: {e}", file=sys.stderr)
        return 1

    size_bytes = dest.stat().st_size
    file_count = count_files_in_tar(dest)
    print(f"Snapshot created: {dest} ({format_size(size_bytes)}, {file_count} files)")
    return 0


def _swap_staged_tree(root: Path, staged_root: Path) -> None:
    """Move staged top-level items into ``root``, one atomic swap each.

    Directories are displaced before the staged copy is moved in, so an
    interrupted restore can only ever leave either the old or the new tree at
    each top-level item — never a mixed set of files. ``raw/`` (sources) and
    other items absent from the backup are left untouched.
    """
    for item in sorted(staged_root.iterdir(), key=lambda p: p.name):
        target = root / item.name
        if item.is_dir() and not item.is_symlink() and target.is_dir() and not target.is_symlink():
            displaced = root / f".{item.name}.pre-restore.{uuid.uuid4().hex}"
            os.replace(target, displaced)
            try:
                os.replace(item, target)
            except OSError:
                os.replace(displaced, target)  # roll back
                raise
            shutil.rmtree(displaced, ignore_errors=True)
        else:
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            os.replace(item, target)


def cmd_restore(root: Path, timestamp: str) -> int:
    """Restore wiki from a backup snapshot, with auto pre-restore backup.

    The archive is integrity-verified first, then extracted into a staging
    directory inside the backups dir, and only then swapped into place. A
    corrupt archive or an interrupted extraction never touches the live tree.
    """
    root_resolved = root.resolve()
    dest = find_backup(root, timestamp)

    if not dest.exists():
        print(f"ERROR: Backup not found: {dest}", file=sys.stderr)
        return 1

    # Fail loudly before touching anything if the archive is corrupt.
    if cmd_verify_snapshot(dest) != 0:
        print("ERROR: Backup failed integrity verification — aborting restore", file=sys.stderr)
        return 1

    # Pre-restore snapshot
    print(f"Creating pre-restore backup...", file=sys.stderr)
    if cmd_snapshot(root) != 0:
        print("ERROR: Pre-restore backup failed — aborting restore", file=sys.stderr)
        return 1

    bdir = backups_dir(root)
    staging = Path(tempfile.mkdtemp(prefix=".restore-staging-", dir=str(bdir)))
    try:
        cmd = ["tar", "xzf", str(dest), "-C", str(staging)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"ERROR: Restore failed: {result.stderr.strip()}", file=sys.stderr)
            return 1

        staged_root = staging / root_resolved.name
        if not staged_root.is_dir():
            staged_root = staging
        _swap_staged_tree(root_resolved, staged_root)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

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


def cmd_verify_snapshot(archive: Path) -> int:
    """Verify a single snapshot archive: digest sidecar + full tar listing.

    Two independent checks, both must pass:
      1. The ``.sha256`` sidecar digest matches the archive bytes.
      2. ``tar -tzf`` can decompress and parse the whole archive.

    Fails loudly (nonzero) on a missing sidecar, digest mismatch, truncated
    gzip stream, or non-tar content.
    """
    archive = Path(archive)
    if not archive.exists():
        print(f"ERROR: Backup not found: {archive}", file=sys.stderr)
        return 1

    sidecar = digest_path(archive)
    if not sidecar.exists():
        print(f"ERROR: Missing integrity digest: {sidecar.name}", file=sys.stderr)
        return 1

    try:
        parts = sidecar.read_text(encoding="utf-8").split()
        expected = parts[0]
    except (OSError, IndexError):
        print(f"ERROR: Unreadable integrity digest: {sidecar.name}", file=sys.stderr)
        return 1

    try:
        actual = _sha256_file(archive)
    except OSError as e:
        print(f"ERROR: Cannot read archive {archive.name}: {e}", file=sys.stderr)
        return 1

    if expected != actual:
        print(
            f"ERROR: Digest mismatch for {archive.name}: "
            f"expected {expected[:16]}..., got {actual[:16]}...",
            file=sys.stderr,
        )
        return 1

    listing = subprocess.run(
        ["tar", "-tzf", str(archive)], capture_output=True, text=True
    )
    if listing.returncode != 0:
        print(
            f"ERROR: Corrupt archive {archive.name}: {listing.stderr.strip()}",
            file=sys.stderr,
        )
        return 1
    entries = [line for line in listing.stdout.splitlines() if line.strip()]
    if not entries:
        print(f"ERROR: Empty archive: {archive.name}", file=sys.stderr)
        return 1

    print(f"Backup verified: {archive.name} ({len(entries)} entries, sha256 {actual[:12]}...)")
    return 0


def cmd_verify(root: Path, latest: bool = False) -> int:
    """Check wiki integrity: wikilinks, frontmatter, empty files, required files.

    With ``latest=True``, also verify the newest backup archive (digest +
    listing). A missing backup is an error in that mode.
    """
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
    pages_rel = Path(layout.pages_dir).relative_to(root_resolved)
    for pattern_dir in [pages_rel] + ([Path(layout.audit_dir).relative_to(root_resolved)] if layout.audit_dir else []) + ([Path(layout.log_dir).relative_to(root_resolved)] if layout.log_dir else []):
        for p in root_resolved.glob(f"{pattern_dir}/**/*.md"):
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

    # ── e. Latest backup archive (opt-in via --latest) ─────────────────────
    if latest:
        backups = list_backups(root)
        if not backups:
            print("ERROR: No backups found to verify", file=sys.stderr)
            issues += 1
        elif cmd_verify_snapshot(backups[0]) != 0:
            issues += 1

    if issues == 0:
        print("Wiki integrity check passed")
        return 0
    else:
        print(f"{issues} issue(s) found", file=sys.stderr)
        return 1


def cmd_prune(root: Path, keep: int) -> int:
    """Keep only the N most recent backups, delete older ones (and digests)."""
    backups = list_backups(root)
    if len(backups) <= keep:
        print("Nothing to prune")
        return 0

    to_delete = backups[keep:]
    for b in to_delete:
        b.unlink()
        sidecar = digest_path(b)
        if sidecar.exists():
            sidecar.unlink()
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

    print("\n=== Auto: Verify backup ===")
    backups = list_backups(root)
    if not backups or cmd_verify_snapshot(backups[0]) != 0:
        return 1

    print("\n=== Auto: Verify wiki ===")
    return cmd_verify(root)


# ── Entry point ─────────────────────────────────────────────────────────────

_POSITIONAL_ACTIONS = {
    "snapshot": "--snapshot",
    "list": "--list",
    "verify": "--verify",
    "auto": "--auto",
}


def _normalize_argv(argv: list[str]) -> list[str]:
    """Accept ``backup.py <wiki> verify --latest`` as well as ``--verify``.

    Keeps the historical flag-based contract working while allowing the
    action-first form used by scripts and docs.
    """
    if len(argv) >= 3 and argv[1] == "restore":
        return [argv[0], "--restore", argv[2]] + argv[3:]
    if len(argv) >= 2 and argv[1] in _POSITIONAL_ACTIONS:
        return [argv[0], _POSITIONAL_ACTIONS[argv[1]]] + argv[2:]
    return argv


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
            "  python3 backup.py ~/my-wiki --verify --latest\n"
            "  python3 backup.py ~/my-wiki verify --latest\n"
            "  python3 backup.py ~/my-wiki --prune 5\n"
            "  python3 backup.py ~/my-wiki --auto"
        ),
    )
    parser.add_argument("wiki_path", help="Path to the wiki root directory")
    parser.add_argument("--snapshot", action="store_true", help="Create a timestamped tar.gz snapshot")
    parser.add_argument("--restore", metavar="TIMESTAMP", help="Restore from a backup by timestamp")
    parser.add_argument("--list", action="store_true", help="List all available backups")
    parser.add_argument("--verify", action="store_true", help="Check wiki integrity")
    parser.add_argument("--latest", action="store_true",
                        help="With --verify: also verify digest + listing of the latest backup")
    parser.add_argument("--prune", metavar="N", type=int, help="Keep only N most recent backups")
    parser.add_argument("--auto", action="store_true", help="Snapshot + prune to 10 + verify")

    args = parser.parse_args(_normalize_argv(sys.argv[1:]))
    root = Path(args.wiki_path).resolve()

    if not root.is_dir():
        print(f"ERROR: {args.wiki_path} is not a valid directory", file=sys.stderr)
        return 1

    if args.latest and not args.verify:
        print("ERROR: --latest requires --verify", file=sys.stderr)
        return 1

    action_count = sum([args.snapshot, args.restore is not None, args.list, args.verify, args.prune is not None, args.auto])
    if action_count == 0:
        parser.print_help()
        return 1
    if action_count > 1:
        print("ERROR: Specify only one action (--snapshot, --restore, --list, --verify, --prune, or --auto)",
              file=sys.stderr)
        return 1

    from llm_wiki.operation import OperationContext

    if args.snapshot:
        with OperationContext("backup.snapshot", wiki_root=str(root)) as ctx:
            ec = cmd_snapshot(root)
            ctx.set_status("succeeded" if ec == 0 else "failed")
        return ec
    elif args.restore:
        with OperationContext("backup.restore", wiki_root=str(root),
                               inputs={"timestamp": args.restore}) as ctx:
            ec = cmd_restore(root, args.restore)
            ctx.set_status("succeeded" if ec == 0 else "failed")
        return ec
    elif args.list:
        return cmd_list(root)
    elif args.verify:
        return cmd_verify(root, latest=args.latest)
    elif args.prune is not None:
        with OperationContext("backup.prune", wiki_root=str(root),
                               inputs={"keep": args.prune}) as ctx:
            ec = cmd_prune(root, args.prune)
            ctx.set_status("succeeded" if ec == 0 else "failed")
        return ec
    elif args.auto:
        with OperationContext("backup.auto", wiki_root=str(root)) as ctx:
            ec = cmd_auto(root)
            ctx.set_status("succeeded" if ec == 0 else "failed")
        return ec

    return 0


if __name__ == "__main__":
    sys.exit(main())
