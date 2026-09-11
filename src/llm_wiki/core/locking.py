"""
Wiki page locking utilities.

Per-page advisory locking via atomic lock-file creation
(``os.open(path, O_CREAT | O_EXCL | O_WRONLY)``). The winner writes an owner
token, PID, wall-clock timestamp, monotonic timestamp and hostname to the
lock file and fsyncs it before returning.

Staleness rules (conservative by design):
  * A lock whose owner PID is demonstrably alive is never broken.
  * A lock whose owner PID is demonstrably dead is broken once it is older
    than ``timeout * STALE_TIMEOUT_FACTOR``.
  * A lock whose PID is unreadable, or whose liveness cannot be checked, is
    broken only after the absolute ``HARD_STALE_LIMIT``, so a lock caught
    mid-creation (file exists, metadata not yet written) is never stolen.

Breaking is a claim operation: the lock file is atomically renamed to a
unique temp path first (``os.replace``), then re-checked, then unlinked.
Only one breaker can win a rename; if the captured file turns out to have
become live between the staleness check and the rename it is restored
instead of destroyed. Release uses the same rename-then-check pattern and
only removes a lock file that still carries our token, so an original
holder can never delete a thief's lock.

Callers rely on: ``WikiLock(page_path, timeout)``, ``metadata`` with
``pid``/``timestamp``/``hostname``, ``lock_path``, ``_fd`` while held,
``DEFAULT_LOCK_TIMEOUT`` and ``clean_stale_locks()``.
"""
import os
import socket
import time
import uuid

DEFAULT_LOCK_TIMEOUT = 30  # seconds
STALE_TIMEOUT_FACTOR = 3   # a dead-PID lock is stale after timeout * this
HARD_STALE_LIMIT = 300     # absolute fallback when PID liveness is unknown


def _hostname():
    """Return short hostname, cross-platform."""
    return socket.gethostname().split(".")[0]


def _read_metadata(path: str):
    """Read ``key=value`` lock metadata without truncating.

    Always opens the lock file read-only ("r") — never with mode "w".
    Returns ``None`` when the file cannot be read (e.g. it just vanished),
    otherwise a dict (possibly empty for unreadable/corrupt content).
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            data = f.read()
    except OSError:
        return None
    metadata: dict = {}
    for line in data.splitlines():
        if "=" in line:
            key, value = line.strip().split("=", 1)
            metadata[key] = value
    return metadata


def _safe_unlink(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def _pid_alive(pid: int):
    """Return True/False when liveness is knowable, else None.

    POSIX: signal 0 probes existence. Windows has no equivalent cheap probe,
    so liveness is reported as unknown and callers fall back to the hard
    stale limit.
    """
    if os.name != "posix":
        return None
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists but owned by another user
    except (OSError, ValueError):
        return False


def _lock_age(path: str, metadata) -> float:
    """Age of a lock in seconds (wall clock), falling back to file mtime."""
    if metadata is not None:
        raw = metadata.get("timestamp")
        if raw is not None:
            try:
                return max(0.0, time.time() - float(raw))
            except (TypeError, ValueError):
                pass
    try:
        return max(0.0, time.time() - os.path.getmtime(path))
    except OSError:
        return 0.0


def _is_stale(path: str, metadata, timeout: int) -> bool:
    """Decide whether a lock file may be broken.

    Requires both a non-alive owner PID and an age past the threshold; locks
    with unreadable metadata or unknowable liveness use the absolute hard
    limit so a lock that is still being written is never treated as stale.
    """
    age = _lock_age(path, metadata)
    pid = None
    if metadata:
        raw = metadata.get("pid")
        if raw is not None:
            try:
                pid = int(raw)
            except (TypeError, ValueError):
                pid = None
    if pid is not None:
        alive = _pid_alive(pid)
        if alive is True:
            return False
        if alive is False:
            return age > timeout * STALE_TIMEOUT_FACTOR
    return age > HARD_STALE_LIMIT


def _restore_captured(captured: str, lock_path: str) -> None:
    """Put a captured lock file back without overwriting a newer lock.

    Uses ``os.link`` so the restore fails atomically if another process has
    already recreated the lock at ``lock_path``; that newer lock is left
    untouched.
    """
    try:
        os.link(captured, lock_path)
    except FileExistsError:
        _safe_unlink(captured)
        return
    except OSError:
        # Hard links unsupported — fall back to replace, only when free.
        if os.path.exists(lock_path):
            _safe_unlink(captured)
            return
        try:
            os.replace(captured, lock_path)
            return
        except OSError:
            _safe_unlink(captured)
            return
    _safe_unlink(captured)


def _break_stale_lock(lock_path: str, timeout: int) -> bool:
    """Atomically claim and remove a stale lock file.

    The rename is the arbiter: exactly one concurrent breaker can move the
    file. After winning, the captured file is re-checked; a lock that became
    live between the staleness check and the rename is restored rather than
    destroyed.
    """
    captured = f"{lock_path}.stale.{os.getpid()}.{uuid.uuid4().hex}"
    try:
        os.replace(lock_path, captured)
    except OSError:
        return False  # lost the race, or the file is already gone
    metadata = _read_metadata(captured)
    if metadata is None:
        # Unreadable right after a successful rename — leave it captured
        # rather than destroying content we cannot inspect.
        return False
    if not _is_stale(captured, metadata, timeout):
        _restore_captured(captured, lock_path)
        return False
    _safe_unlink(captured)
    return True


class WikiLock:
    """Context manager for per-page advisory locking."""

    def __init__(self, page_path: str, timeout: int = DEFAULT_LOCK_TIMEOUT):
        self.page_path = page_path
        self.lock_path = page_path + ".lock"
        self.timeout = timeout
        self._fd = None
        self.token: str | None = None
        self.metadata: dict = {}

    def __enter__(self):
        self._acquire()
        return self

    def __exit__(self, *args):
        self._release()
        return False

    def _check_stale_and_break(self) -> bool:
        """Check for a stale lock and break it. Returns True if broken."""
        metadata = _read_metadata(self.lock_path)
        if metadata is None:
            return False
        if not _is_stale(self.lock_path, metadata, self.timeout):
            return False
        return _break_stale_lock(self.lock_path, self.timeout)

    def _acquire(self):
        """Acquire the lock atomically, breaking genuinely stale locks."""
        lock_dir = os.path.dirname(self.lock_path)
        if lock_dir:
            os.makedirs(lock_dir, exist_ok=True)

        deadline = time.monotonic() + self.timeout
        while True:
            try:
                self._fd = os.open(
                    self.lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o644,
                )
            except FileExistsError:
                if self._check_stale_and_break():
                    continue  # we won the break — try to create immediately
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"Could not acquire lock for {self.page_path} within {self.timeout}s. "
                        f"Another agent holds the lock. If this persists, check for stale lock files "
                        f"or increase --lock-timeout."
                    )
                time.sleep(0.05)  # backoff before retry
                continue

            # We created the file with O_EXCL — nobody else can own it now.
            token = uuid.uuid4().hex
            self.token = token
            self.metadata = {
                "token": token,
                "pid": str(os.getpid()),
                "timestamp": str(time.time()),
                "monotonic": str(time.monotonic()),
                "hostname": _hostname(),
            }
            payload = "".join(f"{k}={v}\n" for k, v in self.metadata.items())
            try:
                os.write(self._fd, payload.encode("utf-8"))
                os.fsync(self._fd)
            except OSError:
                self._close_fd()
                _safe_unlink(self.lock_path)
                raise
            return

    def _close_fd(self):
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None

    def _release(self):
        """Release the lock, removing it only if it still carries our token."""
        self._close_fd()
        token = self.token
        if not token:
            return

        captured = f"{self.lock_path}.release.{os.getpid()}.{uuid.uuid4().hex}"
        try:
            os.replace(self.lock_path, captured)
        except OSError:
            return  # already released/broken by someone else
        metadata = _read_metadata(captured)
        if metadata is not None and metadata.get("token") == token:
            _safe_unlink(captured)
            return
        # The file at lock_path was not ours (stolen/replaced) — never
        # unlink it; put it back for its rightful owner.
        _restore_captured(captured, self.lock_path)


def clean_stale_locks(pages_dir: str, lock_timeout: int = DEFAULT_LOCK_TIMEOUT) -> int:
    """Remove stale lock files from the wiki pages directory.

    Uses the same staleness rules and rename-based breaking as ``WikiLock``,
    so cleanup can never race a live holder into losing its lock.

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
            metadata = _read_metadata(lock_path)
            if metadata is None:
                continue
            if _is_stale(lock_path, metadata, lock_timeout):
                if _break_stale_lock(lock_path, lock_timeout):
                    cleaned += 1
    return cleaned
