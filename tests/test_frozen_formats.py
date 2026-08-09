"""test_frozen_formats.py — byte-identity freeze of public data artifacts (LWM_025).

LWM_025's "byte-identical" contract: the alias-store schema and the quarantined
derived-edge layer are strictly additive — they must never change the shape of
(a) FTS5 keyword-search results or (b) ``graph-data.json``. These tests freeze
BOTH contracts as committed golden snapshots generated from the CURRENT code
(``tests/fixtures/gold/``):

  * ``keyword-search.golden.json`` — the exact output of ``keyword_search()`` on
    the committed ``populated`` fixture wiki (index rebuilt from the pages).
  * ``graph-data.json.golden`` — the exact ``graph-engine`` build output on the
    same fixture wiki.

A future change that adds/removes/renames a field, reorders ranking, or alters
snippet/title derivation FAILS these tests until the contract is intentionally
bumped (regenerate the goldens AND update the frozen field-set constants in the
same commit). This mirrors the graph-engine's own
``graph-engine/test/test_edge_schema.test.ts`` live build-through golden.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLD_DIR = REPO_ROOT / "tests" / "fixtures" / "gold"
KEYWORD_GOLDEN = GOLD_DIR / "keyword-search.golden.json"
GRAPH_DATA_GOLDEN = GOLD_DIR / "graph-data.golden.json"
POPULATED = REPO_ROOT / "tests" / "fixtures" / "wikis" / "populated"

# ── The frozen contracts ──────────────────────────────────────────────────

KW_QUERY = "transformer attention"
KW_K = 3

# (a) Keyword-search result fields — frozen field set, nothing else allowed.
KEYWORD_FIELDS = {"path", "title", "snippet", "score"}

# (b) graph-data.json — frozen field sets at every level.
GRAPH_TOP_LEVEL_FIELDS = {"nodes", "edges", "communities"}
GRAPH_NODE_FIELDS = {"id", "label", "path", "type", "sources", "linkCount", "community"}
GRAPH_EDGE_FIELDS = {"source", "target", "weight"}
GRAPH_COMMUNITY_FIELDS = {"id", "nodeCount", "cohesion", "topNodes"}

GRAPH_ENGINE_CLI = REPO_ROOT / "graph-engine" / "dist" / "index.js"


def _copy_populated(tmp_path: Path) -> Path:
    dest = tmp_path / "wiki"
    shutil.copytree(POPULATED, dest)
    return dest


def _fresh_keyword_results(wiki_root: Path) -> dict:
    from llm_wiki.search.index import index_wiki
    from llm_wiki.search.query import keyword_search

    index_wiki(wiki_root, rebuild=True)
    return {
        "query": KW_QUERY,
        "k": KW_K,
        "results": keyword_search(wiki_root, KW_QUERY, k=KW_K),
        "untokenizable_query_results": keyword_search(wiki_root, "!!!", k=KW_K),
    }


# ── (a) FTS5 keyword-search byte-identity ─────────────────────────────────


def test_keyword_search_output_shape_frozen(tmp_path):
    """FTS5 keyword results expose EXACTLY {path, title, snippet, score}."""
    wiki_root = _copy_populated(tmp_path)
    fresh = _fresh_keyword_results(wiki_root)

    for r in fresh["results"]:
        assert set(r) == KEYWORD_FIELDS, (
            f"search result fields changed: {sorted(r)} != "
            f"{sorted(KEYWORD_FIELDS)} — freeze contract (LWM_025)")
        assert isinstance(r["path"], str) and r["path"].startswith("wiki/")
        assert isinstance(r["title"], str) and r["title"]
        assert isinstance(r["snippet"], str)
        assert isinstance(r["score"], float)

    # Untokenizable query → empty list (byte-identical fallback shape).
    assert fresh["untokenizable_query_results"] == []


def test_keyword_search_golden_byte_identical(tmp_path):
    """Fresh index + search on the committed fixture == committed golden."""
    wiki_root = _copy_populated(tmp_path)
    fresh = _fresh_keyword_results(wiki_root)
    assert fresh == json.loads(KEYWORD_GOLDEN.read_text(encoding="utf-8")), (
        "keyword-search output drifted from the frozen golden — regenerate "
        "tests/fixtures/gold/keyword-search.golden.json only with an intentional "
        "contract bump (LWM_025 byte-identical claim)")


def test_keyword_search_golden_fields_are_the_frozen_set():
    """The golden itself must not silently grow new fields."""
    data = json.loads(KEYWORD_GOLDEN.read_text(encoding="utf-8"))
    assert set(data) == {"query", "k", "results", "untokenizable_query_results"}
    for r in data["results"]:
        assert set(r) == KEYWORD_FIELDS


# ── (b) graph-data.json shape byte-identity ───────────────────────────────


def _load_graph_golden() -> dict:
    return json.loads(GRAPH_DATA_GOLDEN.read_text(encoding="utf-8"))


def test_graph_data_top_level_shape_frozen():
    g = _load_graph_golden()
    assert set(g) == GRAPH_TOP_LEVEL_FIELDS, (
        f"graph-data.json top-level fields changed: {sorted(g)} != "
        f"{sorted(GRAPH_TOP_LEVEL_FIELDS)} — freeze contract (LWM_025)")
    assert isinstance(g["nodes"], list) and g["nodes"]
    assert isinstance(g["edges"], list) and g["edges"]
    assert isinstance(g["communities"], list) and g["communities"]


def test_graph_data_node_field_set_frozen():
    g = _load_graph_golden()
    for n in g["nodes"]:
        assert set(n) == GRAPH_NODE_FIELDS, (
            f"graph-data.json node fields changed: {sorted(n)} != "
            f"{sorted(GRAPH_NODE_FIELDS)} — freeze contract (LWM_025)")
        assert isinstance(n["id"], str)
        assert isinstance(n["label"], str)
        assert isinstance(n["linkCount"], int)
        assert isinstance(n["community"], int)


def test_graph_data_edge_field_set_frozen():
    g = _load_graph_golden()
    for e in g["edges"]:
        assert set(e) == GRAPH_EDGE_FIELDS, (
            f"graph-data.json edge fields changed: {sorted(e)} != "
            f"{sorted(GRAPH_EDGE_FIELDS)} — freeze contract (LWM_025)")
        assert isinstance(e["source"], str)
        assert isinstance(e["target"], str)
        assert isinstance(e["weight"], (int, float))


def test_graph_data_community_field_set_frozen():
    g = _load_graph_golden()
    for c in g["communities"]:
        assert set(c) == GRAPH_COMMUNITY_FIELDS, (
            f"graph-data.json community fields changed: {sorted(c)} != "
            f"{sorted(GRAPH_COMMUNITY_FIELDS)} — freeze contract (LWM_025)")
        assert isinstance(c["id"], int)
        assert isinstance(c["nodeCount"], int)
        assert isinstance(c["cohesion"], (int, float))
        assert isinstance(c["topNodes"], list)


def test_graph_data_golden_invariants():
    """Structural invariants: edges/communities reference real node ids."""
    g = _load_graph_golden()
    node_ids = {n["id"] for n in g["nodes"]}
    node_labels = {n["label"] for n in g["nodes"]}
    assert len(node_ids) == len(g["nodes"])  # ids unique
    for e in g["edges"]:
        assert e["source"] in node_ids, f"edge source {e['source']} not a node"
        assert e["target"] in node_ids, f"edge target {e['target']} not a node"
    for c in g["communities"]:
        for t in c["topNodes"]:
            assert t in node_ids or t in node_labels, (
                f"topNodes entry {t!r} is neither a node id nor a node label")


@pytest.mark.skipif(
    not GRAPH_ENGINE_CLI.exists() or shutil.which("node") is None,
    reason="graph-engine dist not built (run: cd graph-engine && npx tsc)",
)
def test_graph_data_live_build_byte_identical(tmp_path):
    """A fresh graph-engine build of the fixture wiki == committed golden.

    Mirrors graph-engine/test/test_edge_schema.test.ts on the Python side: the
    golden was generated by this exact CLI invocation, so any change to the
    build pipeline that alters graph-data.json fails here (when dist exists).
    """
    wiki_root = _copy_populated(tmp_path)
    result = subprocess.run(
        [shutil.which("node"), str(GRAPH_ENGINE_CLI), "--wiki", str(wiki_root),
         "--action", "build"],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr[-500:]
    fresh = json.loads((wiki_root / "graph-data.json").read_text(encoding="utf-8"))
    assert fresh == _load_graph_golden(), (
        "fresh graph-engine build drifted from the frozen golden — regenerate "
        "tests/fixtures/gold/graph-data.golden.json only with an intentional "
        "contract bump (LWM_025 byte-identical claim)")
