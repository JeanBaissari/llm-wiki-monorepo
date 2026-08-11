"""llm_wiki — Knowledge base operating system.

AI agents compile raw sources into persistent, cross-linked Markdown wikis.
Knowledge compounds over time. No database. No API lock-in. Just files.
"""

import sys as _sys

# Windows consoles default to the ANSI codepage (cp1252), which cannot encode
# the ✓/⚠/→ markers used across the CLI — ingest, lint and scaffold crashed
# with UnicodeEncodeError on Windows CI. Force UTF-8 output (with replacement)
# on every entry path (CLI, skill scripts, module mains). Guarded: some
# embedding environments (pytest capture) do not allow stdout reconfigure.
for _stream in (_sys.stdout, _sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        break

__version__ = "0.6.1"

__all__ = [
    "cli",
    "contracts",
    "core",
    "quality",
    "providers",
    "ingest",
    "graph",
    "search",
    "ops",
    "wiki",
    "research",
]
