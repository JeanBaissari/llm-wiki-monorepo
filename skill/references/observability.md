# Observability Framework — llm-wiki-monorepo

> Structured logging, severity semantics, health checks, and CLI conventions.

## Overview

Every script in the monorepo emits structured JSON log events to stderr. This
enables consistent parsing by CI pipelines, cron monitors, and multi-agent
orchestrators.

**File**: `skill/scripts/wiki_logging.py` (named `wiki_logging.py` to avoid
collision with Python's stdlib `logging` module).

## Log Format

Every log event is a single JSON line to stderr:

```json
{"v":1,"ts":"2026-07-03T14:22:31.123Z","lvl":"INFO","cmp":"ingest","msg":"Ingest started","pages":5}
```

### Required Fields

| Field | Type   | Description                                      |
|-------|--------|--------------------------------------------------|
| `v`   | int    | Format version (always `1`).                     |
| `ts`  | string | ISO 8601 UTC timestamp with milliseconds.         |
| `lvl` | string | Severity level (DEBUG, INFO, WARN, ERROR, PANIC). |
| `cmp` | string | Component identifier (see below).                 |
| `msg` | string | Human-readable log message.                       |

Any additional keyword arguments become extra JSON fields.

### Severity Levels

| Level   | Semantics                                        | Example                                              |
|---------|--------------------------------------------------|------------------------------------------------------|
| `DEBUG` | Diagnostic details; off by default.              | `"SHA256 cache key: abc123"`                         |
| `INFO`  | Normal operational events.                       | `"Ingest complete: 5 pages created"`                 |
| `WARN`  | Unexpected but recoverable; operation continues. | `"Stale lock file detected and cleaned"`             |
| `ERROR` | Operation failed but system can continue.        | `"LLM call failed after 3 retries"`                  |
| `PANIC` | Unrecoverable; operation cannot continue.        | `"Wiki root directory not found"`                    |

### Component Identifiers

Standard component IDs for consistency:

| ID         | Subsystem              |
|------------|------------------------|
| `ingest`   | Page ingestion         |
| `lint`     | Wiki linting           |
| `backup`   | Backup/restore         |
| `lock`     | File locking           |
| `llm`      | LLM API calls          |
| `provider` | LLM provider selection |
| `mcp`      | MCP server             |
| `graph`    | Graph engine           |
| `scaffold` | Wiki scaffolding       |
| `link`     | Link suggestions       |
| `discover` | Layout discovery       |

## Module API

### `wiki_logging.py`

```python
from wiki_logging import (
    log_event,   # log_event(severity, component, message, **metadata)
    debug,       # debug(component, message, **metadata)
    info,        # info(component, message, **metadata)
    warn,        # warn(component, message, **metadata)
    error,       # error(component, message, **metadata)
    panic,       # panic(component, message, **metadata)
    set_level,   # set_level("DEBUG"|"INFO"|"WARN"|"ERROR")
    configure,   # configure(quiet=False, verbose=False)
    LEVELS,      # dict mapping level name → int priority
)
```

### CLI Integration

All scripts accept standardized flags:

```
--quiet      Set log level to ERROR (suppress INFO/WARN/DEBUG)
--verbose    Set log level to DEBUG (show diagnostic details)
--log-json   Accepted for compatibility; JSON is always the output format
```

Default behavior: `INFO` when stderr is a TTY, `WARN` when stderr is piped
(CI/cron). When both `--quiet` and `--verbose` are passed, `--verbose` wins.

```python
import argparse
from wiki_logging import configure

parser = argparse.ArgumentParser()
parser.add_argument("--quiet", action="store_true")
parser.add_argument("--verbose", action="store_true")
args = parser.parse_args()

configure(quiet=args.quiet, verbose=args.verbose)
```

## Health Check

### `skill/scripts/health_check.py`

Aggregates status from all subsystems and returns structured JSON to stdout.

```bash
python3 skill/scripts/health_check.py <wiki-root>
python3 skill/scripts/health_check.py <wiki-root> --quiet   # suppress INFO logs
python3 skill/scripts/health_check.py <wiki-root> --verbose # enable DEBUG logs
```

### Output

```json
{
  "wiki_root": "/path/to/wiki",
  "timestamp": "2026-07-03T14:22:31.123Z",
  "overall_status": "healthy",
  "exit_code": 0,
  "checks": {
    "structure": {"status": "healthy", "pages_dir": "...", "md_count": 54, ...},
    "required_dirs": {"status": "healthy", ...},
    "empty_wiki": {"status": "healthy", "md_file_count": 54},
    "stale_locks": {"status": "healthy", "lock_count": 0, ...},
    "unresolved_conflicts": {"status": "healthy", "conflict_files": 0, ...},
    "cache_integrity": {"status": "healthy", "cache_entries": 5, ...},
    "index_freshness": {"status": "healthy", "staleness_s": 0.0, ...},
    "log_integrity": {"status": "healthy", "log_file_count": 30, ...}
  }
}
```

### Exit Codes

| Code | Status    | Meaning                                      |
|------|-----------|----------------------------------------------|
| 0    | healthy   | All checks pass.                             |
| 1    | degraded  | Warnings: stale locks, old index, few pages. |
| 2    | broken    | Errors: conflicts, corruption, missing dirs. |
| 3    | panic     | Unrecoverable: root missing, empty wiki.     |

### Individual Checks

1. **structure** — Validates wiki layout via `discover_layout()`. Panic if
   pages directory missing.
2. **required_dirs** — Checks that CLAUDE.md/SCHEMA.md and PURPOSE.md exist.
3. **empty_wiki** — Panic if 0 .md files; degraded if ≤3.
4. **stale_locks** — Scans for `*.lock` files with dead PIDs or age >30min.
5. **unresolved_conflicts** — Finds `*(conflict).md` files and inline
   `<<<<<<<` markers.
6. **cache_integrity** — Validates `raw/.cache/*.json` files are parseable.
7. **index_freshness** — Compares `index.md` mtime against newest page mtime.
   Degraded if >1h stale.
8. **log_integrity** — Counts H2 entries across log files. Degraded if >500.

### Cron Integration

Add to EOW pipeline:

```bash
#!/bin/bash
# End-of-week health check
STATUS=$(python3 skill/scripts/health_check.py ~/wiki --quiet | python3 -c "import sys,json; print(json.load(sys.stdin)['overall_status'])")
if [ "$STATUS" != "healthy" ]; then
    echo "Wiki health check: $STATUS — review needed" >&2
    exit 1
fi
```

## Migration Guide

### From bare prints to structured logging

Before:
```python
print(f"ERROR: wiki root not found: {wiki_root}", file=sys.stderr)
return 1
```

After:
```python
from wiki_logging import error
error("ingest", "Wiki root not found", path=wiki_root)
return 1
```

### Adding --quiet/--verbose to a script

```python
import argparse
from wiki_logging import configure

parser = argparse.ArgumentParser()
parser.add_argument("--quiet", action="store_true")
parser.add_argument("--verbose", action="store_true")
# ... other args ...
args = parser.parse_args()

configure(quiet=args.quiet, verbose=args.verbose)
```

## Testing

Tests live in `tests/test_logging.py`. Run with:

```bash
pytest tests/test_logging.py -v
```

Tests validate:
- Valid JSON output with all required fields
- Correct severity level per convenience function
- Severity filtering (INFO suppressed at WARN, PANIC always emitted)
- `configure()` sets correct levels
- Component identifiers preserved
- Arbitrary metadata serialization
- Non-serializable types handled gracefully (datetime, Path, Exception)
- Invalid `set_level()` is no-op
- Timestamps are monotonically increasing
- Format version is always 1
- Empty message and empty metadata work
- Rapid successive calls produce one JSON object per line

## Design Decisions

1. **Always JSON to stderr.** The PRD considered human-readable on TTY, JSON
   otherwise. Decision: always JSON. It's parseable by both humans and machines,
   and mixed output is a footgun for pipeline consumers.

2. **`wiki_logging.py` not `logging.py`.** Python's stdlib `logging` module
   shadows any local file named `logging.py`. The local file is renamed to
   `wiki_logging.py` to avoid the collision. This is non-negotiable — naming
   a Python file `logging.py` is a well-known anti-pattern.

3. **`configure(verbose=True)` wins over `configure(quiet=True)`.** When
   both flags are passed (e.g., `--quiet --verbose`), DEBUG level is used.
   This follows the principle that more information is better for debugging.

4. **`json.dumps(event, default=str)`.** Non-JSON-serializable types
   (datetime, Path, Exception) are converted to strings. The alternative
   — rejecting them — would cause runtime crashes in logging code, which is
   worse than producing slightly degraded metadata.
