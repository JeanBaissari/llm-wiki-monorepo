#!/usr/bin/env python3
"""health_check.py — Health check for LLM Wiki subsystems.

Aggregates status from all subsystems and reports:
    - Structure validity (via discover_layout)
    - Stale locks (.lock files with stale PIDs or old timestamps)
    - Unresolved conflicts (*(conflict).md files)
    - Cache integrity (raw/.cache corruption)
    - Index freshness (index.md age vs. wiki content)
    - Required directories exist
    - Empty wiki detection (no .md pages at all)

Exit codes:
    0 — healthy (all checks pass)
    1 — degraded (warnings found: stale locks, old index, confidence issues)
    2 — broken (errors found: unresolved conflicts, cache corruption, missing dirs)
    3 — panic (unrecoverable: wiki root not found, no pages dir, empty wiki)

Usage:
    python3 health_check.py <wiki-root>          # JSON to stdout, logs to stderr
    python3 health_check.py <wiki-root> --quiet  # suppress informational logs
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from discover import discover_layout
from wiki_logging import info, warn, error, panic, configure as log_configure

# ── Status ordering (higher = worse) ────────────────────────────────────

STATUS_ORDER: dict[str, int] = {
    "healthy": 0,
    "degraded": 1,
    "broken": 2,
    "panic": 3,
}


def _worse(a: str, b: str) -> str:
    """Return the worse of two statuses."""
    return b if STATUS_ORDER.get(b, 0) > STATUS_ORDER.get(a, 0) else a


def _status_exit_code(status: str) -> int:
    """Map status string to exit code."""
    return {"healthy": 0, "degraded": 1, "broken": 2, "panic": 3}.get(status, 3)


# ── Individual checks ───────────────────────────────────────────────────


def check_structure(wiki_root: Path) -> tuple[str, dict]:
    """Validate wiki structure via discover_layout."""
    try:
        layout = discover_layout(str(wiki_root))
        pages_path = Path(layout.pages_dir)
        if not pages_path.exists():
            return "panic", {"error": f"Pages directory not found: {layout.pages_dir}"}
        md_count = len(list(pages_path.rglob("*.md")))
        return "healthy", {
            "pages_dir": layout.pages_dir,
            "md_count": md_count,
            "layout_type": layout.discovery_method,
            "confidence": layout.confidence,
            "has_index": layout.index_file is not None,
            "has_schema": layout.schema_file is not None,
            "has_purpose": layout.purpose_file is not None,
        }
    except Exception as e:
        return "panic", {"error": str(e)}


def check_required_dirs(wiki_root: Path) -> tuple[str, dict]:
    """Check that expected wiki directories exist."""
    layout = discover_layout(str(wiki_root))
    missing: list[str] = []

    pages_path = Path(layout.pages_dir)
    if not pages_path.exists() or not pages_path.is_dir():
        missing.append(layout.pages_dir)

    # Required files — CLAUDE.md or SCHEMA.md
    schema_found = layout.schema_file is not None
    purpose_found = layout.purpose_file is not None

    result = {
        "missing_dirs": missing,
        "has_schema": schema_found,
        "has_purpose": purpose_found,
    }

    if missing:
        return "broken", result
    if not schema_found or not purpose_found:
        return "degraded", {**result, "warning": "Recommended files missing"}
    return "healthy", result


def check_stale_locks(wiki_root: Path) -> tuple[str, dict]:
    """Find .lock files that are stale (PID dead or >30min old)."""
    lock_files = list(wiki_root.rglob("*.lock"))
    if not lock_files:
        return "healthy", {"lock_count": 0, "stale_count": 0}

    now = time.time()
    stale_timeout = 30 * 60  # 30 minutes
    stale: list[str] = []

    for lf in lock_files:
        try:
            stat = lf.stat()
            age_s = now - stat.st_mtime
            # Read PID from lock file
            content = lf.read_text(encoding="utf-8", errors="replace").strip()
            pid_alive = False
            try:
                pid = int(content)
                os.kill(pid, 0)  # Signal 0 checks existence
                pid_alive = True
            except (ValueError, OSError):
                pass

            if not pid_alive or age_s > stale_timeout:
                stale.append(str(lf.relative_to(wiki_root)))
        except OSError:
            stale.append(str(lf.relative_to(wiki_root)))

    result = {
        "lock_count": len(lock_files),
        "stale_count": len(stale),
        "stale_files": stale[:20],
    }
    if stale:
        return "degraded", result
    return "healthy", result


def check_unresolved_conflicts(wiki_root: Path) -> tuple[str, dict]:
    """Find *(conflict).md files indicating unresolved merge conflicts."""
    conflict_files = list(wiki_root.rglob("*(conflict).md"))
    # Also check for conflict markers in wiki page content
    conflict_markers = 0
    pages_path = None
    try:
        layout = discover_layout(str(wiki_root))
        pages_path = Path(layout.pages_dir)
    except Exception:
        pass

    if pages_path and pages_path.exists():
        for md_file in pages_path.rglob("*.md"):
            try:
                text = md_file.read_text(encoding="utf-8", errors="replace")
                if text.startswith("<<<<<<<") or "\n<<<<<<<" in text:
                    conflict_markers += 1
            except OSError:
                pass

    result = {
        "conflict_files": len(conflict_files),
        "conflict_marker_files": conflict_markers,
        "paths": [str(p.relative_to(wiki_root)) for p in conflict_files[:10]],
    }
    if conflict_files or conflict_markers:
        return "broken", result
    return "healthy", result


def check_cache_integrity(wiki_root: Path) -> tuple[str, dict]:
    """Check raw/.cache for corrupt JSON files."""
    layout = discover_layout(str(wiki_root))
    raw_path = None
    if layout.raw_dir:
        raw_path = Path(layout.raw_dir)
    else:
        # Try common locations
        for cand in ["raw", "sources"]:
            p = wiki_root / cand
            if p.is_dir():
                raw_path = p
                break

    if not raw_path or not raw_path.is_dir():
        return "healthy", {"note": "No raw/ directory, skipping cache check"}

    cache_dir = raw_path / ".cache"
    if not cache_dir.exists():
        return "healthy", {"cache_entries": 0, "corrupt": 0}

    cache_files = list(cache_dir.glob("*.json"))
    corrupt: list[str] = []
    for cf in cache_files:
        try:
            with open(cf) as f:
                data = json.load(f)
            if not isinstance(data, dict) or "analysis" not in data:
                corrupt.append(str(cf.relative_to(wiki_root)))
        except (json.JSONDecodeError, OSError):
            corrupt.append(str(cf.relative_to(wiki_root)))

    result = {
        "cache_entries": len(cache_files),
        "corrupt": len(corrupt),
        "corrupt_files": corrupt[:10],
    }
    if corrupt:
        return "degraded", result
    return "healthy", result


def check_index_freshness(wiki_root: Path) -> tuple[str, dict]:
    """Check if index.md is stale relative to wiki page updates."""
    layout = discover_layout(str(wiki_root))
    pages_path = Path(layout.pages_dir)

    if not pages_path.exists():
        return "broken", {"error": "Pages directory not found"}

    index_path = pages_path / "index.md"
    if not index_path.exists():
        return "degraded", {"warning": "index.md not found"}

    try:
        index_mtime = index_path.stat().st_mtime
    except OSError:
        return "broken", {"error": "Cannot stat index.md"}

    # Find the most recent wiki page modification (excluding index.md)
    newest_mtime = index_mtime
    newest_file = ""
    for md_file in pages_path.rglob("*.md"):
        if md_file == index_path:
            continue
        try:
            mtime = md_file.stat().st_mtime
            if mtime > newest_mtime:
                newest_mtime = mtime
                newest_file = str(md_file.relative_to(wiki_root))
        except OSError:
            pass

    staleness_s = newest_mtime - index_mtime
    result = {
        "index_mtime": datetime.fromtimestamp(index_mtime, tz=timezone.utc).isoformat(),
        "newest_page_mtime": datetime.fromtimestamp(newest_mtime, tz=timezone.utc).isoformat(),
        "staleness_s": round(staleness_s, 1),
        "newest_file": newest_file,
    }

    # Pages newer than index means index is stale
    if staleness_s > 86400:  # More than 24h stale
        return "degraded", {**result, "warning": f"index.md is {staleness_s/86400:.1f} days stale"}
    elif staleness_s > 3600:  # More than 1h stale
        return "degraded", {**result, "warning": f"index.md is {staleness_s/3600:.1f} hours stale"}
    return "healthy", result


def check_empty_wiki(wiki_root: Path) -> tuple[str, dict]:
    """Check if wiki is empty (0 .md files in pages directory)."""
    try:
        layout = discover_layout(str(wiki_root))
        pages_path = Path(layout.pages_dir)
    except Exception:
        return "panic", {"error": "Cannot detect pages directory"}

    if not pages_path.exists():
        return "panic", {"error": f"Pages directory not found: {pages_path}"}

    md_files = list(pages_path.rglob("*.md"))
    result = {"md_file_count": len(md_files)}

    if len(md_files) == 0:
        return "panic", result
    if len(md_files) <= 3:
        return "degraded", {**result, "warning": "Very few pages — possibly incomplete wiki"}
    return "healthy", result


def check_log_integrity(wiki_root: Path) -> tuple[str, dict]:
    """Check log directory integrity."""
    layout = discover_layout(str(wiki_root))
    log_path = None
    if layout.log_dir:
        log_path = Path(layout.log_dir)
    else:
        for cand in ["log", "logs"]:
            p = wiki_root / cand
            if p.is_dir():
                log_path = p
                break

    if not log_path or not log_path.exists():
        return "healthy", {"note": "No log directory found"}

    log_files = [p for p in log_path.iterdir() if p.is_file() and p.name != ".gitkeep"]
    # Check H2 rotation threshold
    total_h2 = 0
    import re
    H2_RE = re.compile(r"^##\s", re.MULTILINE)
    for lf in log_files:
        try:
            text = lf.read_text(encoding="utf-8", errors="replace")
            total_h2 += len(H2_RE.findall(text))
        except OSError:
            pass

    result = {
        "log_file_count": len(log_files),
        "total_h2_entries": total_h2,
    }
    if total_h2 > 500:
        return "degraded", {**result, "warning": f"Log rotation needed — {total_h2} H2 entries (>500)"}
    return "healthy", result


# ── Aggregate health check ──────────────────────────────────────────────


def check_wiki_health(wiki_root: str) -> dict:
    """Run all health checks and return structured status."""
    root_path = Path(wiki_root).resolve()

    results: dict = {
        "wiki_root": str(root_path),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_status": "healthy",
        "checks": {},
        "exit_code": 0,
    }

    # Check 0: wiki root exists
    if not root_path.exists() or not root_path.is_dir():
        results["overall_status"] = "panic"
        results["exit_code"] = 3
        results["checks"]["wiki_root"] = {
            "status": "panic",
            "error": f"Wiki root not found or not a directory: {root_path}",
        }
        return results

    # Ordered checks (each may upgrade overall_status)
    checks = [
        ("structure", check_structure),
        ("required_dirs", check_required_dirs),
        ("empty_wiki", check_empty_wiki),
        ("stale_locks", check_stale_locks),
        ("unresolved_conflicts", check_unresolved_conflicts),
        ("cache_integrity", check_cache_integrity),
        ("index_freshness", check_index_freshness),
        ("log_integrity", check_log_integrity),
    ]

    overall = "healthy"
    for name, check_fn in checks:
        try:
            status, detail = check_fn(root_path)
        except Exception as e:
            status = "broken"
            detail = {"error": f"Check threw exception: {e}"}
            error("health_check", f"Check '{name}' failed with exception", error=str(e))

        results["checks"][name] = {"status": status, **detail}
        overall = _worse(overall, status)

        if status in ("panic", "broken"):
            warn("health_check", f"Check '{name}': {status}",
                 status=status, **{k: str(v)[:200] for k, v in detail.items()})
        elif status == "degraded":
            info("health_check", f"Check '{name}': degraded",
                 status=status)

    results["overall_status"] = overall
    results["exit_code"] = _status_exit_code(overall)

    info("health_check", "Health check complete",
         overall_status=overall, exit_code=results["exit_code"])
    return results


# ── CLI ─────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Health check for LLM Wiki subsystems."
    )
    parser.add_argument("wiki_root", help="Path to the wiki root directory")
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress INFO-level log output (only WARN and above)"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Enable DEBUG-level log output"
    )
    args = parser.parse_args()

    log_configure(quiet=args.quiet, verbose=args.verbose)

    results = check_wiki_health(args.wiki_root)

    # Output structured JSON to stdout
    print(json.dumps(results, indent=2, default=str))

    return results["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
