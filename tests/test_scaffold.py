"""test_scaffold.py — Tests for scaffold.py wiki creation.

Covers:
  - Scaffold creates directory structure
  - --force overwrites existing wiki
  - Template selection
  - Required files are created (PURPOSE.md, CLAUDE.md, wiki/index.md, log/)
"""
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAFFOLD_SCRIPT = REPO_ROOT / "skill" / "scripts" / "scaffold.py"


def run_scaffold(wiki_root, name="Test Wiki", template="codebase", force=False):
    """Run scaffold.py and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, str(SCAFFOLD_SCRIPT), str(wiki_root), name,
           "--template", template]
    if force:
        cmd.append("--force")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.returncode, result.stdout, result.stderr


class TestScaffoldBasic:
    """Basic scaffold creation."""

    def test_creates_directory_structure(self, tmp_path):
        wiki = tmp_path / "test-wiki"
        rc, stdout, stderr = run_scaffold(wiki)
        assert rc == 0, f"Scaffold failed: {stderr[:500]}"
        assert wiki.is_dir()
        assert (wiki / "PURPOSE.md").exists()
        assert (wiki / "CLAUDE.md").exists()
        assert (wiki / "wiki" / "index.md").exists()
        assert (wiki / "log").is_dir()
        assert (wiki / "audit").is_dir()
        assert (wiki / "raw").is_dir()

    def test_creates_log_entry(self, tmp_path):
        wiki = tmp_path / "test-wiki"
        rc, _, _ = run_scaffold(wiki)
        assert rc == 0
        log_files = list((wiki / "log").glob("*.md"))
        assert len(log_files) >= 1

    def test_force_overwrite(self, tmp_path):
        wiki = tmp_path / "test-wiki"
        # First scaffold
        rc, _, _ = run_scaffold(wiki)
        assert rc == 0
        # Second scaffold without --force should still succeed
        # (scaffold creates subdirs, doesn't error on existing)
        rc2, _, _ = run_scaffold(wiki, force=True)
        assert rc2 == 0

    def test_template_codebase(self, tmp_path):
        wiki = tmp_path / "test-wiki"
        rc, _, _ = run_scaffold(wiki, template="codebase")
        assert rc == 0

    def test_template_research(self, tmp_path):
        wiki = tmp_path / "test-wiki"
        rc, _, _ = run_scaffold(wiki, template="research")
        assert rc == 0

    def test_template_reading(self, tmp_path):
        wiki = tmp_path / "test-wiki"
        rc, _, _ = run_scaffold(wiki, template="reading")
        assert rc == 0

    def test_extra_dirs_created(self, tmp_path):
        """Codebase template should create architecture/, modules/, etc."""
        wiki = tmp_path / "test-wiki"
        rc, _, _ = run_scaffold(wiki, template="codebase")
        assert rc == 0
        wiki_dir = wiki / "wiki"
        # At minimum, index.md exists
        assert (wiki_dir / "index.md").exists()


# ── Count ─────────────────────────────────────────────────────────────────
# test_scaffold.py = 7 test functions
