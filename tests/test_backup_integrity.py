"""test_backup_integrity.py — Atomic, verifiable snapshots and staged restores (D08-04).

Covers:
  - snapshot -> digest + tar listing verification passes
  - truncated / tampered archives fail verification loudly
  - restore round-trips through a staging directory into a fresh tree
  - two snapshots in the same second never clobber each other
  - failed restores leave the live tree untouched
"""

import gzip
import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from llm_wiki.wiki.backup import (
    backups_dir,
    cmd_prune,
    cmd_restore,
    cmd_snapshot,
    cmd_verify,
    cmd_verify_snapshot,
    digest_path,
    list_backups,
    parse_timestamp,
)


def _make_wiki(tmp_path: Path) -> Path:
    """Create a minimal, verifiable wiki tree with one content page."""
    root = tmp_path / "integrity-wiki"
    pages = root / "wiki"
    (root / "audit").mkdir(parents=True)
    (root / "log").mkdir(parents=True)
    pages.mkdir(parents=True)
    (pages / "index.md").write_text(
        "---\ntitle: Index\ntype: index\ncreated: 2026-01-01\n---\n\n# Index\n\nContent.\n",
        encoding="utf-8",
    )
    (pages / "page.md").write_text(
        "---\ntitle: Page\ntype: concept\ncreated: 2026-01-01\n---\n\n# Page\n\nOriginal body.\n",
        encoding="utf-8",
    )
    (root / "CLAUDE.md").write_text("# Schema\n", encoding="utf-8")
    (root / "PURPOSE.md").write_text("# Purpose\n", encoding="utf-8")
    return root


class TestSnapshotAtomicity:
    """Snapshots land atomically with a verifiable digest sidecar."""

    def test_snapshot_then_verify_passes(self, tmp_path):
        root = _make_wiki(tmp_path)
        assert cmd_snapshot(root) == 0

        backups = list_backups(root)
        assert len(backups) == 1
        archive = backups[0]
        assert archive.exists() and archive.stat().st_size > 0
        assert digest_path(archive).exists()

        # No temp archive is left behind after the atomic replace.
        leftovers = [p.name for p in backups_dir(root).iterdir() if ".tmp." in p.name]
        assert leftovers == []

        assert cmd_verify_snapshot(archive) == 0
        assert cmd_verify(root, latest=True) == 0

    def test_same_second_double_snapshot_does_not_clobber(self, tmp_path):
        root = _make_wiki(tmp_path)
        assert cmd_snapshot(root) == 0
        assert cmd_snapshot(root) == 0

        backups = list_backups(root)
        assert len(backups) == 2, f"second snapshot clobbered the first: {backups}"
        assert len({b.name for b in backups}) == 2
        for b in backups:
            assert b.exists()
            assert cmd_verify_snapshot(b) == 0

    def test_prune_removes_digest_sidecars(self, tmp_path):
        root = _make_wiki(tmp_path)
        for _ in range(3):
            assert cmd_snapshot(root) == 0
        assert cmd_prune(root, 1) == 0

        remaining = list_backups(root)
        assert len(remaining) == 1
        assert digest_path(remaining[0]).exists()
        assert len(list(backups_dir(root).glob("*.sha256"))) == 1


class TestSnapshotVerification:
    """Corruption is detected loudly by digest and/or tar listing."""

    def test_truncated_archive_fails_verify(self, tmp_path):
        root = _make_wiki(tmp_path)
        assert cmd_snapshot(root) == 0
        archive = list_backups(root)[0]

        data = archive.read_bytes()
        archive.write_bytes(data[: max(1, len(data) // 2)])

        assert cmd_verify_snapshot(archive) != 0
        assert cmd_verify(root, latest=True) != 0

    def test_valid_digest_but_corrupt_listing_fails(self, tmp_path):
        root = _make_wiki(tmp_path)
        assert cmd_snapshot(root) == 0
        archive = list_backups(root)[0]

        # Valid gzip stream that is not a tar archive, with a matching digest:
        # only the `tar -tzf` listing check can catch this.
        data = gzip.compress(b"B" * 1024)
        archive.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        digest_path(archive).write_text(f"{digest}  {archive.name}\n", encoding="utf-8")

        assert cmd_verify_snapshot(archive) != 0

    def test_missing_digest_fails_verify(self, tmp_path):
        root = _make_wiki(tmp_path)
        assert cmd_snapshot(root) == 0
        archive = list_backups(root)[0]
        digest_path(archive).unlink()

        assert cmd_verify_snapshot(archive) != 0


class TestRestoreIntegrity:
    """Restores are verified first and swapped in from a staging directory."""

    def test_round_trip_restore_recreates_tree(self, tmp_path):
        root = _make_wiki(tmp_path)
        page = root / "wiki" / "page.md"
        original = page.read_text(encoding="utf-8")
        assert cmd_snapshot(root) == 0
        archive = list_backups(root)[0]
        timestamp = parse_timestamp(archive)

        # Simulate a clobbered tree: wipe pages and add a stray file.
        pages = root / "wiki"
        for child in pages.iterdir():
            child.unlink()
        (pages / "scratch.md").write_text("scratch", encoding="utf-8")

        assert cmd_restore(root, timestamp) == 0
        assert page.read_text(encoding="utf-8") == original
        assert not (pages / "scratch.md").exists()
        assert cmd_verify(root) == 0

        # Staging directory is always cleaned up.
        assert list(backups_dir(root).glob(".restore-staging-*")) == []

    def test_corrupt_archive_restore_aborts_before_touching_tree(self, tmp_path):
        root = _make_wiki(tmp_path)
        assert cmd_snapshot(root) == 0
        archive = list_backups(root)[0]
        timestamp = parse_timestamp(archive)

        data = archive.read_bytes()
        archive.write_bytes(data[: max(1, len(data) // 2)])

        page = root / "wiki" / "page.md"
        page.write_text("live change", encoding="utf-8")

        assert cmd_restore(root, timestamp) != 0

        # The live tree is untouched and no pre-restore snapshot was taken.
        assert page.read_text(encoding="utf-8") == "live change"
        assert len(list_backups(root)) == 1
        assert list(backups_dir(root).glob(".restore-staging-*")) == []

    def test_restore_unknown_timestamp_fails(self, tmp_path):
        root = _make_wiki(tmp_path)
        assert cmd_snapshot(root) == 0
        assert cmd_restore(root, "19700101-000000") != 0
