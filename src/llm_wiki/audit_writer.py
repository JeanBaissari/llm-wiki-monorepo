"""
audit_writer.py — Schema-complete atomic audit writer for LLM Wiki.

Provides one shared audit writer used by ingest, web viewer, and Obsidian paths.
Uses temp/fsync/rename atomic write protocol with file-level locking.
"""

import json
import os
import re
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from .schema_validator import validate_audit


FRONTMATTER_RE = re.compile(r"^---\n(?:.*?\n)---\n", re.DOTALL)


def _generate_audit_id() -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = uuid.uuid4().hex[:4]
    return f"{ts}-{suffix}"


def _atomic_write(path: str, content: str) -> bool:
    """Write content atomically using temp/fsync/rename protocol."""
    dirname = os.path.dirname(path) or "."
    os.makedirs(dirname, exist_ok=True)
    basename = os.path.basename(path)
    tmp_path = os.path.join(dirname, f".{basename}.tmp.{os.getpid()}")

    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.rename(tmp_path, path)
        return True
    except (IOError, OSError) as e:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        print(f"  ⚠  Atomic write failed for {path}: {e}", file=sys.stderr)
        return False


def _acquire_lock(lock_path: str, timeout: float = 5.0):
    """Try to acquire a file-level advisory lock.

    Returns a lock file descriptor (truthy) on success, or None on failure.
    The caller must keep the fd alive and pass it to _release_lock.
    """
    try:
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        import portalocker
        lf = open(lock_path, "w")
        portalocker.lock(lf, portalocker.LOCK_EX | portalocker.LOCK_NB)
        lf.write(f"{os.getpid()}\n")
        lf.flush()
        return lf
    except ImportError:
        return True  # No locking available, proceed
    except (OSError, portalocker.LockException):
        return None


def _release_lock(lock_handle, lock_path: str) -> None:
    """Release a previously acquired lock."""
    if hasattr(lock_handle, "close"):
        try:
            import portalocker
            portalocker.unlock(lock_handle)
        except Exception:
            pass
        try:
            lock_handle.close()
        except Exception:
            pass
    try:
        if os.path.exists(lock_path):
            os.unlink(lock_path)
    except OSError:
        pass


def _compute_anchor(target_path: str, line_range: tuple[int, int]) -> dict:
    """Compute anchor fields from a target file's line range.

    Returns dict with anchor_before, anchor_text, anchor_after.
    """
    try:
        lines = Path(target_path).read_text(encoding="utf-8").split("\n")
    except (FileNotFoundError, IOError):
        return {
            "anchor_before": "",
            "anchor_text": str(line_range),
            "anchor_after": "",
        }

    start, end = line_range
    # line_range is 1-indexed
    start_idx = max(0, start - 1)
    end_idx = min(len(lines), end)

    before_lines = lines[max(0, start_idx - 3):start_idx]
    target_lines = lines[start_idx:end_idx]
    after_lines = lines[end_idx:min(len(lines), end_idx + 3)]

    return {
        "anchor_before": "\n".join(before_lines),
        "anchor_text": "\n".join(target_lines),
        "anchor_after": "\n".join(after_lines),
    }


def _format_audit_frontmatter(data: dict) -> str:
    """Serialize audit data as YAML frontmatter."""
    lines = ["---"]
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, list):
            items = ", ".join(f'"{v}"' for v in value)
            lines.append(f"{key}: [{items}]")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, int):
            lines.append(f"{key}: {value}")
        elif isinstance(value, dict):
            lines.append(f"{key}: {json.dumps(value)}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


class AuditWriter:
    """Atomic audit writer with schema validation and lock coordination.

    Usage:
        writer = AuditWriter(audit_dir="/path/to/wiki/audit")
        result = writer.write_anchored(
            target="wiki/concepts/test.md",
            target_lines=(10, 12),
            severity="suggest",
            author="test-agent",
            source="manual",
            body="Suggestion text here",
        )
    """

    def __init__(self, audit_dir: str | Path, wiki_root: str | Path | None = None):
        self.audit_dir = str(Path(audit_dir).resolve())
        self.wiki_root = str(Path(wiki_root).resolve()) if wiki_root else None
        self.resolved_dir = os.path.join(self.audit_dir, "resolved")

    def write_anchored(
        self,
        target: str,
        target_lines: tuple[int, int],
        severity: str,
        author: str,
        source: str,
        body: str = "",
        extra_fields: dict | None = None,
    ) -> Optional[str]:
        """Write an anchored audit entry. Returns the audit file path, or None on failure.

        Fields are auto-computed from the target file when possible.
        """
        target_path = os.path.join(self.wiki_root or "", target) if self.wiki_root else target

        anchors = _compute_anchor(target_path, target_lines)

        data = {
            "id": _generate_audit_id(),
            "target": target,
            "target_lines": [target_lines[0], target_lines[1]],
            "anchor_before": anchors["anchor_before"],
            "anchor_text": anchors["anchor_text"],
            "anchor_after": anchors["anchor_after"],
            "severity": severity,
            "author": author,
            "source": source,
            "created": datetime.now().strftime("%Y-%m-%d"),
            "status": "open",
        }

        if extra_fields:
            data.update(extra_fields)

        # Validate before writing
        val_errors = validate_audit(data)
        if val_errors:
            print(f"  ⚠  Audit validation errors: {val_errors}", file=sys.stderr)
            return None

        frontmatter = _format_audit_frontmatter(data)
        full_content = f"{frontmatter}\n\n{body}\n" if body else f"{frontmatter}\n"

        audit_id = data["id"]
        audit_filename = f"{audit_id}.md"
        audit_path = os.path.join(self.audit_dir, audit_filename)

        # File-level lock for append coordination
        lock_path = audit_path + ".lock"
        lock_handle = _acquire_lock(lock_path)
        if lock_handle is None:
            print(f"  ⚠  Could not acquire lock for {audit_path}", file=sys.stderr)
            return None

        try:
            success = _atomic_write(audit_path, full_content)
            if not success:
                return None
            return audit_path
        finally:
            _release_lock(lock_handle, lock_path)

    def write_unanchored(
        self,
        target: str,
        target_kind: str,
        target_reason: str,
        severity: str,
        author: str,
        source: str,
        body: str = "",
        extra_fields: dict | None = None,
    ) -> Optional[str]:
        """Write an unanchored audit entry that applies to a whole file/operation/wiki."""
        data = {
            "id": _generate_audit_id(),
            "target": target,
            "target_kind": target_kind,
            "target_reason": target_reason,
            "severity": severity,
            "author": author,
            "source": source,
            "created": datetime.now().strftime("%Y-%m-%d"),
            "status": "open",
        }

        if extra_fields:
            data.update(extra_fields)

        val_errors = validate_audit(data)
        if val_errors:
            print(f"  ⚠  Audit validation errors: {val_errors}", file=sys.stderr)
            return None

        frontmatter = _format_audit_frontmatter(data)
        full_content = f"{frontmatter}\n\n{body}\n" if body else f"{frontmatter}\n"

        audit_id = data["id"]
        audit_filename = f"{audit_id}.md"
        audit_path = os.path.join(self.audit_dir, audit_filename)

        lock_path = audit_path + ".lock"
        lock_handle = _acquire_lock(lock_path)
        if lock_handle is None:
            print(f"  ⚠  Could not acquire lock for {audit_path}", file=sys.stderr)
            return None

        try:
            success = _atomic_write(audit_path, full_content)
            if not success:
                return None
            return audit_path
        finally:
            _release_lock(lock_handle, lock_path)

    def resolve_audit(self, audit_id: str, resolution_note: str = "") -> bool:
        """Move an open audit to resolved status."""
        open_path = os.path.join(self.audit_dir, f"{audit_id}.md")
        resolved_path = os.path.join(self.resolved_dir, f"{audit_id}.md")

        if not os.path.exists(open_path):
            print(f"  ⚠  Audit not found: {open_path}", file=sys.stderr)
            return False

        try:
            content = Path(open_path).read_text(encoding="utf-8")
            # Update status in frontmatter
            updated = re.sub(r"^status: open$", "status: resolved", content, flags=re.MULTILINE)
            if resolution_note:
                updated += f"\n## Resolution\n\n{resolution_note}\n"

            os.makedirs(os.path.dirname(resolved_path), exist_ok=True)
            success = _atomic_write(resolved_path, updated)
            if success:
                os.unlink(open_path)
            return success
        except (IOError, OSError) as e:
            print(f"  ⚠  Failed to resolve audit {audit_id}: {e}", file=sys.stderr)
            return False
