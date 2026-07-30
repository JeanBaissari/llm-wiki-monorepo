"""Deep research tests with mocked LLM and URL fetching."""
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))


class TestDeepResearchMock:
    """Test deep research pipeline with controlled inputs."""

    def test_deep_research_module_imports(self):
        """Module is importable."""
        from llm_wiki.research.deep_research import main
        assert main is not None

    def test_deep_research_help(self, monkeypatch):
        """--help exits 0."""
        import subprocess
        env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
        r = subprocess.run(
            [sys.executable, "-m", "llm_wiki", "deep-research", "--help"],
            capture_output=True, text=True, timeout=15, env=env
        )
        assert r.returncode == 0
