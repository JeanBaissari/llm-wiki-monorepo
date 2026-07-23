"""Thin wrapper — re-exports from llm_wiki.atomic_write."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm_wiki.core.atomic import (
    atomic_write,
    cleanup_temp_files,
)
