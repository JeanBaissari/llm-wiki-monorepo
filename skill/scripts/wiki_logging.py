#!/usr/bin/env python3
"""wiki_logging.py — Structured JSON logging for the llm-wiki-monorepo.

Every log event is a single JSON line to stderr with fields:
    {"v":1,"ts":"2026-07-03T14:22:31.123Z","lvl":"ERROR","cmp":"ingest","msg":"LLM call failed",...}

Usage:
    from wiki_logging import info, warn, error, set_level, configure

    configure(quiet=True)          # suppress INFO/WARN/DEBUG
    configure(verbose=True)        # enable DEBUG
    info("ingest", "Ingest started", pages=5)
    error("llm", "API call failed", provider="openai", retry=2)

CLI integration:
    import argparse
    from wiki_logging import configure
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    configure(quiet=args.quiet, verbose=args.verbose)
"""

import json
import os
import sys
from datetime import datetime, timezone

LOG_VERSION = 1

LEVELS: dict[str, int] = {
    "DEBUG": 10,
    "INFO": 20,
    "WARN": 30,
    "ERROR": 40,
    "PANIC": 50,
}

# Controlled by configure() / set_level()
_current_level: int = LEVELS["INFO"] if os.isatty(sys.stderr.fileno()) else LEVELS["WARN"]


def set_level(level: str) -> None:
    """Set minimum log level. Called by argparse --verbose/--quiet."""
    global _current_level
    if level in LEVELS:
        _current_level = LEVELS[level]


def configure(
    quiet: bool = False,
    verbose: bool = False,
    force_json: bool = False,
) -> None:
    """One-shot configuration for CLI scripts.

    Args:
        quiet: Suppress INFO/WARN/DEBUG (set level to ERROR).
        verbose: Enable DEBUG (set level to DEBUG).
        force_json: Force JSON output even when stderr is a TTY (no-op:
                    JSON is always the output format).

    If both quiet and verbose are set, verbose wins (DEBUG level).
    """
    if verbose:
        set_level("DEBUG")
    elif quiet:
        set_level("ERROR")
    # force_json is accepted for CLI compatibility but is a no-op:
    # this module always outputs JSON because "parseable by both humans
    # and machines" is the spec.


def _timestamp() -> str:
    """ISO 8601 timestamp with milliseconds, UTC."""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def log_event(
    severity: str,
    component: str,
    message: str,
    **metadata: object,
) -> None:
    """Emit a structured log event to stderr.

    Args:
        severity: One of DEBUG, INFO, WARN, ERROR, PANIC.
        component: Short subsystem identifier (ingest, lint, backup, ...).
        message: Human-readable log message.
        **metadata: Additional structured key-value pairs serialized as JSON.
    """
    if LEVELS.get(severity, 0) < _current_level:
        return

    event: dict[str, object] = {
        "v": LOG_VERSION,
        "ts": _timestamp(),
        "lvl": severity,
        "cmp": component,
        "msg": message,
        **metadata,
    }
    # json.dumps with default=str handles datetime/Path/Exception gracefully
    print(json.dumps(event, default=str), file=sys.stderr)


# ── Convenience functions ────────────────────────────────────────────────


def debug(component: str, message: str, **metadata: object) -> None:
    """Log at DEBUG level."""
    log_event("DEBUG", component, message, **metadata)


def info(component: str, message: str, **metadata: object) -> None:
    """Log at INFO level."""
    log_event("INFO", component, message, **metadata)


def warn(component: str, message: str, **metadata: object) -> None:
    """Log at WARN level — unexpected but recoverable."""
    log_event("WARN", component, message, **metadata)


def error(component: str, message: str, **metadata: object) -> None:
    """Log at ERROR level — operation failed but system can continue."""
    log_event("ERROR", component, message, **metadata)


def panic(component: str, message: str, **metadata: object) -> None:
    """Log at PANIC level — unrecoverable; operation cannot continue."""
    log_event("PANIC", component, message, **metadata)
