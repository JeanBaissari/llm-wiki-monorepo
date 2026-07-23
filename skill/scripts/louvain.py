#!/usr/bin/env python3
"""Thin wrapper — re-exports from llm_wiki.louvain."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm_wiki.graph.louvain import (
    detect_communities,
    louvain,
    _renumber_size_descending,
    _compute_modularity,
    compute_cohesion,
    build_top_nodes,
)
