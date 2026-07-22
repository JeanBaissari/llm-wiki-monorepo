"""Thin wrapper — re-exports from llm_wiki.providers."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm_wiki.providers import *
from llm_wiki.providers import (
    LLMResponse,
    ProviderNotAvailableError,
    detect_default_provider,
)
