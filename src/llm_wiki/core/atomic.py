"""
Atomic write utilities for wiki files.

Writes to a temp file, fsyncs, then replaces atomically.
POSIX guarantees rename() is atomic on the same filesystem; os.replace()
extends the same atomic-replace semantics to Windows (MoveFileEx with
REPLACE_EXISTING), where os.rename() to an existing target can raise
PermissionError under file-indexer/AV contention.
"""
import os
import sys
import time


def atomic_write(path: str, content: str, encoding: str = "utf-8") -> bool:
    """
    Write content to path atomically.

    1. Write to <dir>/.<basename>.tmp.<PID> in the same directory
    2. fsync the temp file
    3. os.replace() to target path (atomic on same filesystem)

    Returns True on success, False on failure.
    If the process crashes before replace, the .tmp file is left for cleanup.
    """
    dirname = os.path.dirname(path) or "."
    os.makedirs(dirname, exist_ok=True)

    basename = os.path.basename(path)
    # Strip leading dot to avoid double-dot temp files
    if basename.startswith("."):
        clean_basename = basename.lstrip(".")
        tmp_path = os.path.join(dirname, f".{clean_basename}.tmp.{os.getpid()}")
    else:
        tmp_path = os.path.join(dirname, f".{basename}.tmp.{os.getpid()}")

    try:
        with open(tmp_path, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
        return True
    except (IOError, OSError) as e:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        print(f"  \N{WARNING SIGN}  Atomic write failed for {path}: {e}", file=sys.stderr)
        return False


def cleanup_temp_files(dirpath: str) -> int:
    """Remove stale .tmp.<PID> files from a directory.

    A temp file is stale if its PID suffix corresponds to a non-existent process.

    Returns count of files cleaned up.
    """
    import re

    cleaned = 0
    tmp_re = re.compile(r"^\.(.+)\.tmp\.(\d+)$")
    if not os.path.isdir(dirpath):
        return 0
    for entry in os.listdir(dirpath):
        m = tmp_re.match(entry)
        if not m:
            continue
        pid_str = m.group(2)
        try:
            pid = int(pid_str)
        except ValueError:
            continue
        # Check if PID is alive
        if os.name == "posix":
            try:
                os.kill(pid, 0)
                # PID is alive — temp file may still be in use, skip
                continue
            except (OSError, ValueError):
                pass  # PID dead, safe to clean
        else:
            # Non-POSIX: clean if older than 1 hour (pid check not available)
            tmp_path = os.path.join(dirpath, entry)
            try:
                if os.path.getmtime(tmp_path) < time.time() - 3600:
                    pass  # stale
                else:
                    continue  # might be recent
            except OSError:
                continue
        tmp_path = os.path.join(dirpath, entry)
        try:
            os.unlink(tmp_path)
            cleaned += 1
        except OSError:
            pass
    return cleaned
