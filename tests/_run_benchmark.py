#!/usr/bin/env python3
"""Quick benchmark runner for link_suggest — runs scales 100, 500, 1000.

Usage: cd to repo root, then python3 tests/_run_benchmark.py
"""
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skill" / "scripts"
TESTS_DIR = REPO_ROOT / "tests"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from test_link_suggest_benchmark import build_synthetic_wiki, run_benchmark

for page_count in [100, 500, 1000]:
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_dir = build_synthetic_wiki(Path(tmpdir), page_count)
        result = run_benchmark(wiki_dir, page_count, 100)
        print(f"{page_count:>4} pages | before: {result['time_before_ms']:>8.0f}ms | after: {result['time_after_ms']:>8.0f}ms | speedup: {result['speedup']:>5.1f}x | suggestions: {result['suggestion_count']}")
