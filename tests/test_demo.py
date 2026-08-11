"""test_demo.py — Tests for `llm-wiki demo` (LWM_036).

Verification contract (from LWM_036):
  (a) the committed fixture itself is lint-clean;
  (b) materializing to a tmp dest produces a wiki that passes all 15 lint checks;
  (c) discover_layout(dest) detects the canonical layout (pages_dir = <dest>/wiki);
  (d) keyword search on the dest returns hits (llm_wiki.search path);
  (e) byte-identity of the copied content vs the fixture except regenerated
      caches (FTS index db + graph-data.json);
  (f) no symlinks in the copy (git-copy semantics);
  (g) refusal without --force on a non-empty target, success with --force;
  (h) graph-build skip-hint when the graph-engine dist is absent (mocked).

All tests are hermetic (tmp dirs only; no node, no [semantic] extra).
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

import llm_wiki.wiki.demo as demo
from llm_wiki.core.layout import discover_layout
from llm_wiki.quality.lint import lint
from llm_wiki.search.query import keyword_search

FIXTURE = REPO_ROOT / "src" / "llm_wiki" / "wiki" / "demo_wiki"

# Paths regenerated at materialize time — excluded from byte-identity checks.
CACHE_RELPATHS = {".index"}
GRAPH_ARTIFACT = "graph-data.json"


def _relpath_set(root: Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}


class TestDemoFixture:
    """The committed fixture is a valid, clean wiki."""

    def test_fixture_lint_clean(self):
        """(a) All 15 lint checks pass on the committed fixture itself."""
        assert lint(str(FIXTURE)) == 0

    def test_fixture_page_inventory(self):
        """The fixture carries 8 content pages across 3 page dirs + index."""
        pages = sorted(FIXTURE.glob("wiki/*/*.md"))
        assert len(pages) == 8
        dirs = {p.parent.name for p in pages}
        assert {"entities", "concepts", "summaries"} <= dirs
        assert (FIXTURE / "wiki" / "index.md").exists()
        assert (FIXTURE / "PURPOSE.md").exists()
        assert (FIXTURE / "CLAUDE.md").exists()
        assert (FIXTURE / "log").is_dir()
        assert (FIXTURE / "raw").is_dir()
        assert (FIXTURE / "audit").is_dir()
        assert (FIXTURE / ".schema_version").exists()


class TestDemoMaterialize:
    """Materializing the demo produces a working, byte-faithful wiki."""

    def test_materialize_and_lint_passes(self, tmp_path):
        """(b) A materialized copy passes all 15 lint checks."""
        dest = tmp_path / "demo"
        rc = demo.run([str(dest)])
        assert rc == 0
        assert lint(str(dest)) == 0

    def test_discover_canonical(self, tmp_path):
        """(c) discover_layout detects the canonical layout on the copy."""
        dest = tmp_path / "demo"
        assert demo.run([str(dest)]) == 0
        layout = discover_layout(str(dest))
        assert Path(layout.pages_dir) == dest / "wiki"
        assert layout.raw_dir is not None
        assert layout.log_dir is not None
        assert layout.audit_dir is not None
        assert layout.index_file is not None
        assert layout.confidence >= 0.85

    def test_search_hits(self, tmp_path):
        """(d) Keyword search on the dest returns >=1 hit."""
        dest = tmp_path / "demo"
        assert demo.run([str(dest)]) == 0
        results = keyword_search(str(dest), "event loop")
        assert results, "keyword search should return hits on the demo wiki"
        assert any("event-loop" in r["path"] for r in results)

    def test_copy_byte_identical(self, tmp_path):
        """(e) Copied content is byte-identical except regenerated caches."""
        dest = tmp_path / "demo"
        assert demo.run([str(dest)]) == 0

        fixture_files = _relpath_set(FIXTURE)
        dest_files = _relpath_set(dest)

        for rel in fixture_files:
            assert rel in dest_files, f"missing copied file: {rel}"
            assert (FIXTURE / rel).read_bytes() == (dest / rel).read_bytes(), \
                f"content differs: {rel}"

        cache_ok = CACHE_RELPATHS | {GRAPH_ARTIFACT}
        for rel in dest_files:
            top = rel.split("/", 1)[0]
            assert top in cache_ok or rel in fixture_files, \
                f"unexpected extra file in copy: {rel}"

    def test_no_symlinks(self, tmp_path):
        """(f) The materialized copy contains no symlinks."""
        dest = tmp_path / "demo"
        assert demo.run([str(dest)]) == 0
        symlinks = [p for p in dest.rglob("*") if p.is_symlink()]
        assert symlinks == []

    def test_force_overwrite(self, tmp_path):
        """(g) Non-empty dest is refused without --force; --force replaces."""
        dest = tmp_path / "demo"
        dest.mkdir()
        sentinel = dest / "keep.txt"
        sentinel.write_text("sentinel", encoding="utf-8")

        rc = demo.run([str(dest)])
        assert rc == 1
        assert sentinel.exists(), "refusal must not touch the existing target"
        assert not (dest / "wiki").exists()

        rc = demo.run([str(dest), "--force"])
        assert rc == 0
        assert (dest / "wiki" / "index.md").exists()
        assert not sentinel.exists(), "--force must replace the target"

    def test_graph_skip_hint_without_dist(self, tmp_path, monkeypatch, capsys):
        """(h) When graph-engine dist is absent, print a hint and keep going."""
        monkeypatch.setattr(demo, "_graph_engine_js", lambda: None)
        dest = tmp_path / "demo"
        rc = demo.run([str(dest)])
        captured = capsys.readouterr()
        assert rc == 0
        assert "Graph build skipped" in captured.out + captured.err

    def test_graph_skip_hint_when_node_missing(self, tmp_path, monkeypatch, capsys):
        """Dist present but node unavailable must degrade, not crash."""
        monkeypatch.setattr(demo, "_graph_engine_js",
                            lambda: Path("/nonexistent/graph-engine/dist/index.js"))
        monkeypatch.setattr(demo.subprocess, "run",
                            lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("node")))
        dest = tmp_path / "demo"
        rc = demo.run([str(dest)])
        captured = capsys.readouterr()
        assert rc == 0
        assert "node unavailable" in captured.out + captured.err

    def test_json_output(self, tmp_path, monkeypatch, capsys):
        """--json prints dest + page count as JSON and suppresses prose."""
        monkeypatch.setattr(demo, "_graph_engine_js", lambda: None)
        dest = tmp_path / "demo"
        assert demo.run([str(dest), "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["dest"] == str(dest)
        assert payload["page_count"] == 9
        assert payload["graph"] == "skipped"

    def test_usage_error_returns_2(self):
        """Missing dest is a usage error (exit 2)."""
        assert demo.run([]) == 2
