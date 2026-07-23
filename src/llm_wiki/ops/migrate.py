#!/usr/bin/env python3
"""
migrate_log.py — Convert old-style single log.md to new log/ directory format.

Usage:
    python3 migrate_log.py <wiki-root>

Description:
    Reads the old <wiki-root>/log.md file and converts it into the new
    log/YYYYMMDD.md directory format.  Each day's entries are grouped into
    a single file with H1 '# YYYY-MM-DD' and H2 entries for each operation.

    The old log.md format uses::

        ## [YYYY-MM-DD] op | description

    Optionally with a time component::

        ## [YYYY-MM-DD HH:MM] op | description

    The new format converts the ``[YYYY-MM-DD]`` date prefix to a time prefix
    ``[HH:MM]`` (defaulting to ``00:00`` if no time was recorded, preserving
    the rest of the entry line).

    After successful conversion the original log.md is deleted so the wiki
    is left entirely on the new per-day-file scheme.

Example log.md being migrated::

    ## [2025-03-10] ingest | added paper on attention mechanisms
    ## [2025-03-10] edit | updated transformer architecture page
    ## [2025-03-11] review | weekly content review

    After migration:
        log/20250310.md → H1 '# 2025-03-10', two H2 entries
        log/20250311.md → H1 '# 2025-03-11', one H2 entry
"""

import re
import sys
from collections import defaultdict
from pathlib import Path


# Matches: "## [YYYY-MM-DD]" or "## [YYYY-MM-DD HH:MM]" followed by rest of line
LOG_ENTRY_RE = re.compile(
    r"^##\s+\[(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?\]\s*(.*)"
)


def migrate(root: str) -> int:
    root_path = Path(root)
    log_md = root_path / "log.md"
    log_dir = root_path / "log"

    if not log_md.exists():
        print("No log.md found — nothing to migrate")
        return 0

    # Read and parse the old log file
    text = log_md.read_text(encoding="utf-8")

    entries_by_date: dict[str, list[str]] = defaultdict(list)
    current_date: str | None = None
    total_entries = 0

    for line in text.splitlines():
        m = LOG_ENTRY_RE.match(line)
        if m:
            date = m.group(1)               # YYYY-MM-DD
            time = m.group(2) or "00:00"    # HH:MM or default
            rest = m.group(3).strip()       # "op | description"
            entries_by_date[date].append(f"## [{time}] {rest}")
            current_date = date
            total_entries += 1
        elif current_date and line.strip():
            # Continuation line of the previous entry — append indented
            entries_by_date[current_date][-1] += f"\n  {line.rstrip()}"

    if not entries_by_date:
        print("No log entries found in log.md — nothing to migrate")
        return 0

    # Ensure log/ directory exists
    log_dir.mkdir(parents=True, exist_ok=True)

    # Write one file per distinct date
    days = 0
    for date in sorted(entries_by_date.keys()):
        y, mo, d = date.split("-")
        filename = f"{y}{mo}{d}.md"
        file_path = log_dir / filename

        # Build content: H1 heading, blank line, then all H2 entries
        lines = [f"# {date}", ""]
        for entry in entries_by_date[date]:
            lines.append(entry)
        lines.append("")  # trailing newline

        file_path.write_text("\n".join(lines), encoding="utf-8")
        days += 1

    # Remove old monolithic log.md now that everything is safely migrated
    log_md.unlink()

    print(f"Migrated {total_entries} entries across {days} days")
    print(f"  Source: {log_md}")
    print(f"  Target: {log_dir}/")

    return 0


def main() -> int:
    import sys
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    return migrate(sys.argv[1])


if __name__ == "__main__":
    sys.exit(main())
