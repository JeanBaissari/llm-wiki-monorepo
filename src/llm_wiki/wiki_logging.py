"""
wiki_logging.py — Structured JSON logging for the llm-wiki-monorepo.

Every log event is a single JSON line to stderr with fields:
    {"v":1,"ts":"2026-07-03T14:22:31.123Z","lvl":"ERROR","cmp":"ingest","msg":"LLM call failed",...}

Usage:
    from wiki_logging import info, warn, error, set_level, configure

    configure(quiet=True)          # suppress INFO/WARN/DEBUG
    configure(verbose=True)        # enable DEBUG
    info("ingest", "Ingest started", pages=5)
    error("llm", "API call failed", provider="openai", retry=2)
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

_current_level: int = LEVELS["INFO"] if os.isatty(sys.stderr.fileno()) else LEVELS["WARN"]


def set_level(level: str) -> None:
    global _current_level
    if level in LEVELS:
        _current_level = LEVELS[level]


def configure(
    quiet: bool = False,
    verbose: bool = False,
    force_json: bool = False,
) -> None:
    if verbose:
        set_level("DEBUG")
    elif quiet:
        set_level("ERROR")


def _timestamp() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def log_event(
    severity: str,
    component: str,
    message: str,
    **metadata: object,
) -> None:
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
    print(json.dumps(event, default=str), file=sys.stderr)


def debug(component: str, message: str, **metadata: object) -> None:
    log_event("DEBUG", component, message, **metadata)


def info(component: str, message: str, **metadata: object) -> None:
    log_event("INFO", component, message, **metadata)


def warn(component: str, message: str, **metadata: object) -> None:
    log_event("WARN", component, message, **metadata)


def error(component: str, message: str, **metadata: object) -> None:
    log_event("ERROR", component, message, **metadata)


def panic(component: str, message: str, **metadata: object) -> None:
    log_event("PANIC", component, message, **metadata)
