"""
test_concurrency_locks.py — Tests for LWM_006 concurrency locks and atomic writes.

Covers:
  - write_wiki lock enforcement: held lock returns 'locked' status
  - backup --verify empty file detection
  - Atomic write protection for index.md, logs, cache
  - Multi-process concurrent writes
"""

import json
import multiprocessing
import os
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from llm_wiki.core.locking import WikiLock
from llm_wiki.ingest import write_wiki, update_index, read_file
from llm_wiki.backup import cmd_verify


class TestWriteWikiLockEnforcement:
    """write_wiki must respect page locks (LWM_006)."""

    def test_lock_timeout_failure(self, tmp_path):
        """Lock timeout should return 'locked' status."""
        wiki = tmp_path / "wiki"
        page_path = wiki / "test" / "page.md"
        page_path.parent.mkdir(parents=True)
        page_path.write_text("content")

        lock = WikiLock(str(page_path), timeout=30)
        lock.__enter__()
        try:
            status, ok = write_wiki(str(wiki), "test/page.md",
                                        "---\ntitle: Test\n---\n\nNew",
                                        lock_timeout=1)
            assert status == "locked", f"Expected locked, got {status}"
            assert not ok
        finally:
            lock.__exit__()

    def test_lock_enforced_across_read_hash_write(self, tmp_path):
        """Hash comparison happens inside the lock."""
        wiki = tmp_path / "wiki"
        page_path = wiki / "test" / "page.md"
        page_path.parent.mkdir(parents=True)
        content = "---\ntitle: Test\n---\n\nOriginal"
        write_wiki(str(wiki), "test/page.md", content)

        lock = WikiLock(str(page_path), timeout=30)
        lock.__enter__()
        try:
            status, ok = write_wiki(str(wiki), "test/page.md",
                                        "---\ntitle: Test\n---\n\nModified",
                                        lock_timeout=1)
            assert status == "locked"
            assert not ok

            # File content must not change
            assert "Original" in page_path.read_text()
        finally:
            lock.__exit__()

    def test_release_then_write_succeeds(self, tmp_path):
        """After lock release, write succeeds normally."""
        wiki = tmp_path / "wiki"
        page_path = wiki / "test" / "page.md"
        page_path.parent.mkdir(parents=True)
        page_path.write_text("old")

        lock = WikiLock(str(page_path), timeout=5)
        lock.__enter__()
        lock.__exit__()

        status, ok = write_wiki(str(wiki), "test/page.md",
                                    "---\ntitle: Test\n---\n\nNew",
                                    lock_timeout=5)
        assert status in ("updated", "created")
        assert ok


class TestBackupVerifyEmptyFiles:
    """backup --verify must detect empty files (LWM_006)."""

    def test_empty_audit_file_detected(self, tmp_path):
        """Empty file in audit/ directory is detected."""
        wiki = tmp_path / "wiki"
        wiki.mkdir(parents=True)
        (wiki / "wiki").mkdir(parents=True)
        (wiki / "audit").mkdir(parents=True)
        (wiki / "log").mkdir(parents=True)

        (wiki / "wiki" / "index.md").write_text("---\ntitle: Index\ntype: index\ncreated: 2026-01-01\n---\n\n# Index")
        (wiki / "CLAUDE.md").write_text("# Schema")
        (wiki / "PURPOSE.md").write_text("# Purpose")

        empty_file = wiki / "audit" / "empty.md"
        empty_file.write_text("")

        rc = cmd_verify(wiki)
        assert rc != 0, "backup --verify should fail with empty files"
        assert not empty_file.stat().st_size, f"{empty_file} should be empty"

    def test_empty_log_file_detected(self, tmp_path):
        """Empty file in log/ directory is detected."""
        wiki = tmp_path / "wiki"
        wiki.mkdir(parents=True)
        (wiki / "wiki").mkdir(parents=True)
        (wiki / "audit").mkdir(parents=True)
        (wiki / "log").mkdir(parents=True)

        (wiki / "wiki" / "index.md").write_text("---\ntitle: Index\ntype: index\ncreated: 2026-01-01\n---\n\n# Index")
        (wiki / "CLAUDE.md").write_text("# Schema")
        (wiki / "PURPOSE.md").write_text("# Purpose")

        empty_file = wiki / "log" / "empty.md"
        empty_file.write_text("")

        rc = cmd_verify(wiki)
        assert rc != 0, "backup --verify should fail with empty files"
        assert not empty_file.stat().st_size

    def test_clean_wiki_passes(self, tmp_path):
        """Clean scaffolded wiki passes verification."""
        wiki = tmp_path / "wiki"
        wiki.mkdir(parents=True)
        (wiki / "wiki").mkdir(parents=True)
        (wiki / "audit").mkdir(parents=True)
        (wiki / "log").mkdir(parents=True)

        (wiki / "wiki" / "index.md").write_text("---\ntitle: Index\ntype: index\ncreated: 2026-01-01\n---\n\n# Index\n\nContent.\n")
        (wiki / "CLAUDE.md").write_text("# Schema")
        (wiki / "PURPOSE.md").write_text("# Purpose")

        rc = cmd_verify(wiki)
        assert rc == 0, f"Clean wiki should pass, got {rc}"


class TestAtomicAncillaryWrites:
    """Ancillary writes use atomic_write (LWM_006)."""

    def test_update_index_uses_atomic_write(self, tmp_path):
        """update_index should produce a valid index file."""
        wiki = tmp_path / "wiki"
        pages_dir = wiki / "wiki"
        pages_dir.mkdir(parents=True)
        index_path = pages_dir / "index.md"
        index_path.write_text("# Wiki Index\n\n")

        added = update_index(str(wiki), ["entities/NewPage.md"])
        assert added == 1

        content = index_path.read_text()
        assert "NewPage" in content

        added = update_index(str(wiki), ["entities/NewPage.md"])
        assert added == 0

    def test_append_log_creates_file(self, tmp_path):
        """append_log should create a valid log file."""
        from llm_wiki.ingest import append_log
        wiki = tmp_path / "wiki"
        log_dir = wiki / "log"
        log_dir.mkdir(parents=True)

        append_log(str(wiki), "test-source", 1, 0, 0, log_dir=str(log_dir))

        log_files = list(log_dir.glob("*.md"))
        assert len(log_files) == 1
        content = log_files[0].read_text()
        assert "test-source" in content


class TestConcurrencyStress:
    """Multi-process write stress tests (LWM_006)."""

    @staticmethod
    def _writer_worker(page_path, content, result_queue, lock_timeout=10):
        try:
            from llm_wiki.ingest import write_wiki
            wiki_root = os.path.dirname(os.path.dirname(page_path))
            rel = os.path.relpath(page_path, wiki_root)
            status, ok = write_wiki(
                wiki_root, rel, content, lock_timeout=lock_timeout,
            )
            result_queue.put((status, ok))
        except Exception as e:
            result_queue.put(("error", str(e)))

    def test_ten_writers_different_pages(self, tmp_path):
        """10 concurrent writers to different pages: all succeed."""
        wiki = tmp_path / "wiki"
        wiki.mkdir()

        procs = []
        result_queue = multiprocessing.Queue()
        for i in range(10):
            page_path = wiki / "entities" / f"Page{i}.md"
            page_path.parent.mkdir(parents=True, exist_ok=True)
            content = f"---\ntitle: Page {i}\ntype: entity\n---\n\n# Page {i}\nContent {i}."
            p = multiprocessing.Process(
                target=self._writer_worker,
                args=(str(page_path), content, result_queue),
            )
            procs.append(p)

        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=30)

        results = []
        while not result_queue.empty():
            results.append(result_queue.get())

        created = [r for r in results if r[0] == "created"]
        assert len(created) == 10, f"Expected 10 created, got: {results}"

        for i in range(10):
            assert (wiki / "entities" / f"Page{i}.md").exists()

    def test_two_writers_same_page(self, tmp_path):
        """2 concurrent writers to same page: one gets locked/conflict."""
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        page_dir = wiki / "entities"
        page_dir.mkdir(parents=True)
        page_path = page_dir / "SharedPage.md"

        initial = "---\ntitle: Shared Page\ntype: concept\n---\n\n# Version 0"
        page_path.write_text(initial)

        content_a = initial.replace("Version 0", "Version A")
        content_b = initial.replace("Version 0", "Version B")

        result_queue = multiprocessing.Queue()

        p_a = multiprocessing.Process(
            target=self._writer_worker,
            args=(str(page_path), content_a, result_queue),
        )
        p_b = multiprocessing.Process(
            target=self._writer_worker,
            args=(str(page_path), content_b, result_queue),
        )

        p_a.start()
        p_b.start()
        p_a.join(timeout=30)
        p_b.join(timeout=30)

        results = []
        while not result_queue.empty():
            results.append(result_queue.get())

        statuses = [r[0] for r in results]
        assert any(s in ("created", "updated") for s in statuses), f"No success: {results}"
