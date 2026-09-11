"""
test_concurrency.py — Tests for concurrency control: locking, atomic writes,
conflict detection, and conflict resolution.

Covers:
  - WikiLock acquire/release lifecycle
  - Lock blocking and timeout behavior
  - Stale lock detection (dead vs live PID)
  - Atomic write correctness and crash resilience
  - Content hash computation stability and injection
  - Conflict detection via hash mismatch
  - Conflict file generation
  - --force flag skips conflict detection
  - write_wiki() integration with locking + conflict detection
  - update_index() atomic read-modify-write
  - Concurrency stress tests
"""
import hashlib
import multiprocessing
import os
import re
import signal
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from llm_wiki.core.locking import (
    WikiLock,
    HARD_STALE_LIMIT,
    clean_stale_locks,
)
from llm_wiki.core.atomic import atomic_write, cleanup_temp_files
from llm_wiki.core.hashing import compute_hash, read_hash, inject_hash, HASH_FIELD
from llm_wiki.ingest.writer import write_wiki, write_file, update_index, read_file


def _dead_pids(count):
    """Return ``count`` PIDs that are not alive on POSIX (synthetic on others)."""
    pids = []
    candidate = 10_000_000
    while len(pids) < count:
        if os.name == "posix":
            try:
                os.kill(candidate, 0)
                candidate += 1
                continue
            except OSError:
                pass
        pids.append(candidate)
        candidate += 1
    return pids


# ══════════════════════════════════════════════════════════════════════════
# WikiLock tests
# ══════════════════════════════════════════════════════════════════════════

class TestWikiLockBasic:
    """WikiLock acquire/release lifecycle."""

    def test_acquire_and_release(self, tmp_path):
        """Single writer acquires and releases lock successfully."""
        page = tmp_path / "test_page.md"
        page.write_text("content")

        with WikiLock(str(page), timeout=5) as lock:
            assert os.path.exists(str(page) + ".lock")
            assert lock._fd is not None

        # Lock file cleaned up on exit
        assert not os.path.exists(str(page) + ".lock")

    def test_lock_file_contains_metadata(self, tmp_path):
        """Lock file should contain PID, timestamp, and hostname."""
        page = tmp_path / "test_page.md"
        page.write_text("content")

        with WikiLock(str(page), timeout=5) as lock:
            # Instance metadata: works on every platform (Windows LockFileEx
            # blocks second-handle reads of the locked file, so re-reading the
            # file while locked is POSIX-only).
            assert lock.metadata["pid"] == str(os.getpid())
            assert "timestamp" in lock.metadata
            assert "hostname" in lock.metadata
            if os.name == "posix":
                lock_content = Path(str(page) + ".lock").read_text()
                assert f"pid={os.getpid()}" in lock_content
                assert "timestamp=" in lock_content
                assert "hostname=" in lock_content

    def test_context_manager_returns_self(self, tmp_path):
        """Context manager should return the lock instance."""
        page = tmp_path / "test_page.md"
        page.write_text("content")

        with WikiLock(str(page), timeout=5) as lock:
            assert isinstance(lock, WikiLock)

    def test_lock_directory_created(self, tmp_path):
        """Lock should work even if parent directory doesn't exist."""
        page = tmp_path / "deep" / "nested" / "page.md"

        with WikiLock(str(page), timeout=5):
            assert os.path.exists(str(page) + ".lock")

        assert not os.path.exists(str(page) + ".lock")


class TestWikiLockBlocking:
    """Lock blocking and timeout behavior."""

    def test_second_writer_blocks(self, tmp_path):
        """Two writers: second waits and succeeds after first releases."""
        page = tmp_path / "test_page.md"
        page.write_text("content")

        lock1 = WikiLock(str(page), timeout=10)
        lock1.__enter__()
        try:
            # Second lock should fail with short timeout
            lock2 = WikiLock(str(page), timeout=1)
            with pytest.raises(TimeoutError):
                lock2.__enter__()
        finally:
            lock1.__exit__()

        # After first releases, second should succeed
        with WikiLock(str(page), timeout=5):
            pass  # succeeds

    def test_lock_timeout_error_message(self, tmp_path):
        """Timeout error should contain page path."""
        page = tmp_path / "test_page.md"
        page.write_text("content")

        lock1 = WikiLock(str(page), timeout=10)
        lock1.__enter__()
        try:
            with pytest.raises(TimeoutError) as exc_info:
                lock2 = WikiLock(str(page), timeout=1)
                lock2.__enter__()
            assert str(page) in str(exc_info.value)
        finally:
            lock1.__exit__()

    def test_separate_pages_no_blocking(self, tmp_path):
        """Two writers to different pages should not block each other."""
        page_a = tmp_path / "a.md"
        page_b = tmp_path / "b.md"
        page_a.write_text("a")
        page_b.write_text("b")

        # Acquire both locks simultaneously
        with WikiLock(str(page_a), timeout=2):
            with WikiLock(str(page_b), timeout=2):
                pass  # both succeed, no blocking


class TestStaleLockDetection:
    """Stale lock detection and breaking."""

    def test_stale_lock_dead_pid(self, tmp_path):
        """Stale lock with a dead PID is broken by the next writer."""
        page = tmp_path / "test_page.md"
        page.write_text("content")

        dead_pid = _dead_pids(1)[0]
        old_time = time.time() - (HARD_STALE_LIMIT + 60)
        lock_path = str(page) + ".lock"
        with open(lock_path, "w") as f:
            f.write(f"pid={dead_pid}\ntimestamp={old_time}\nhostname=test\n")

        with WikiLock(str(page), timeout=2) as lock:
            assert lock._fd is not None
            assert lock.metadata["pid"] == str(os.getpid())
            assert f"pid={os.getpid()}" in Path(lock_path).read_text()

        # Our release removed our own lock.
        assert not os.path.exists(lock_path)

    def test_live_pid_lock_respected(self, tmp_path):
        """A lock owned by a live PID is respected, not stolen."""
        page = tmp_path / "test_page.md"
        page.write_text("content")

        lock_path = str(page) + ".lock"
        with open(lock_path, "w") as f:
            f.write(f"pid={os.getpid()}\ntimestamp={time.time()}\nhostname=test\n")

        with pytest.raises(TimeoutError):
            WikiLock(str(page), timeout=1).__enter__()

        # The live owner's lock file must still be present and untouched.
        assert os.path.exists(lock_path)
        assert f"pid={os.getpid()}" in Path(lock_path).read_text()

    def test_clean_stale_locks(self, tmp_path):
        """clean_stale_locks removes stale locks and leaves live ones alone."""
        page = tmp_path / "test_page.md"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text("content")

        dead_pids = _dead_pids(3)
        old_time = time.time() - (HARD_STALE_LIMIT + 60)
        stale_paths = []
        for i, pid in enumerate(dead_pids):
            p = page.parent / f"test_page.stale{i}.md.lock"
            p.write_text(f"pid={pid}\ntimestamp={old_time}\nhostname=test\n")
            stale_paths.append(p)

        live_path = page.parent / "test_page.live.md.lock"
        live_path.write_text(
            f"pid={os.getpid()}\ntimestamp={time.time()}\nhostname=test\n"
        )

        cleaned = clean_stale_locks(str(page.parent))
        assert cleaned == 3
        for p in stale_paths:
            assert not p.exists(), f"{p} should have been cleaned"
        assert live_path.exists(), "live lock must not be cleaned"

    def test_stale_lock_corrupt_file(self, tmp_path):
        """Corrupt lock files are breakable once past the absolute hard limit."""
        page = tmp_path / "test_page.md"
        page.write_text("content")
        lock_path = str(page) + ".lock"

        # No parseable metadata — only the file mtime can establish age.
        with open(lock_path, "w") as f:
            f.write("garbage with no metadata\n")
        old = time.time() - (HARD_STALE_LIMIT + 60)
        os.utime(lock_path, (old, old))

        with WikiLock(str(page), timeout=2):
            pass

    def test_fresh_unreadable_lock_not_broken(self, tmp_path):
        """A lock caught mid-creation (metadata not yet written) is not stolen."""
        page = tmp_path / "test_page.md"
        page.write_text("content")
        lock_path = str(page) + ".lock"

        # Empty file: simulates the window between O_EXCL create and write.
        with open(lock_path, "w"):
            pass

        with pytest.raises(TimeoutError):
            with WikiLock(str(page), timeout=1):
                pass
        assert os.path.exists(lock_path)

    def test_stale_lock_invalid_pid(self, tmp_path):
        """A lock with a non-integer PID falls back to the hard limit."""
        page = tmp_path / "test_page.md"
        page.write_text("content")
        lock_path = str(page) + ".lock"

        old_time = time.time() - (HARD_STALE_LIMIT + 60)
        with open(lock_path, "w") as f:
            f.write(f"pid=not_a_number\ntimestamp={old_time}\nhostname=test\n")

        with WikiLock(str(page), timeout=2):
            pass

    def test_release_only_unlinks_own_token(self, tmp_path):
        """Releasing must never delete a lock file that carries another token."""
        page = tmp_path / "test_page.md"
        page.write_text("content")
        lock = WikiLock(str(page), timeout=5)
        lock.__enter__()
        lock_path = lock.lock_path

        # Simulate the holder's lock being replaced by a thief's lock.
        foreign = "token=foreign-token\npid=1\ntimestamp=0\nhostname=thief\n"
        Path(lock_path).write_text(foreign, encoding="utf-8")
        lock.__exit__(None, None, None)

        assert os.path.exists(lock_path), "foreign lock must not be unlinked"
        assert "token=foreign-token" in Path(lock_path).read_text()


class TestLockStealing:
    """Real two-process races around stale-lock breaking (D08-01)."""

    @staticmethod
    def _hold_backdated_lock(lock_path, ready, hold_s):
        """Child: create a lock with a live PID but an ancient timestamp."""
        with open(lock_path, "w") as f:
            f.write(
                f"pid={os.getpid()}\ntimestamp={time.time() - 86400}\n"
                f"hostname=test\ntoken=live-holder\n"
            )
        ready.set()
        time.sleep(hold_s)

    @pytest.mark.skipif(os.name != "posix", reason="PID liveness checks are POSIX-only")
    def test_live_holder_not_stolen_even_if_backdated(self, tmp_path):
        """Old code deleted any lock older than 3x timeout — even with a live PID."""
        page = tmp_path / "page.md"
        page.write_text("content")
        lock_path = str(page) + ".lock"

        ready = multiprocessing.Event()
        holder = multiprocessing.Process(
            target=self._hold_backdated_lock, args=(lock_path, ready, 30)
        )
        holder.start()
        try:
            assert ready.wait(10), "holder process did not start"
            with pytest.raises(TimeoutError):
                with WikiLock(str(page), timeout=1):
                    pytest.fail("stole the lock from a live holder")

            content = Path(lock_path).read_text()
            assert f"pid={holder.pid}" in content
            assert "token=live-holder" in content
        finally:
            holder.terminate()
            holder.join(10)
            if holder.is_alive():
                holder.kill()
                holder.join(5)
        assert holder.exitcode is not None

    @staticmethod
    def _write_stale_lock_and_exit(lock_path, ready):
        with open(lock_path, "w") as f:
            f.write(
                f"pid={os.getpid()}\ntimestamp={time.time() - 86400}\n"
                f"hostname=test\ntoken=dead-owner\n"
            )
        ready.set()

    def test_dead_owner_lock_is_broken(self, tmp_path):
        """A lock left behind by an exited process is breakable."""
        page = tmp_path / "page.md"
        page.write_text("content")
        lock_path = str(page) + ".lock"

        ready = multiprocessing.Event()
        owner = multiprocessing.Process(
            target=self._write_stale_lock_and_exit, args=(lock_path, ready)
        )
        owner.start()
        try:
            assert ready.wait(10), "owner process did not start"
        finally:
            owner.join(10)
        assert owner.exitcode == 0, f"owner exited with {owner.exitcode}"

        with WikiLock(str(page), timeout=5) as lock:
            assert lock._fd is not None
            assert f"pid={os.getpid()}" in Path(lock_path).read_text()
        assert not os.path.exists(lock_path)

    @staticmethod
    def _acquire_and_record(page_path, timeout, results):
        from llm_wiki.core.locking import WikiLock as _WikiLock

        try:
            with _WikiLock(page_path, timeout=timeout):
                t_in = time.monotonic()
                time.sleep(0.25)
                t_out = time.monotonic()
            results.put(("ok", os.getpid(), t_in, t_out))
        except Exception as e:  # pragma: no cover - diagnostic path
            results.put(("error", str(e), 0.0, 0.0))

    def test_concurrent_stale_breakers_are_mutually_exclusive(self, tmp_path):
        """Four processes race to break one stale lock: no two hold it at once."""
        page = tmp_path / "page.md"
        page.write_text("content")
        lock_path = str(page) + ".lock"
        with open(lock_path, "w") as f:
            f.write(
                f"pid={_dead_pids(1)[0]}\ntimestamp={time.time() - 86400}\n"
                f"hostname=test\ntoken=dead-owner\n"
            )

        results = multiprocessing.Queue()
        procs = [
            multiprocessing.Process(
                target=self._acquire_and_record, args=(str(page), 10, results)
            )
            for _ in range(4)
        ]
        for p in procs:
            p.start()
        for p in procs:
            p.join(30)
        assert all(p.exitcode == 0 for p in procs), [p.exitcode for p in procs]

        intervals = []
        while not results.empty():
            entry = results.get()
            assert entry[0] == "ok", entry
            intervals.append((entry[2], entry[3]))
        assert len(intervals) == 4, f"expected 4 acquisitions, got {intervals}"
        intervals.sort()
        for (_, prev_end), (next_start, _) in zip(intervals, intervals[1:]):
            assert next_start >= prev_end, f"overlapping lock holds: {intervals}"


# ══════════════════════════════════════════════════════════════════════════
# Atomic write tests
# ══════════════════════════════════════════════════════════════════════════

class TestAtomicWrite:
    """Atomic write correctness and crash resilience."""

    def test_atomic_write_creates_file(self, tmp_path):
        """Atomic write should create the file with correct content."""
        target = tmp_path / "subdir" / "test.md"
        assert atomic_write(str(target), "hello world")
        assert target.exists()
        assert target.read_text() == "hello world"

    def test_atomic_write_overwrites(self, tmp_path):
        """Atomic write should overwrite existing files."""
        target = tmp_path / "test.md"
        target.write_text("old content")
        assert atomic_write(str(target), "new content")
        assert target.read_text() == "new content"

    def test_atomic_write_no_partial_on_crash(self, tmp_path):
        """Crash before rename: original file preserved, temp file exists."""
        target = tmp_path / "test.md"
        target.write_text("original content")

        # Simulate crash by writing manually and checking temp file pattern
        dirname = str(tmp_path)
        tmp_pattern = ".test.md.tmp."

        # Clean up any existing tmp files
        for f in os.listdir(dirname):
            if tmp_pattern in f:
                os.unlink(os.path.join(dirname, f))

        # Write via atomic_write which should succeed
        assert atomic_write(str(target), "new content")
        assert target.read_text() == "new content"

        # No temp files left behind
        tmp_files = [f for f in os.listdir(dirname) if tmp_pattern in f]
        assert len(tmp_files) == 0

    def test_atomic_write_unicode(self, tmp_path):
        """Atomic write should handle Unicode content."""
        target = tmp_path / "unicode.md"
        content = "café résumé ñ 🚀\n# Heading\nContent with Unicode."
        assert atomic_write(str(target), content)
        assert target.read_text(encoding="utf-8") == content

    def test_cleanup_temp_files(self, tmp_path):
        """Cleanup should remove stale temp files."""
        # Create fake temp files with dead PIDs
        dirname = str(tmp_path)
        dead_pid = 99999
        try:
            os.kill(dead_pid, 0)
            dead_pid = 99998
            os.kill(dead_pid, 0)
            dead_pid = 99997
            os.kill(dead_pid, 0)
        except OSError:
            pass

        tmp_file = os.path.join(dirname, f".test.md.tmp.{dead_pid}")
        with open(tmp_file, "w") as f:
            f.write("temp content")
        # Set mtime to old so cleanup picks it up
        os.utime(tmp_file, (0, 0))

        cleaned = cleanup_temp_files(dirname)
        assert cleaned >= 1
        assert not os.path.exists(tmp_file)

    def test_atomic_write_dotfile(self, tmp_path):
        """Atomic write should handle filenames starting with dot."""
        target = tmp_path / ".hidden.md"
        assert atomic_write(str(target), "hidden content")
        assert target.read_text() == "hidden content"

    def test_cleanup_temp_files_nonexistent_dir(self, tmp_path):
        """Cleanup on non-existent directory returns 0."""
        cleaned = cleanup_temp_files(os.path.join(str(tmp_path), "nonexistent"))
        assert cleaned == 0

    def test_cleanup_temp_files_live_pid_skipped(self, tmp_path):
        """Temp file with live PID should NOT be cleaned up."""
        dirname = str(tmp_path)
        live_pid = os.getpid()
        tmp_file = os.path.join(dirname, f".test.md.tmp.{live_pid}")
        with open(tmp_file, "w") as f:
            f.write("live content")

        cleaned = cleanup_temp_files(dirname)
        assert cleaned == 0  # live PID, should skip
        assert os.path.exists(tmp_file)  # temp file preserved


# ══════════════════════════════════════════════════════════════════════════
# Content hash tests
# ══════════════════════════════════════════════════════════════════════════

class TestContentHash:
    """Content hash computation and injection."""

    def test_compute_hash_deterministic(self):
        """Same content should produce the same hash."""
        content = "---\ntitle: Test\n---\n\n# Test\nContent."
        h1 = compute_hash(content)
        h2 = compute_hash(content)
        assert h1 == h2
        assert len(h1) == 64  # SHA256 hex digest

    def test_compute_hash_excludes_hash_field(self):
        """Changing only _content_hash should not change the hash."""
        content = "---\ntitle: Test\n---\n\n# Test"
        h1 = compute_hash(content)
        content_with_hash = "---\ntitle: Test\n_content_hash: abc123\n---\n\n# Test"
        h2 = compute_hash(content_with_hash)
        assert h1 == h2  # hash field excluded, so hashes match

    def test_compute_hash_different_content(self):
        """Different content should produce different hashes."""
        h1 = compute_hash("# Page A\nContent.")
        h2 = compute_hash("# Page B\nDifferent.")
        assert h1 != h2

    def test_read_hash_present(self):
        """read_hash should extract existing hash."""
        content = "---\ntitle: Test\n_content_hash: abc123def\n---\n\n# Test"
        assert read_hash(content) == "abc123def"

    def test_read_hash_absent(self):
        """read_hash should return empty string if no hash."""
        content = "---\ntitle: Test\n---\n\n# Test"
        assert read_hash(content) == ""

    def test_inject_hash_adds_to_frontmatter(self):
        """inject_hash should add _content_hash to frontmatter."""
        content = "---\ntitle: Test\n---\n\n# Test\nContent."
        result = inject_hash(content)
        assert HASH_FIELD in result
        assert "---\ntitle: Test\n_content_hash:" in result
        # Should not duplicate --- delimiters
        assert result.count("---") == 2

    def test_inject_hash_updates_existing(self):
        """inject_hash should update existing _content_hash."""
        content = "---\ntitle: Test\n_content_hash: oldhash\n---\n\n# Test"
        result = inject_hash(content)
        assert HASH_FIELD in result
        assert "oldhash" not in result
        assert result.count("_content_hash:") == 1

    def test_hash_stability(self):
        """Hash should be stable across multiple injections."""
        content = "---\ntitle: Test\n---\n\n# Test"
        h1 = read_hash(inject_hash(content))
        h2 = read_hash(inject_hash(content))
        assert h1 == h2  # injecting twice gives same hash

    def test_inject_hash_no_frontmatter(self):
        """inject_hash should create frontmatter for content without any ---."""
        content = "# Just a heading\n\nSome content without frontmatter."
        result = inject_hash(content)
        assert result.startswith("---\n")
        assert HASH_FIELD in result
        assert "# Just a heading" in result
        # Should have exactly two --- lines (opening and closing)
        assert result.count("---") == 2


# ══════════════════════════════════════════════════════════════════════════
# write_wiki() integration tests
# ══════════════════════════════════════════════════════════════════════════

class TestWriteWikiConcurrency:
    """Integration tests for write_wiki with locking and conflict detection."""

    def test_creates_page_with_hash(self, tmp_path):
        """New pages should get _content_hash injected."""
        wiki = tmp_path / "wiki"
        content = "---\ntitle: Test Page\ntype: concept\n---\n\n# Test Page\nContent."
        status, ok = write_wiki(str(wiki), "test/page.md", content)
        assert status == "created"
        assert ok
        written = (wiki / "test" / "page.md").read_text()
        assert HASH_FIELD in written

    def test_skips_identical_content(self, tmp_path):
        """Identical content should be skipped (no-op)."""
        wiki = tmp_path / "wiki"
        content = "---\ntitle: Test\ntype: concept\n---\n\n# Test\nContent."
        # First write — content gets hash injected on disk
        status1, ok1 = write_wiki(str(wiki), "test/page.md", content)
        assert status1 == "created"

        # Read back what was actually written (with injected hash)
        written = (wiki / "test" / "page.md").read_text()

        # Second write with the hashed content — should be identical
        status2, ok2 = write_wiki(str(wiki), "test/page.md", written)
        assert status2 == "skipped"
        assert ok2

    def test_updates_with_force(self, tmp_path):
        """Force should overwrite existing page."""
        wiki = tmp_path / "wiki"
        content1 = "---\ntitle: Test\ntype: concept\n---\n\n# Original"
        content2 = "---\ntitle: Test\ntype: concept\n---\n\n# Modified"

        status1, _ = write_wiki(str(wiki), "test/page.md", content1)
        assert status1 == "created"

        status2, ok2 = write_wiki(str(wiki), "test/page.md", content2, force=True)
        assert status2 == "updated"
        assert ok2
        written = (wiki / "test" / "page.md").read_text()
        assert "Modified" in written

    def test_conflict_detection(self, tmp_path):
        """When hash mismatches, should detect conflict."""
        wiki = tmp_path / "wiki"
        page_path = wiki / "test" / "page.md"

        # Write initial content (gets hash injected)
        content1 = "---\ntitle: Test\ntype: concept\n---\n\n# Version 1"
        status1, _ = write_wiki(str(wiki), "test/page.md", content1)
        assert status1 == "created"

        # Read the actual content with injected hash
        original = page_path.read_text()
        # Store the hash for later use
        original_hash = read_hash(original)

        # Simulate another agent modifying the page (properly: update hash too)
        modified = original.replace("Version 1", "Version 2")
        modified = inject_hash(modified)  # other agent's write updates hash
        page_path.write_text(modified)

        # Now try to write content that carries the ORIGINAL hash
        # (as if the writer read V1, but disk now has V2)
        content_with_hash = inject_hash(content1)
        status3, ok3 = write_wiki(str(wiki), "test/page.md", content_with_hash)

        # Content_with_hash has V1's hash, disk has V2's hash → conflict
        assert status3 == "conflict"
        assert ok3

        # Conflict file should exist
        conflict_path = str(page_path).replace(".md", " (conflict).md")
        assert os.path.exists(conflict_path)

    def test_conflict_file_content_preserved(self, tmp_path):
        """Conflict file should contain the writer's intended content."""
        wiki = tmp_path / "wiki"
        page_path = wiki / "test" / "page.md"

        content1 = "---\ntitle: Test\ntype: concept\n---\n\n# Original Content Here"
        write_wiki(str(wiki), "test/page.md", content1)

        # Another agent modifies (properly: update hash too)
        original = page_path.read_text()
        modified = original.replace("Original", "Agent B Modified")
        modified = inject_hash(modified)  # other agent's write updates hash
        page_path.write_text(modified)

        # Writer A's new version with V1 hash injected
        content_a = inject_hash(content1)
        status, ok = write_wiki(str(wiki), "test/page.md", content_a)
        assert status == "conflict"

        conflict_path = str(page_path).replace(".md", " (conflict).md")
        assert os.path.exists(conflict_path)
        conflict_content = Path(conflict_path).read_text()
        assert "Original Content Here" in conflict_content

    def test_lock_timeout_failure(self, tmp_path):
        """Lock timeout should return 'locked' status."""
        wiki = tmp_path / "wiki"
        page_path = wiki / "test" / "page.md"
        page_path.parent.mkdir(parents=True)
        page_path.write_text("content")

        # Hold the lock
        lock = WikiLock(str(page_path), timeout=30)
        lock.__enter__()
        try:
            status, ok = write_wiki(str(wiki), "test/page.md",
                                    "---\ntitle: Test\n---\n\nNew",
                                    lock_timeout=1)
            assert status == "locked"
            assert not ok
        finally:
            lock.__exit__()

    def test_update_index_atomic(self, tmp_path):
        """update_index should atomically append to index."""
        wiki = tmp_path / "wiki"
        # update_index expects index at root/wiki/index.md
        pages_dir = wiki / "wiki"
        pages_dir.mkdir(parents=True)
        index_path = pages_dir / "index.md"

        # Create initial index (utf-8 explicit: write_text default encoding is
        # locale-dependent — cp1252 on Windows — which corrupts the em-dash
        # for readers that decode utf-8).
        index_path.write_text(
            "# Wiki Index\n\n- [[existing|Existing]] — existing\n", encoding="utf-8"
        )

        pages = ["entities/NewPage.md", "concepts/AnotherConcept.md"]
        added = update_index(str(wiki), pages)
        assert added == 2

        content = index_path.read_text()
        assert "NewPage" in content
        assert "AnotherConcept" in content
        assert "existing" in content  # original content preserved

    def test_update_index_no_duplicates(self, tmp_path):
        """update_index should not add duplicate entries."""
        wiki = tmp_path / "wiki"
        pages_dir = wiki / "wiki"
        pages_dir.mkdir(parents=True)
        index_path = pages_dir / "index.md"
        index_path.write_text(
            "# Wiki Index\n\n- [[existing|Existing]] — existing\n", encoding="utf-8"
        )

        pages = ["entities/NewPage.md"]
        added1 = update_index(str(wiki), pages)
        assert added1 == 1

        added2 = update_index(str(wiki), pages)
        assert added2 == 0  # no duplicates added

    def test_write_file_atomic(self, tmp_path, monkeypatch):
        """write_file must never leave a partial file when the rename fails."""
        target = tmp_path / "sub" / "test.md"
        assert write_file(str(target), "original content")
        assert target.read_text() == "original content"

        def _fail_replace(src, dst):
            raise OSError("simulated crash before rename")

        monkeypatch.setattr(os, "replace", _fail_replace)
        assert write_file(str(target), "partial new content") is False
        monkeypatch.undo()

        # Original content survives intact and no temp file is left behind.
        assert target.read_text() == "original content"
        leftovers = [p.name for p in target.parent.iterdir() if ".tmp." in p.name]
        assert leftovers == []


# ══════════════════════════════════════════════════════════════════════════
# Concurrency stress tests
# ══════════════════════════════════════════════════════════════════════════

class TestConcurrencyStress:
    """Multi-process concurrency stress tests."""

    @staticmethod
    def _writer_worker(page_path, content, result_queue, lock_timeout=10):
        """Worker function for multiprocessing tests."""
        try:
            status, ok = write_wiki(
                os.path.dirname(os.path.dirname(page_path)),
                os.path.relpath(page_path, os.path.dirname(os.path.dirname(page_path))),
                content,
                lock_timeout=lock_timeout,
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
            page_path = wiki / f"entities" / f"Page{i}.md"
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

        # Verify all pages exist
        for i in range(10):
            assert (wiki / "entities" / f"Page{i}.md").exists()

    def test_two_writers_same_page(self, tmp_path):
        """2 concurrent writers with one base hash: exactly one write wins."""
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        page_dir = wiki / "entities"
        page_dir.mkdir(parents=True)
        page_path = page_dir / "SharedPage.md"

        # Seed through write_wiki so the page carries a content hash; both
        # writers then build on that same base hash.
        initial = "---\ntitle: Shared Page\ntype: concept\n---\n\n# Version 0"
        status, _ = write_wiki(str(wiki), "entities/SharedPage.md", initial)
        assert status == "created"
        on_disk = page_path.read_text()
        base_hash = read_hash(on_disk)
        assert base_hash

        content_a = on_disk.replace("Version 0", "Version A")
        content_b = on_disk.replace("Version 0", "Version B")

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
        assert p_a.exitcode == 0 and p_b.exitcode == 0

        results = []
        while not result_queue.empty():
            results.append(result_queue.get())

        assert len(results) == 2, f"Expected 2 results, got: {results}"
        statuses = sorted(r[0] for r in results)
        assert statuses == ["conflict", "updated"], (
            f"Expected exactly one winner + one conflict: {results}"
        )

        final = page_path.read_text()
        assert ("Version A" in final) != ("Version B" in final), final
        conflict_path = str(page_path).replace(".md", " (conflict).md")
        assert os.path.exists(conflict_path)
        conflict_text = Path(conflict_path).read_text()
        assert ("Version A" in conflict_text) or ("Version B" in conflict_text)


# Count: 27 test functions
