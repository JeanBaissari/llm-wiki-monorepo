#!/usr/bin/env python3
"""Thin wrapper — re-exports from llm_wiki.wiki_logging."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm_wiki.wiki_logging import *
from llm_wiki.wiki_logging import (
    set_level,
    configure,
    log_event,
    debug,
    info,
    warn,
    error,
    panic,
)
