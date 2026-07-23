"""
Wiki page locking utilities.

Provides a context manager for per-page advisory locking via portalocker.
Lock files: <page_path>.lock — contain PID, timestamp, hostname.
Staleness detection: timeout-based (lock_timeout x 3) is primary and cross-platform.
On Unix, fast-path PID check via os.kill(pid, 0) avoids unnecessary timeout delays.
"""
import os
import time
import socket

import portalocker

DEFAULT_LOCK_TIMEOUT = 30  # seconds


def _hostname():
    """Return short hostname, cross-platform."""
    return socket.gethostname().split(".")[0]


class WikiLock:
    """Context manager for per-page advisory locking."""

    def __init__(self, page_path: str, timeout: int = DEFAULT_LOCK_TIMEOUT):
        self.page_path = page_path
        self.lock_path = page_path + ".lock"
        self.timeout = timeout
        self._fd = None

    def __enter__(self):
        self._check_stale_and_break()
        self._acquire()
        return self

    def __exit__(self, *args):
        self._release()
        return False

    def _check_stale_and_break(self):
        """Check for stale locks and break them. Cross-platform by design."""
        if not os.path.exists(self.lock_path):
            return
        try:
            with open(self.lock_path, "r") as f:
                metadata = {}
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        metadata[k] = v
            lock_age = time.time() - float(metadata.get("timestamp", 0))
            # Primary: timeout-based (works everywhere)
            if lock_age > self.timeout * 3:
                os.unlink(self.lock_path)
                return
            # Fast-path: PID check (Unix only)
            if os.name == "posix" and "pid" in metadata:
                try:
                    os.kill(int(metadata["pid"]), 0)
                    # PID is alive — lock is valid, do not break
                except (OSError, ValueError):
                    os.unlink(self.lock_path)
        except (OSError, ValueError):
            try:
                os.unlink(self.lock_path)
            except OSError:
                pass

    def _acquire(self):
        """Acquire exclusive lock with timeout."""
        lock_dir = os.path.dirname(self.lock_path)
        if lock_dir:
            os.makedirs(lock_dir, exist_ok=True)

        deadline = time.monotonic() + self.timeout
        while True:
            try:
                self._fd = open(self.lock_path, "w")
                portalocker.lock(self._fd, portalocker.LOCK_EX | portalocker.LOCK_NB)
                # Write lock metadata
                self._fd.write(
                    f"pid={os.getpid()}\n"
                    f"timestamp={time.time()}\n"
                    f"hostname={_hostname()}\n"
                )
                self._fd.flush()
                return
            except portalocker.exceptions.LockException:
                if self._fd:
                    self._fd.close()
                    self._fd = None
                if time.monotonic() > deadline:
                    raise TimeoutError(
                        f"Could not acquire lock for {self.page_path} within {self.timeout}s. "
                        f"Another agent holds the lock. If this persists, check for stale lock files "
                        f"or increase --lock-timeout."
                    )
                time.sleep(0.1)  # backoff before retry

    def _release(self):
        """Release lock and clean up lock file."""
        if self._fd:
            try:
                portalocker.unlock(self._fd)
            except Exception:
                pass
            try:
                self._fd.close()
            except Exception:
                pass
            self._fd = None
        try:
            os.unlink(self.lock_path)
        except OSError:
            pass


def clean_stale_locks(pages_dir: str, lock_timeout: int = DEFAULT_LOCK_TIMEOUT) -> int:
    """Remove stale lock files from the wiki pages directory.

    Returns count of stale locks cleaned up.
    """
    cleaned = 0
    if not os.path.isdir(pages_dir):
        return 0
    for root, dirs, files in os.walk(pages_dir):
        for f in files:
            if not f.endswith(".md.lock"):
                continue
            lock_path = os.path.join(root, f)
            try:
                with open(lock_path, "r") as lf:
                    metadata = {}
                    for line in lf:
                        if "=" in line:
                            k, v = line.strip().split("=", 1)
                            metadata[k] = v
                lock_age = time.time() - float(metadata.get("timestamp", 0))
                if lock_age > lock_timeout * 3:
                    os.unlink(lock_path)
                    cleaned += 1
                    continue
                if os.name == "posix" and "pid" in metadata:
                    try:
                        os.kill(int(metadata["pid"]), 0)
                        # PID alive, lock valid
                    except (OSError, ValueError):
                        os.unlink(lock_path)
                        cleaned += 1
            except (OSError, ValueError):
                try:
                    os.unlink(lock_path)
                    cleaned += 1
                except OSError:
                    pass
    return cleaned
