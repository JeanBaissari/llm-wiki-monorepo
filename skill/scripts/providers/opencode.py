"""Thin wrapper — delegates to llm_wiki.providers.opencode."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm_wiki.providers.opencode import (
    OpenCodeProvider,
    IPC_BASE,
    create_ipc_dirs,
    cleanup_ipc_dirs,
)
