#!/usr/bin/env python3
"""Thin wrapper — delegates to llm_wiki.migrate_log."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm_wiki.ops.migrate import main

if __name__ == "__main__":
    raise SystemExit(main())
