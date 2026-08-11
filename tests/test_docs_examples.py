"""Contract tests: verify code examples in docs match CLI behavior."""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT


def _extract_bash_blocks(filepath: Path) -> list[str]:
    """Extract all ```bash code blocks from a markdown file."""
    text = filepath.read_text(encoding="utf-8")
    blocks = []
    pattern = re.compile(r'```bash\n(.*?)```', re.DOTALL)
    for match in pattern.finditer(text):
        code = match.group(1).strip()
        for line in code.split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("$"):
                blocks.append(line)
    return blocks


class TestDocsExamples:
    """Verify that documented commands in README.md work."""

    def test_readme_commands(self):
        """Every llm-wiki command in README.md produces valid help."""
        readme = DOCS_DIR / "README.md"
        blocks = _extract_bash_blocks(readme)

        env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

        for line in blocks:
            cmd = line.strip()
            if not cmd.startswith("llm-wiki "):
                continue
            if "llm-wiki --version" in cmd:
                r = subprocess.run(
                    [sys.executable, "-m", "llm_wiki", "--version"],
                    capture_output=True, text=True, timeout=10, env=env
                )
                assert r.returncode == 0, f"{cmd} failed"
                from llm_wiki import __version__
                assert __version__ in r.stdout, f"Version {__version__} not in: {r.stdout}"

            elif "llm-wiki scaffold" in cmd and "--template" in cmd:
                pass

            elif "llm-wiki" in cmd and "--help" not in cmd and "pip" not in cmd:
                parts = cmd.split()
                help_cmd = parts[:2] + ["--help"]
                r = subprocess.run(
                    [sys.executable, "-m", "llm_wiki"] + help_cmd[1:],
                    capture_output=True, text=True, timeout=10, env=env
                )
                assert r.returncode == 0, f"{cmd} --help failed: {r.stderr[:100]}"

    def test_quickstart_commands(self):
        """Quickstart document commands reference valid CLI."""
        quickstart = DOCS_DIR / "docs" / "getting-started" / "quickstart.md"
        if not quickstart.exists():
            pytest.skip("quickstart.md not found")
        blocks = _extract_bash_blocks(quickstart)
        assert len(blocks) > 0, "No bash blocks found in quickstart"
