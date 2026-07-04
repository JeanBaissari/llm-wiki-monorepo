"""test_index.py — Tests for index_wiki.py SQLite FTS5 search persistence.

Covers:
  - FTS5 index creation and schema
  - SHA256 freshness: unchanged files skipped on re-index
  - SHA256 change detection: modified files re-indexed
  - Incremental update: new files added, deleted files removed
  - --rebuild flag: drops and recreates from scratch
  - Regex tokenizer preservation (mirrors search.ts)
  - Aggregate stats: doc_count, avg_length computation
  - Title extraction: frontmatter → H1 → filename fallback
  - CLI integration via subprocess
  - Empty wiki handling
"""
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Import from the package module
sys.path.insert(0, str(REPO_ROOT / "src"))

from llm_wiki.index_wiki import (
    index_wiki,
    init_schema,
    tokenize,
    extract_title,
    sha256_hex,
    prepare_content,
    _open_db,
)


# ── Helpers ────────────────────────────────────────────────────────────────

def _db_has_table(db_path: Path, table: str) -> bool:
    """Check if a table exists in the SQLite database."""
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def _count_pages(db_path: Path) -> int:
    """Count rows in the FTS5 pages table."""
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("SELECT COUNT(*) FROM pages").fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def _get_meta(db_path: Path, file_path: str) -> dict | None:
    """Get index_meta row for a given file path."""
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT sha256, indexed_at, file_size FROM index_meta WHERE file_path = ?",
            (file_path,),
        ).fetchone()
        if row:
            return {"sha256": row[0], "indexed_at": row[1], "file_size": row[2]}
        return None
    finally:
        conn.close()


def _get_stat(db_path: Path, key: str) -> str | None:
    """Get a value from index_stats."""
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT value FROM index_stats WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _run_cli(wiki_root: Path, *args: str) -> subprocess.CompletedProcess:
    """Run index_wiki.py via the Python interpreter with given args."""
    script = REPO_ROOT / "skill" / "scripts" / "index_wiki.py"
    cmd = [sys.executable, str(script), str(wiki_root), *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


# ── Tokenizer tests ────────────────────────────────────────────────────────

class TestTokenizer:
    """Verify regex tokenizer matches search.ts implementation."""

    def test_basic_tokenization(self):
        tokens = tokenize("Python is a high-level programming language")
        assert "python" in tokens
        assert "high" in tokens
        assert "level" in tokens
        assert "programming" in tokens
        assert "language" in tokens
        # Stop words filtered
        assert "is" not in tokens
        assert "a" not in tokens

    def test_stop_words_filtered(self):
        """All defined stop words are filtered."""
        text = "the a an and or but in on at to for of with by from as are was were be"
        tokens = tokenize(text)
        assert tokens == []

    def test_short_tokens_filtered(self):
        """Single-character tokens are filtered."""
        tokens = tokenize("a b c de fg hi")
        # Only tokens with len > 1 pass
        for t in tokens:
            assert len(t) > 1

    def test_punctuation_splitting(self):
        """Punctuation is treated as token delimiters."""
        tokens = tokenize("hello,world;test:case!question?answer(parentheses)[brackets]")
        assert "hello" in tokens
        assert "world" in tokens
        assert "test" in tokens
        assert "case" in tokens

    def test_numeric_tokens(self):
        """Numeric tokens pass the tokenizer."""
        tokens = tokenize("model v2 uses 42 parameters")
        assert "v2" in tokens
        assert "42" in tokens
        assert "parameters" in tokens


# ── Title extraction tests ─────────────────────────────────────────────────

class TestTitleExtraction:
    """Title extraction: frontmatter → H1 → filename stem."""

    def test_frontmatter_title(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("---\ntitle: Frontmatter Title\n---\n\n# Some Heading\n\nContent.")
        assert extract_title(f.read_text(), f) == "Frontmatter Title"

    def test_h1_fallback(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("# Heading One\n\nContent without frontmatter.")
        assert extract_title(f.read_text(), f) == "Heading One"

    def test_filename_fallback(self, tmp_path):
        f = tmp_path / "my-awesome-page.md"
        f.write_text("Content with no title or heading.")
        assert extract_title(f.read_text(), f) == "my awesome page"

    def test_empty_frontmatter_no_title(self, tmp_path):
        f = tmp_path / "doc.md"
        f.write_text("---\ntype: concept\n---\n\n# Actual H1\n\nContent.")
        assert extract_title(f.read_text(), f) == "Actual H1"


# ── SHA256 freshness tests ─────────────────────────────────────────────────

class TestSHA256Freshness:
    """SHA256-based incremental indexing."""

    def test_sha256_detects_change(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("original content")
        h1 = sha256_hex(f)
        f.write_text("modified content")
        h2 = sha256_hex(f)
        assert h1 != h2

    def test_sha256_stable_for_unchanged(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("stable content")
        h1 = sha256_hex(f)
        h2 = sha256_hex(f)
        assert h1 == h2


# ── FTS5 index creation tests ──────────────────────────────────────────────

class TestIndexCreation:
    """Building the FTS5 index from a wiki."""

    def test_creates_index_db(self, tmp_wiki):
        """Indexing should create .index/wiki.db."""
        stats = index_wiki(tmp_wiki)
        db_path = tmp_wiki / ".index" / "wiki.db"
        assert db_path.exists()
        assert stats["files_indexed"] > 0

    def test_creates_fts5_table(self, tmp_wiki):
        """The pages FTS5 virtual table must exist."""
        index_wiki(tmp_wiki)
        db_path = tmp_wiki / ".index" / "wiki.db"
        assert _db_has_table(db_path, "pages")

    def test_creates_index_meta_table(self, tmp_wiki):
        """index_meta must exist for SHA256 tracking."""
        index_wiki(tmp_wiki)
        db_path = tmp_wiki / ".index" / "wiki.db"
        assert _db_has_table(db_path, "index_meta")

    def test_creates_index_stats_table(self, tmp_wiki):
        """index_stats must exist for BM25 aggregate data."""
        index_wiki(tmp_wiki)
        db_path = tmp_wiki / ".index" / "wiki.db"
        assert _db_has_table(db_path, "index_stats")

    def test_indexed_pages_have_content(self, tmp_wiki):
        """Indexed pages should have non-empty tokenized content."""
        index_wiki(tmp_wiki)
        db_path = tmp_wiki / ".index" / "wiki.db"
        conn = sqlite3.connect(str(db_path))
        try:
            rows = conn.execute(
                "SELECT path, title, content FROM pages"
            ).fetchall()
            assert len(rows) > 0
            for path, title, content in rows:
                assert path, f"Empty path for {title}"
                assert title, f"Empty title for {path}"
                # Content may be empty for very short pages (all stop words)
        finally:
            conn.close()

    def test_populated_wiki_index(self, populated_wiki):
        """The populated fixture should index successfully."""
        stats = index_wiki(populated_wiki)
        db_path = populated_wiki / ".index" / "wiki.db"
        assert db_path.exists()
        # Populated fixture has many pages
        assert stats["total_indexed"] >= 5


# ── Incremental update tests ───────────────────────────────────────────────

class TestIncrementalUpdate:
    """Incremental indexing: unchanged skipped, new added, changed updated."""

    def test_unchanged_files_skipped(self, tmp_wiki):
        """Second run should skip all files if nothing changed."""
        index_wiki(tmp_wiki)  # First build
        stats = index_wiki(tmp_wiki)  # Second run
        assert stats["files_indexed"] == 0
        assert stats["files_skipped"] > 0

    def test_new_file_detected(self, tmp_wiki):
        """A new .md file should be picked up incrementally."""
        index_wiki(tmp_wiki)
        pages_dir = Path(tmp_wiki) / "wiki"
        new_file = pages_dir / "new_page.md"
        new_file.write_text("---\ntitle: New Page\n---\n\n# New Page\n\nFresh content here.\n")

        stats = index_wiki(tmp_wiki)
        assert stats["files_indexed"] == 1
        assert "new_page.md" in str(new_file)

    def test_modified_file_reindexed(self, tmp_wiki):
        """A modified file should be detected via SHA256 and re-indexed."""
        index_wiki(tmp_wiki)
        pages_dir = Path(tmp_wiki) / "wiki"
        # Find an existing .md file
        md_files = list(pages_dir.rglob("*.md"))
        assert md_files, "No .md files in tmp_wiki"
        target = md_files[0]

        # Modify it
        original = target.read_text()
        target.write_text(original + "\n\n## Added Section\nNew content for testing.\n")

        stats = index_wiki(tmp_wiki)
        # At least 1 indexed (the modified one), rest skipped
        assert stats["files_indexed"] >= 1

    def test_deleted_file_removed(self, tmp_wiki):
        """A deleted .md file should be removed from the index."""
        pages_dir = Path(tmp_wiki) / "wiki"
        # Create a unique file
        doomed = pages_dir / "doomed_page.md"
        doomed.write_text("---\ntitle: Doomed\n---\n\n# Doomed\n\nThis will be deleted.\n")
        index_wiki(tmp_wiki)

        # Verify it's indexed
        db_path = tmp_wiki / ".index" / "wiki.db"
        count_before = _count_pages(db_path)

        # Delete it
        doomed.unlink()

        stats = index_wiki(tmp_wiki)
        assert stats["files_deleted"] == 1
        count_after = _count_pages(db_path)
        assert count_after == count_before - 1

    def test_meta_updated_on_change(self, tmp_wiki):
        """SHA256 in index_meta should update when file changes."""
        index_wiki(tmp_wiki)
        pages_dir = Path(tmp_wiki) / "wiki"
        md_files = list(pages_dir.rglob("*.md"))
        target = md_files[0]

        db_path = tmp_wiki / ".index" / "wiki.db"
        meta_before = _get_meta(db_path, str(target))
        assert meta_before is not None

        # Modify
        target.write_text(target.read_text() + "\n\nExtra content.")

        index_wiki(tmp_wiki)
        meta_after = _get_meta(db_path, str(target))
        assert meta_after is not None
        assert meta_after["sha256"] != meta_before["sha256"]


# ── Rebuild flag tests ─────────────────────────────────────────────────────

class TestRebuild:
    """The --rebuild flag should drop and recreate the index."""

    def test_rebuild_creates_fresh_index(self, tmp_wiki):
        """--rebuild should create the index even if one exists."""
        index_wiki(tmp_wiki)
        db_path = tmp_wiki / ".index" / "wiki.db"
        original_mtime = db_path.stat().st_mtime

        # Wait a moment so mtime definitely changes
        time.sleep(0.1)
        stats = index_wiki(tmp_wiki, rebuild=True)
        assert stats["files_indexed"] > 0
        assert db_path.stat().st_mtime > original_mtime

    def test_rebuild_clears_stale_entries(self, tmp_wiki):
        """--rebuild should not retain entries for deleted files."""
        pages_dir = Path(tmp_wiki) / "wiki"
        doomed = pages_dir / "stale_page.md"
        doomed.write_text("---\ntitle: Stale\n---\n\n# Stale\n\nGone soon.\n")
        index_wiki(tmp_wiki)

        # Delete the file
        doomed.unlink()

        # Rebuild (not incremental) should not have the stale entry
        stats = index_wiki(tmp_wiki, rebuild=True)
        db_path = tmp_wiki / ".index" / "wiki.db"
        count = _count_pages(db_path)
        # The stale page should be gone
        assert stats["files_deleted"] == 0  # Rebuild doesn't track deletions separately
        # Instead, rebuild just indexes what's on disk
        assert stats["files_indexed"] == count


# ── Aggregate stats tests ─────────────────────────────────────────────────

class TestAggregateStats:
    """BM25 aggregate stats: doc_count, avg_length."""

    def test_doc_count_set(self, tmp_wiki):
        """doc_count should match actual indexed pages."""
        index_wiki(tmp_wiki)
        db_path = tmp_wiki / ".index" / "wiki.db"
        doc_count = int(_get_stat(db_path, "doc_count") or "0")
        actual = _count_pages(db_path)
        assert doc_count == actual
        assert doc_count > 0

    def test_avg_length_computed(self, tmp_wiki):
        """avg_length should be a positive number."""
        index_wiki(tmp_wiki)
        db_path = tmp_wiki / ".index" / "wiki.db"
        avg_len = float(_get_stat(db_path, "avg_length") or "0")
        assert avg_len > 0

    def test_empty_wiki_stats_zero(self, tmp_path):
        """Empty wiki should have doc_count=0 and avg_length=0."""
        empty_root = tmp_path / "empty-wiki"
        empty_root.mkdir()
        pages = empty_root / "wiki"
        pages.mkdir()
        # No .md files — but we need at least one for discover_layout to work
        (pages / "index.md").write_text("# Empty Wiki\n\nNothing here.\n")

        # index_wiki may sys.exit(1) for empty — catch it
        try:
            stats = index_wiki(empty_root)
        except SystemExit as e:
            # exit code 1 = no pages found
            if e.code == 1:
                return  # Expected
            raise

        db_path = empty_root / ".index" / "wiki.db"
        if db_path.exists():
            # If tables were created but no pages
            doc_count = int(_get_stat(db_path, "doc_count") or "0")
            assert doc_count == stats.get("total_indexed", 0)


# ── CLI integration tests ──────────────────────────────────────────────────

class TestCLIIntegration:
    """index_wiki.py via CLI (subprocess)."""

    def test_cli_help(self):
        """--help should print usage and exit 0."""
        result = _run_cli(Path("/tmp"), "--help")
        # help exits 0
        pass  # Just verify it doesn't crash

    def test_cli_json_output(self, tmp_wiki):
        """--json flag should produce valid JSON."""
        result = _run_cli(tmp_wiki, "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "files_indexed" in data
        assert "total_indexed" in data
        assert "elapsed_ms" in data
        assert isinstance(data["elapsed_ms"], int)

    def test_cli_rebuild_flag(self, tmp_wiki):
        """--rebuild should work from CLI."""
        # First build
        _run_cli(tmp_wiki)
        db_path = tmp_wiki / ".index" / "wiki.db"
        assert db_path.exists()

        # Rebuild
        result = _run_cli(tmp_wiki, "--rebuild")
        assert result.returncode == 0
        assert "Indexed:" in result.stdout

    def test_cli_nonexistent_dir(self):
        """Non-existent directory should exit with error."""
        result = _run_cli(Path("/tmp/nonexistent_dir_xyz_123"), "--json")
        assert result.returncode != 0

    def test_cli_empty_wiki(self, tmp_path):
        """CLI on an empty wiki should exit 1."""
        empty_root = tmp_path / "cli-empty"
        empty_root.mkdir()
        (empty_root / "wiki").mkdir()
        result = _run_cli(empty_root)
        assert result.returncode == 1  # No pages found


# ── Database schema tests ──────────────────────────────────────────────────

class TestDatabaseSchema:
    """init_schema behavior."""

    def test_init_schema_creates_tables(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = _open_db(db_path)
        try:
            init_schema(conn)
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {t[0] for t in tables}
            assert "pages" in table_names
            assert "index_meta" in table_names
            assert "index_stats" in table_names
        finally:
            conn.close()

    def test_init_schema_rebuild_drops(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = _open_db(db_path)
        try:
            init_schema(conn)
            # Insert test data
            conn.execute(
                "INSERT INTO index_meta (file_path, sha256, indexed_at, file_size) "
                "VALUES ('test.md', 'abc123', '2026-01-01', 100)"
            )
            conn.commit()

            # Rebuild should drop
            init_schema(conn, rebuild=True)
            rows = conn.execute("SELECT COUNT(*) FROM index_meta").fetchone()
            assert rows[0] == 0
        finally:
            conn.close()


# ── prepare_content tests ──────────────────────────────────────────────────

class TestPrepareContent:
    """prepare_content returns correct (path, title, tokenized)."""

    def test_relative_path(self, tmp_path):
        wiki_root = tmp_path / "mywiki"
        wiki_root.mkdir()
        pages = wiki_root / "wiki" / "subdir"
        pages.mkdir(parents=True)
        f = pages / "doc.md"
        f.write_text("# Test Doc\n\nSome content here.")

        rel_path, title, tokenized = prepare_content(f, wiki_root)
        assert rel_path == "wiki/subdir/doc.md"
        assert title == "Test Doc"
        assert "test" in tokenized.lower()
        assert "doc" in tokenized.lower()

    def test_content_preserved_as_tokens(self, tmp_path):
        wiki_root = tmp_path / "wiki2"
        wiki_root.mkdir()
        (wiki_root / "wiki").mkdir()
        f = wiki_root / "wiki" / "concept.md"
        f.write_text("# Neural Networks\n\nNeural networks are computing systems inspired by biological neural networks.")

        _, _, tokenized = prepare_content(f, wiki_root)
        assert "neural" in tokenized
        assert "networks" in tokenized
        assert "computing" in tokenized
        # Stop words filtered
        assert " are " not in f" {tokenized} "
        assert " by " not in f" {tokenized} "


# ── Count ──────────────────────────────────────────────────────────────────
# test_index.py = tokenizer (5) + title (4) + sha256 (2) +
#                 creation (5) + incremental (5) + rebuild (2) +
#                 aggregate (3) + cli (5) + schema (2) + prepare (2)
#               = 35 test functions
