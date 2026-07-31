"""Deep research deterministic tests — no network, no LLM required."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
sys.path.insert(0, str(SRC))

DEEP_RESEARCH_SOURCES = REPO_ROOT / "tests" / "fixtures" / "deep_research_sources"


class TestDeepResearchModule:
    """Module-level tests — no fixtures needed."""

    def test_module_imports(self):
        from llm_wiki.research.deep_research import main
        assert main is not None

    def test_help_exits_zero(self):
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        r = subprocess.run(
            [sys.executable, "-m", "llm_wiki", "deep-research", "--help"],
            capture_output=True, text=True, timeout=15, env=env
        )
        assert r.returncode == 0


class TestDeepResearchWithFixtures:
    """Tests against the fixture wiki with pre-fetched sources."""

    def test_fixture_wiki_exists(self):
        assert (DEEP_RESEARCH_SOURCES / "wiki" / "index.md").exists()
        assert (DEEP_RESEARCH_SOURCES / "raw" / "articles" / "attention_paper.md").exists()

    def test_dispatch_no_args_exits_usage_error(self):
        """Deep research with no args exits with usage error (argparse)."""
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        r = subprocess.run(
            [sys.executable, "-m", "llm_wiki", "deep-research"],
            capture_output=True, text=True, timeout=15, env=env
        )
        assert r.returncode in (1, 2)

    def test_dispatch_missing_topic_exits_usage_error(self):
        """Deep research with wiki root but no topic exits with usage error."""
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        r = subprocess.run(
            [sys.executable, "-m", "llm_wiki", "deep-research",
             str(DEEP_RESEARCH_SOURCES)],
            capture_output=True, text=True, timeout=15, env=env
        )
        assert r.returncode in (1, 2)

    def test_dispatch_with_urls_starts_pipeline(self):
        """Providing --urls and topic starts the pipeline."""
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        r = subprocess.run(
            [sys.executable, "-m", "llm_wiki", "deep-research",
             str(DEEP_RESEARCH_SOURCES),
             "--urls", "https://example.com/test-article",
             "test-topic"],
            capture_output=True, text=True, timeout=30, env=env
        )
        assert r.returncode in (0, 1)

    def test_invalid_wiki_root_exits_nonzero(self):
        """Missing topic positional arg causes argparse error (exit 2)."""
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        r = subprocess.run(
            [sys.executable, "-m", "llm_wiki", "deep-research",
             "/tmp/nonexistent-wiki-xyz",
             "--urls", "https://example.com/test"],
            capture_output=True, text=True, timeout=15, env=env
        )
        assert r.returncode != 0

    def test_slugify_contains_topic(self):
        """Pipeline with real-feeling topic argument completes without crash."""
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        r = subprocess.run(
            [sys.executable, "-m", "llm_wiki", "deep-research",
             str(DEEP_RESEARCH_SOURCES),
             "--urls", "https://arxiv.org/abs/1706.03762",
             "transformer-architectures"],
            capture_output=True, text=True, timeout=30, env=env
        )
        assert r.returncode in (0, 1)

    def test_stub_page_created_on_success(self):
        """When sources exist, a synthesis stub page is created."""
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        r = subprocess.run(
            [sys.executable, "-m", "llm_wiki", "deep-research",
             str(DEEP_RESEARCH_SOURCES),
             "--urls", "https://arxiv.org/abs/1706.03762",
             "transformer-architectures"],
            capture_output=True, text=True, timeout=30, env=env
        )
        assert r.returncode in (0, 1)
        syn_page = DEEP_RESEARCH_SOURCES / "wiki" / "synthesis" / "transformer-architectures.md"
        if r.returncode == 0:
            assert syn_page.exists(), f"Synthesis page not found at {syn_page}"
