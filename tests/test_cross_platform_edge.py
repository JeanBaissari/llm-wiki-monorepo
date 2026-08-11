"""test_cross_platform_edge.py — Lane-X (§7.8) cross-platform hardening tests.

Locks in the regressions the CI green-up rounds fixed on Windows/macOS. Each
test class maps to a specific historical bug (see git log):

  TestSymlinkedWikiPaths      macOS `/var` symlink resolution (847eb9e — round 5)
                              resolve() in layout.py / index.py: indexing under a
                              symlinked prefix indexed 0 files.
  TestPathNormalization       forward-slash path normalization (d073a8f round 6,
                              71b1e6a round 7, 7ca73b0 round 8, 5ffde89 round 9):
                              FTS incremental deletes, wikilink page keys, lint
                              paths all use str(x).replace(os.sep, "/").
  TestCRLFTolerance           Windows CRLF line endings (.gitattributes -text,
                              rounds 5-7): frontmatter/log regexes and round-trips
                              must survive \r\n.
  TestNonUtf8Decode           Windows cp1252 / non-UTF8 bytes (7d97a47, d073a8f,
                              71b1e6a): readers use encoding="utf-8",
                              errors="replace" so latin-1/cp1252 pages never crash.
  TestAtomicWrite             os.replace atomic writes (847eb9e — round 5): no
                              partial files on failure, Windows-safe replace.
  TestUtf8StdoutReconfigure   UTF-8 stdio reconfigure (7d97a47, d073a8f,
                              d68791a-era __init__): ✓/⚠ markers never raise
                              UnicodeEncodeError under an ANSI/ASCII stdout.

Every test runs on Linux today and is portable to macOS/Windows CI.
"""
import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path, PureWindowsPath

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from llm_wiki.core.atomic import atomic_write
from llm_wiki.core.frontmatter import parse_frontmatter
from llm_wiki.core.layout import discover_layout
from llm_wiki.core.wikilinks import load_pages
from llm_wiki.quality.lint.service import lint
from llm_wiki.search.index import index_wiki, prepare_content, extract_title


# ══════════════════════════════════════════════════════════════════════════
# Shared helpers
# ══════════════════════════════════════════════════════════════════════════

def _page_fm(title: str, ptype: str, day: str) -> str:
    return (
        f"---\ntitle: {title}\ntype: {ptype}\n"
        f"created: {day}\nupdated: {day}\n---\n\n"
    )


def _clean_wiki(root: Path, content_pages: int = 2) -> Path:
    """Build a canonical, lint-clean wiki (lint() returns 0).

    layout: wiki/{index.md, entities/pageN.md}, raw/, log/, audit/resolved/,
    outputs/queries/. All pages cross-linked and listed in index.md with recent
    dates. Returns the wiki root.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    for sub in (
        "wiki/entities",
        "wiki/concepts",
        "raw",
        "log",
        "audit/resolved",
        "outputs/queries",
    ):
        (root / sub).mkdir(parents=True, exist_ok=True)

    pages = [
        (f"entities/page{i}.md", f"page{i}", f"Page {i}", "entity")
        for i in range(1, content_pages + 1)
    ]
    stems = [stem for _, stem, _, _ in pages]
    index_links = " ".join(f"[[{stem}]]" for stem in stems)
    (root / "wiki" / "index.md").write_text(
        _page_fm("Index", "index", today) + f"# Index\n\n{index_links}\n",
        encoding="utf-8",
    )
    for rel, stem, title, ptype in pages:
        body = f"# {title}\n\nContent for {title}.\n"
        other_links = " ".join(f"[[{o}]]" for o in stems if o != stem)
        if other_links:
            body += other_links + "\n"
        (root / "wiki" / rel).write_text(
            _page_fm(title, ptype, today) + body, encoding="utf-8"
        )
    return root


def _symlink_dir(target: Path, link: Path) -> None:
    """Create a directory symlink; skip the test if the environment forbids it.

    Windows requires Developer Mode / admin privileges for symlink creation —
    when unavailable (a genuine platform limitation) the test is skipped rather
    than failed.
    """
    try:
        link.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError) as e:
        pytest.skip(
            f"directory symlinks unavailable here (Windows needs Developer "
            f"Mode/admin): {e}"
        )


def _count_pages(db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
    finally:
        conn.close()


def _fts_paths(db_path: Path) -> list[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        return [r[0] for r in conn.execute("SELECT path FROM pages")]
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════
# Symlinked wiki paths — macOS /var fix (CI round 5, 847eb9e)
# ══════════════════════════════════════════════════════════════════════════

class TestSymlinkedWikiPaths:
    """discover/index/lint must work when given the path of a symlink to a wiki.

    The historical bug: discover_layout() resolves symlinks (e.g. /var →
    /private/var on macOS) but index.py compared relative_to() against the
    unresolved root, so every file was skipped as "not in subpath" → 0 files
    indexed under a symlinked prefix.
    """

    def test_discover_via_symlinked_root(self, tmp_path):
        real = _clean_wiki(tmp_path / "real", content_pages=2)
        link = tmp_path / "wiki-link"
        _symlink_dir(real, link)

        layout = discover_layout(str(link))
        # Paths must resolve to the real location, not the symlink spelling
        assert Path(layout.pages_dir) == (real / "wiki").resolve()
        assert Path(layout.raw_dir) == (real / "raw").resolve()
        assert Path(layout.log_dir) == (real / "log").resolve()
        assert Path(layout.audit_dir) == (real / "audit").resolve()
        assert layout.confidence > 0

    def test_index_via_symlinked_root(self, tmp_path):
        real = _clean_wiki(tmp_path / "real", content_pages=2)
        link = tmp_path / "wiki-link"
        _symlink_dir(real, link)

        stats = index_wiki(link)
        # The regression: 0 files indexed under a symlinked prefix
        assert stats["files_indexed"] == 3
        assert stats["total_indexed"] == 3

        db = real / ".index" / "wiki.db"
        assert db.exists()
        # Every index_meta path must live under the RESOLVED real root
        root_resolved = str(real.resolve())
        conn = sqlite3.connect(str(db))
        try:
            metas = [r[0] for r in conn.execute("SELECT file_path FROM index_meta")]
        finally:
            conn.close()
        assert len(metas) == 3
        for fp in metas:
            assert str(Path(fp).resolve()).startswith(root_resolved)

    def test_lint_via_symlinked_root(self, tmp_path):
        real = _clean_wiki(tmp_path / "real", content_pages=2)
        link = tmp_path / "wiki-link"
        _symlink_dir(real, link)
        assert lint(str(link)) == 0

    def test_symlinked_page_subdir(self, tmp_path):
        """A subdirectory of the wiki that is itself a symlink must not crash,
        duplicate, or recursively traverse."""
        real = _clean_wiki(tmp_path / "real", content_pages=1)
        external = tmp_path / "external"
        (external / "concepts").mkdir(parents=True)
        today = datetime.now().strftime("%Y-%m-%d")
        (external / "concepts" / "zeta.md").write_text(
            _page_fm("Zeta", "concept", today)
            + "# Zeta\n\nReached via a symlinked subdirectory.\n",
            encoding="utf-8",
        )
        # Replace the (empty) real concepts dir with a symlink to external/
        (real / "wiki" / "concepts").rmdir()
        _symlink_dir(external / "concepts", real / "wiki" / "concepts")

        layout = discover_layout(str(real))
        assert Path(layout.pages_dir) == (real / "wiki").resolve()

        stats = index_wiki(real)
        paths = _fts_paths(real / ".index" / "wiki.db")
        # No duplicate/recursive traversal, and the row count matches
        assert len(paths) == len(set(paths))
        assert stats["total_indexed"] == len(paths)

        # lint completes without crashing (rc 0 or 1 depending on how the
        # reachable page set resolves)
        assert lint(str(real)) in (0, 1)


# ══════════════════════════════════════════════════════════════════════════
# Path normalization / separator robustness — CI rounds 6-9
# ══════════════════════════════════════════════════════════════════════════

class TestPathNormalization:
    """Page keys / wikilink targets / FTS paths must be forward-slash spelled
    on every OS. str(Path.relative_to()) yields backslashes on Windows, so each
    consumer applies str(x).replace(os.sep, "/"). These tests build paths with
    os.path.join / Path so they exercise os.sep on every platform."""

    def test_prepare_content_forward_slashes(self, tmp_path):
        root = _clean_wiki(tmp_path / "wiki", content_pages=1)
        f = root / "wiki" / "entities" / "page1.md"
        rel, title, _ = prepare_content(f, root)
        assert rel == "wiki/entities/page1.md"
        assert "\\" not in rel
        assert title == "Page 1"

    def test_index_stores_forward_slash_paths(self, tmp_path):
        root = _clean_wiki(tmp_path / "wiki", content_pages=3)
        index_wiki(root)
        paths = _fts_paths(root / ".index" / "wiki.db")
        assert len(paths) == 4
        assert all("\\" not in p for p in paths)

    def test_incremental_delete_normalizes_native_separators(self, tmp_path):
        """A stale index entry stored with the native-separator absolute path
        must still delete its forward-slash FTS row (71b1e6a round 7)."""
        root = _clean_wiki(tmp_path / "wiki", content_pages=1)
        index_wiki(root)
        db = root / ".index" / "wiki.db"

        # Inject a "previous run" stale entry: native-sep absolute path in
        # index_meta, forward-slash relative path in the FTS row.
        stale_abs = os.path.join(str(root), "wiki", "entities", "ghost.md")
        conn = sqlite3.connect(str(db))
        try:
            conn.execute(
                "INSERT INTO pages (path, title, content) VALUES (?, ?, ?)",
                ("wiki/entities/ghost.md", "Ghost", "ghost"),
            )
            conn.execute(
                "INSERT INTO index_meta (file_path, sha256, indexed_at, file_size) "
                "VALUES (?, 'deadbeef', '2026-01-01T00:00:00', 10)",
                (stale_abs,),
            )
            conn.commit()
        finally:
            conn.close()

        count_before = _count_pages(db)
        stats = index_wiki(root)
        assert stats["files_deleted"] == 1
        assert _count_pages(db) == count_before - 1
        conn = sqlite3.connect(str(db))
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM pages WHERE path = 'wiki/entities/ghost.md'"
            ).fetchone()
        finally:
            conn.close()
        assert row[0] == 0

    def test_load_pages_forward_slash_keys(self, tmp_path):
        """Wikilink page keys use forward slashes — no backslash-in-key bug
        (the validate_fixtures.py fix, 7ca73b0 round 8, applies to
        core/wikilinks too)."""
        root = _clean_wiki(tmp_path / "wiki", content_pages=2)
        pages = load_pages(root / "wiki")
        assert "page1" in pages  # stem key
        assert "entities/page1" in pages  # forward-slash relative-path key
        assert not any("\\" in k for k in pages)  # no backslash keys

    def test_wikilink_resolution_accepts_path_links(self, tmp_path):
        """A wikilink authored as [[entities/page2]] must resolve on every OS."""
        root = _clean_wiki(tmp_path / "wiki", content_pages=2)
        page = root / "wiki" / "entities" / "page1.md"
        text = page.read_text(encoding="utf-8", errors="replace")
        page.write_text(
            text + "See [[entities/page2]] for more.\n", encoding="utf-8"
        )
        assert lint(str(root)) == 0  # the path-style link is NOT dead

    def test_windows_separator_normalization_invariant(self):
        """The exact failure mode the .replace(os.sep, '/') fixes express:
        PureWindowsPath.relative_to() yields backslashes, which must be
        normalized to the forward-slash spelling every consumer stores."""
        root_w = PureWindowsPath("C:/wikis/proj")
        f_w = PureWindowsPath("C:/wikis/proj/wiki/sub/doc.md")
        rel_w = str(f_w.relative_to(root_w))
        assert "\\" in rel_w  # Windows-native relative_to() really is backslash
        assert rel_w.replace("\\", "/") == "wiki/sub/doc.md"


# ══════════════════════════════════════════════════════════════════════════
# CRLF tolerance — Windows line endings (CI rounds 5-7)
# ══════════════════════════════════════════════════════════════════════════

class TestCRLFTolerance:
    """Pages authored with CRLF line endings must parse, lint, and round-trip.
    The canonical frontmatter regex and log checks are line-ending sensitive."""

    def test_crlf_frontmatter_parsed(self):
        content = (
            "---\r\n"
            "title: Cafe\r\n"
            "type: concept\r\n"
            "created: 2026-01-01\r\n"
            "updated: 2026-01-01\r\n"
            "sources: [one, two]\r\n"
            "---\r\n"
            "\r\n"
            "# Cafe\r\n"
            "\r\n"
            "Body text.\r\n"
        )
        fm = parse_frontmatter(content)
        assert fm is not None
        assert fm["title"] == "Cafe"
        assert fm["type"] == "concept"
        assert fm["sources"] == ["one", "two"]

    def test_crlf_title_extraction(self, tmp_path):
        content = (
            "---\r\ntitle: Cafe\r\ntype: concept\r\n---\r\n"
            "\r\n# Cafe\r\n\r\nBody.\r\n"
        )
        assert extract_title(content, tmp_path / "cafe.md") == "Cafe"

    def test_crlf_wiki_pipeline_and_round_trip(self, tmp_path):
        today = datetime.now().strftime("%Y-%m-%d")
        root = _clean_wiki(tmp_path / "wiki", content_pages=2)
        page = root / "wiki" / "entities" / "page1.md"
        crlf_content = (
            "---\r\n"
            "title: CRLF Page\r\n"
            "type: entity\r\n"
            f"created: {today}\r\n"
            f"updated: {today}\r\n"
            "---\r\n"
            "\r\n"
            "# CRLF Page\r\n"
            "\r\n"
            "Written with Windows line endings.\r\n"
        )
        page.write_text(crlf_content, encoding="utf-8", newline="")

        # Round-trip: the bytes on disk keep CRLF and the body intact
        raw = page.read_bytes()
        assert b"\r\n" in raw
        assert b"Written with Windows line endings." in raw
        assert "Written with Windows line endings." in page.read_text(
            encoding="utf-8"
        )

        # Frontmatter + lint + discover all still work
        fm = parse_frontmatter(crlf_content)
        assert fm is not None and fm["title"] == "CRLF Page"
        layout = discover_layout(str(root))
        assert Path(layout.pages_dir) == (root / "wiki").resolve()
        assert lint(str(root)) == 0


# ══════════════════════════════════════════════════════════════════════════
# Non-UTF8 (cp1252 / latin-1) decode — Windows cp1252 fix
# ══════════════════════════════════════════════════════════════════════════

class TestNonUtf8Decode:
    """A page containing cp1252-encodable bytes written as latin-1 must never
    crash discover/index/lint. The codebase guard is
    read_text(encoding="utf-8", errors="replace")."""

    def test_latin1_bytes_survive_discover_index_lint(self, tmp_path):
        today = datetime.now().strftime("%Y-%m-%d")
        root = _clean_wiki(tmp_path / "wiki", content_pages=2)
        # é (0xE9) and cp1252 em-dash (0x97) are both invalid UTF-8 bytes.
        page = root / "wiki" / "entities" / "cafe.md"
        dates = f"created: {today}\nupdated: {today}\n".encode("ascii")
        page.write_bytes(
            b"---\ntitle: Caf\xe9\ntype: entity\n"
            + dates
            + b"---\n\n# Caf\xe9\n\nR\xe9sum\xe9 \x97 details.\n"
        )
        # Give the latin-1 page an inbound link + index entry so lint stays clean
        index = root / "wiki" / "index.md"
        index.write_text(
            index.read_text(encoding="utf-8") + "[[cafe]]\n", encoding="utf-8"
        )

        layout = discover_layout(str(root))
        assert Path(layout.pages_dir) == (root / "wiki").resolve()

        stats = index_wiki(root)
        assert stats["files_indexed"] == 4  # index + 2 pages + cafe

        # Before the lint fix this raised UnicodeDecodeError
        assert lint(str(root)) == 0

        # Round-trip: raw bytes untouched
        assert page.read_bytes().endswith(b"R\xe9sum\xe9 \x97 details.\n")

    def test_cp1252_em_dash_bytes_decoded_with_replacement(self, tmp_path):
        """0x97 is the cp1252 em-dash (U+2014) and is invalid UTF-8 — the exact
        byte a Windows-default-encoded write produces (71b1e6a round 7)."""
        page = tmp_path / "page.md"
        page.write_bytes(b"---\ntitle: a \x97 b\ntype: concept\n---\n\nbody \x97\n")
        text = page.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        assert fm is not None
        assert "\ufffd" in fm["title"]  # replacement char, no crash


# ══════════════════════════════════════════════════════════════════════════
# Atomic writes (os.replace) — CI round 5 (847eb9e)
# ══════════════════════════════════════════════════════════════════════════

class TestAtomicWrite:
    """atomic_write must use os.replace (Windows-safe MoveFileEx-REPLACE
    semantics) and leave no partial files on failure."""

    @staticmethod
    def _boom_replace(src, dst):
        raise OSError("simulated os.replace failure")

    def test_uses_os_replace_not_rename(self, tmp_path, monkeypatch):
        target = tmp_path / "doc.md"
        calls = []
        real_replace = os.replace

        def spy(src, dst):
            calls.append((str(src), str(dst)))
            return real_replace(src, dst)

        monkeypatch.setattr(os, "replace", spy)

        def no_rename(*a, **k):
            raise AssertionError(
                "atomic_write must use os.replace (Windows-safe), not os.rename"
            )

        monkeypatch.setattr(os, "rename", no_rename)

        assert atomic_write(str(target), "hello") is True
        assert target.read_text(encoding="utf-8") == "hello"
        assert len(calls) == 1
        src, dst = calls[0]
        assert dst == str(target)
        # The temp file is staged in the same directory (same filesystem)
        assert ".tmp." in Path(src).name
        assert Path(src).parent == target.parent

    def test_failure_leaves_no_partial_file(self, tmp_path, monkeypatch):
        target = tmp_path / "doc.md"
        monkeypatch.setattr(os, "replace", self._boom_replace)
        assert atomic_write(str(target), "content") is False
        assert not target.exists()
        assert [p.name for p in tmp_path.iterdir() if ".tmp." in p.name] == []

    def test_failure_preserves_existing_target(self, tmp_path, monkeypatch):
        target = tmp_path / "doc.md"
        target.write_text("original", encoding="utf-8")
        monkeypatch.setattr(os, "replace", self._boom_replace)
        assert atomic_write(str(target), "overwritten") is False
        assert target.read_text(encoding="utf-8") == "original"
        assert [p.name for p in tmp_path.iterdir() if ".tmp." in p.name] == []


# ══════════════════════════════════════════════════════════════════════════
# UTF-8 stdout reconfigure — Windows scaffold crash fix (7d97a47, d073a8f)
# ══════════════════════════════════════════════════════════════════════════

class TestUtf8StdoutReconfigure:
    """The ✓/⚠/→ markers used across the CLI must never raise
    UnicodeEncodeError when stdout is forced to an ANSI/ASCII encoding."""

    @staticmethod
    def _ascii_env() -> dict:
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "ascii"
        return env

    def test_import_reconfigures_stdout_to_utf8(self):
        code = (
            "import sys\n"
            "import llm_wiki\n"
            "sys.stdout.write('encoding=' + sys.stdout.encoding + '\\n')\n"
            "sys.stdout.write('\u2713 ok\\n')\n"
            "sys.stderr.write('\u26a0 warn\\n')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            env=self._ascii_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert result.returncode == 0, result.stderr
        assert "encoding=utf-8" in result.stdout
        assert "\u2713 ok" in result.stdout
        assert "UnicodeEncodeError" not in result.stderr

    def test_scaffold_cli_under_ascii_stdout(self, tmp_path):
        """scaffold prints ✓ markers — the original Windows crash (7d97a47)."""
        target = tmp_path / "ascii-wiki"
        script = REPO_ROOT / "skill" / "scripts" / "scaffold.py"
        result = subprocess.run(
            [sys.executable, str(script), str(target), "ASCII Test",
             "--template", "codebase", "--force"],
            env=self._ascii_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert result.returncode == 0, result.stderr
        assert "UnicodeEncodeError" not in result.stderr
        assert "\u2713" in result.stdout
        assert (target / "wiki" / "index.md").exists()

    def test_lint_cli_under_ascii_stdout(self, tmp_path):
        """lint prints ✅/🟡/⚠ markers — the em-dash/arrow crashes (d073a8f)."""
        root = _clean_wiki(tmp_path / "wiki", content_pages=2)
        script = REPO_ROOT / "skill" / "scripts" / "lint_wiki.py"
        result = subprocess.run(
            [sys.executable, str(script), str(root)],
            env=self._ascii_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert result.returncode == 0, result.stderr
        assert "UnicodeEncodeError" not in result.stderr
        assert "\u2705" in result.stdout

    def test_reconfigure_guard_when_forbidden(self, monkeypatch):
        """Embedding environments (e.g. pytest capture) may forbid stdout
        reconfigure — the guard must break out of the loop, not raise."""

        class ForbidsReconfigure:
            def __init__(self):
                self.chunks = []

            def write(self, s):
                self.chunks.append(s)

            def flush(self):
                pass

            def reconfigure(self, **kw):
                raise ValueError("reconfigure forbidden")

        fake = ForbidsReconfigure()
        monkeypatch.setattr(sys, "stdout", fake)
        monkeypatch.setattr(sys, "stderr", fake)
        monkeypatch.setattr(sys, "argv", ["llm-wiki", "--version"])

        from llm_wiki.cli import main

        assert main() == 0
        assert "llm-wiki" in "".join(fake.chunks)


# ── Count ─────────────────────────────────────────────────────────────────
# test_cross_platform_edge.py = symlinked paths (4) + path normalization (6) +
#                               CRLF (3) + non-utf8 (2) + atomic (3) +
#                               utf8 stdout (4) = 22 test functions
