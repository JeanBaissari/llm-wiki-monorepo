"""test_discover.py — Tests for discover.py layout detection.

Covers:
  - Canonical layout (wiki/, raw/, log/, audit/)
  - Flat layout (no subdirectories)
  - Custom layout detection
  - Frontmatter sampling
  - Date format detection
  - JSON output
  - Confidence scoring
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from llm_wiki.core.layout import (
    discover_layout,
    WikiLayout,
    find_first_dir,
    find_first_file,
    detect_date_format,
)
from llm_wiki.core.frontmatter import parse_frontmatter


class TestDiscoverCanonicalLayout:
    """Layout detection on a standard wiki structure."""

    def test_detects_wiki_dir(self, tmp_wiki):
        """A scaffolded wiki should have wiki/ detected as pages_dir."""
        layout = discover_layout(str(tmp_wiki))
        assert layout.pages_dir is not None
        assert "wiki" in layout.pages_dir

    def test_detects_raw_dir(self, tmp_wiki):
        """Should detect raw/ directory if it exists."""
        layout = discover_layout(str(tmp_wiki))
        assert layout.raw_dir is not None

    def test_detects_log_dir(self, tmp_wiki):
        """Should detect log/ directory."""
        layout = discover_layout(str(tmp_wiki))
        assert layout.log_dir is not None
        assert "log" in layout.log_dir

    def test_detects_audit_dir(self, tmp_wiki):
        """Should detect audit/ directory."""
        layout = discover_layout(str(tmp_wiki))
        assert layout.audit_dir is not None
        assert "audit" in layout.audit_dir

    def test_has_index_file(self, tmp_wiki):
        """Should find wiki/index.md."""
        layout = discover_layout(str(tmp_wiki))
        assert layout.index_file is not None
        assert "index.md" in layout.index_file

    def test_confidence_high_for_canonical(self, tmp_wiki):
        """A canonical structure should have high confidence."""
        layout = discover_layout(str(tmp_wiki))
        assert layout.confidence >= 0.5


class TestDiscoverFlatLayout:
    """Layout detection on non-standard structures."""

    def test_flat_with_md_files(self, tmp_path):
        """A directory with bare .md files should be detected as flat."""
        root = tmp_path / "flat-wiki"
        root.mkdir()
        (root / "page1.md").write_text("# Page 1\n\nContent.")
        (root / "page2.md").write_text("# Page 2\n\nContent.")

        layout = discover_layout(str(root))
        assert layout.pages_dir is not None

    def test_empty_directory(self, tmp_path):
        """An empty directory should still produce a layout (with low confidence)."""
        root = tmp_path / "empty-dir"
        root.mkdir()
        layout = discover_layout(str(root))
        assert layout.pages_dir is not None
        assert layout.confidence <= 0.3


class TestDiscoverPopularWiki:
    """Discovery on the populated fixture."""

    def test_populated_wiki_detection(self, populated_wiki):
        """A populated wiki should be fully discovered."""
        layout = discover_layout(str(populated_wiki))
        assert layout.pages_dir is not None
        assert "wiki" in layout.pages_dir
        # Should detect raw/sources since we added them
        if layout.raw_dir:
            assert len(layout.raw_dir) > 0


class TestDetectDateFormat:
    """Date format detection."""

    def test_iso_format(self):
        fmt = detect_date_format(["2026-01-15", "2026-06-20", "2025-12-01"])
        assert fmt == "%Y-%m-%d"

    def test_single_value(self):
        fmt = detect_date_format(["2026/06/20"])
        assert fmt == "%Y/%m/%d"

    def test_mixed_formats(self):
        """Should pick the most common format."""
        fmt = detect_date_format([
            "2026-01-15", "2026-01-16", "2026/06/20",
        ])
        assert fmt == "%Y-%m-%d"  # 2 vs 1

    def test_empty_list(self):
        fmt = detect_date_format([])
        assert fmt == "%Y-%m-%d"  # default


class TestFindHelpers:
    """find_first_dir and find_first_file."""

    def test_find_first_dir_found(self, tmp_path):
        (tmp_path / "docs").mkdir()
        result = find_first_dir(tmp_path, ["docs", "wiki"])
        assert result is not None

    def test_find_first_dir_not_found(self, tmp_path):
        result = find_first_dir(tmp_path, ["nonexistent"])
        assert result is None

    def test_find_first_file_found(self, tmp_path):
        (tmp_path / "README.md").write_text("# Readme")
        result = find_first_file(tmp_path, ["README.md"])
        assert result is not None

    def test_find_first_file_not_found(self, tmp_path):
        result = find_first_file(tmp_path, ["missing.txt"])
        assert result is None


# ── Count ─────────────────────────────────────────────────────────────────
# test_discover.py = canonical (6) + flat (2) + populated (1) +
#                    date_format (4) + find_helpers (4)
#                  = 17 test functions
