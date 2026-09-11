"""Documentation link integrity — tracked docs must not contain dead links.

Runs `scripts/docs_link_check.py` over the repo's documentation surfaces
(root docs, docs/, skill/, package READMEs) and fails on any missing relative
target or anchor. Keeps README/docs navigation honest across renames.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKER = REPO_ROOT / "scripts" / "docs_link_check.py"


def test_docs_links_are_valid():
    assert CHECKER.exists(), f"missing {CHECKER}"
    result = subprocess.run(
        [sys.executable, str(CHECKER)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Broken documentation links found:\n"
        f"{result.stdout}\n{result.stderr}"
    )
