"""
operation.py — OperationContext, event emission, and context manager for LLM Wiki.

Provides:
  - OperationContext: tracks run_id, command, inputs, hashes, timestamps, status, paths, errors
  - emit_event(): writes JSONL event records
  - with OperationContext(...) as ctx: context manager pattern
"""

import hashlib
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .schema_validator import validate_log_event


def _generate_id() -> str:
    """Generate a stable operation ID (ULID-style)."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    return f"op_{ts}-{suffix}"


def _generate_run_id() -> str:
    """Generate a run ID grouping retries."""
    return f"run_{uuid.uuid4().hex[:12]}"


def _sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_of_file(path: str) -> Optional[str]:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except (OSError, IOError):
        return None


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OperationContext:
    """Tracks state for one mutating operation.

    Usage:
        with OperationContext("ingest", wiki_root="/tmp/wiki") as ctx:
            ctx.add_touched("created", "wiki/concepts/test.md")
            # ... do work ...
            ctx.succeed()
    """

    def __init__(
        self,
        command: str,
        wiki_root: str | Path | None = None,
        component: str = "cli",
        inputs: dict | None = None,
        parent_operation_id: str | None = None,
    ):
        self.operation_id = _generate_id()
        self.run_id = _generate_run_id()
        self.parent_operation_id = parent_operation_id
        self.component = component
        self.command = command
        self.wiki_root = str(Path(wiki_root).resolve()) if wiki_root else None
        self.inputs = self._redact_secrets(inputs or {})
        self.input_hashes: dict[str, str] = {}
        self.status = "started"
        self.started_at = _iso_now()
        self.ended_at: str | None = None
        self.duration_ms: float | None = None
        self.touched_paths: dict[str, list[str]] = {
            "created": [],
            "updated": [],
            "deleted": [],
            "read": [],
        }
        self.artifact_refs: dict[str, list[str]] = {
            "audit_ids": [],
            "claim_refs": [],
            "cache_paths": [],
            "backup_paths": [],
            "graph_outputs": [],
            "index_outputs": [],
        }
        self.errors: list[dict] = []
        self._start_time = time.monotonic()

    def _redact_secrets(self, inputs: dict) -> dict:
        """Redact known secret fields from inputs for safe logging."""
        redacted = dict(inputs)
        for key in redacted:
            kl = key.lower()
            if any(secret in kl for secret in ("password", "secret", "token", "key", "api")):
                redacted[key] = "**REDACTED**"
        return redacted

    def add_touched(self, category: str, path: str) -> None:
        if category in self.touched_paths:
            self.touched_paths[category].append(str(Path(path).resolve()))

    def add_error(self, code: str, message: str, path: str | None = None, recoverable: bool = False) -> None:
        self.errors.append({
            "code": code,
            "message": message,
            "path": path,
            "recoverable": recoverable,
        })

    def add_input_hash(self, path: str) -> None:
        h = _sha256_of_file(path)
        if h:
            self.input_hashes[str(Path(path).resolve())] = h

    def add_artifact_ref(self, category: str, ref: str) -> None:
        if category in self.artifact_refs:
            self.artifact_refs[category].append(ref)

    def set_status(self, status: str) -> None:
        self.status = status

    def succeed(self) -> None:
        self._finish("succeeded")

    def fail(self) -> None:
        self._finish("failed")

    def _finish(self, status: str) -> None:
        self.status = status
        self.ended_at = _iso_now()
        self.duration_ms = (time.monotonic() - self._start_time) * 1000
        emit_event(self, status)
        self.write_manifest()

    def write_manifest(self) -> None:
        """Write a full operation manifest to log/operations/manifest-{run_id}.json."""
        if not self.wiki_root:
            return
        manifest_dir = Path(self.wiki_root) / "log" / "operations"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = manifest_dir / f"manifest-{self.run_id}.json"
        try:
            manifest_path.write_text(self.to_json(), encoding="utf-8")
        except IOError as e:
            print(f"  ⚠  Failed to write manifest: {e}", file=sys.stderr)

    def to_dict(self) -> dict:
        return {
            "operation_id": self.operation_id,
            "run_id": self.run_id,
            "parent_operation_id": self.parent_operation_id,
            "component": self.component,
            "command": self.command,
            "wiki_root": self.wiki_root,
            "inputs": self.inputs,
            "input_hashes": self.input_hashes,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_ms": self.duration_ms,
            "touched_paths": self.touched_paths,
            "artifact_refs": self.artifact_refs,
            "errors": self.errors,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)

    def __enter__(self):
        emit_event(self, "started")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.add_error(
                exc_type.__name__,
                str(exc_val) if exc_val else "Unknown error",
                recoverable=False,
            )
            self._finish("failed")
        else:
            if self.status == "started" or self.status == "running":
                self._finish("succeeded")
        return False  # Don't suppress exceptions


def _get_log_dir(wiki_root: str | None) -> str:
    """Determine the log/operations/ directory."""
    if wiki_root:
        log_dir = Path(wiki_root) / "log" / "operations"
        log_dir.mkdir(parents=True, exist_ok=True)
        return str(log_dir)
    return os.path.join(os.getcwd(), "log", "operations")


def emit_event(ctx: OperationContext, event_type: str) -> None:
    """Emit a structured JSONL event for an operation lifecycle transition."""
    event = {
        "v": 1,
        "ts": _iso_now(),
        "lvl": "INFO",
        "cmp": ctx.component,
        "msg": f"Operation {ctx.command} {event_type}",
        "operation_id": ctx.operation_id,
        "run_id": ctx.run_id,
        "event_type": event_type,
        "status": ctx.status,
        "command": ctx.command,
        "wiki_root": ctx.wiki_root,
        "touched_paths": ctx.touched_paths if event_type in ("succeeded", "failed") else None,
        "duration_ms": ctx.duration_ms,
        "errors": ctx.errors if event_type == "failed" else None,
    }

    # Validate event before writing
    validation_errors = validate_log_event(event)
    if validation_errors:
        print(f"  ⚠  Event validation warning: {validation_errors}", file=sys.stderr)

    # Write to daily JSONL file
    os.makedirs(_get_log_dir(ctx.wiki_root), exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    log_path = os.path.join(_get_log_dir(ctx.wiki_root), f"{date_str}.jsonl")

    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, default=str) + "\n")
            f.flush()
            os.fsync(f.fileno())
    except IOError as e:
        print(f"  ⚠  Failed to write event: {e}", file=sys.stderr)
