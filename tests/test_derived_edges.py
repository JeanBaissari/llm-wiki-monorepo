"""Tests for the quarantined derived-edge layer (LWM_029).

Covers the separate-layer persistence, default-exclusion (analytics byte-identical
whether or not the layer exists), co-occurrence generation on the base install,
rel_type tagging + wikilink-duplicate dropping, and the fail-closed NMI/modularity
inclusion gate (positive + negative).
"""

import json

from llm_wiki.graph import derived_edges as de
from llm_wiki.graph.insights import detect_communities_for_insights


def _make_wiki(tmp_path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    # Two pages sharing 2 sources → a co-occurrence edge; they do NOT wikilink.
    (wiki / "rag.md").write_text(
        "---\ntitle: RAG\ntype: concept\nsources: [paper-a, paper-b]\n---\n\n"
        "# RAG\n\nRetrieval augmented generation.\n",
        encoding="utf-8",
    )
    (wiki / "retrieval.md").write_text(
        "---\ntitle: Retrieval\ntype: concept\nsources: [paper-a, paper-b]\n---\n\n"
        "# Retrieval\n\nDense retrieval methods.\n",
        encoding="utf-8",
    )
    # A page that wikilinks to RAG — this edge must stay canonical (not derived).
    (wiki / "notes.md").write_text(
        "---\ntitle: Notes\ntype: note\nsources: [paper-a, paper-b]\n---\n\n"
        "# Notes\n\nSee [[RAG]].\n",
        encoding="utf-8",
    )
    return tmp_path, wiki


def test_generate_writes_separate_layer_only(tmp_path):
    root, _wiki = _make_wiki(tmp_path)
    stats = de.generate_derived_edges(root, min_shared_sources=2)
    # Layer file exists; graph-data.json was never created by this operation.
    assert de.derived_path(root).exists()
    assert not (root / ".index" / "graph-data.json").exists()
    assert stats["co_occurs_with"] >= 1  # rag<->retrieval share 2 sources
    edges = de.load_derived_edges(root)
    assert all(e["layer"] == "derived" for e in edges)
    assert all(e["rel_type"] in (de.REL_SIMILAR, de.REL_COOCCUR) for e in edges)
    assert all(e["directed"] is False for e in edges)


def test_wikilink_duplicates_dropped(tmp_path):
    root, _wiki = _make_wiki(tmp_path)
    de.generate_derived_edges(root, min_shared_sources=2)
    edges = de.load_derived_edges(root)
    # notes<->rag is a real wikilink → must NOT appear as a derived edge.
    keys = {de._undirected_key(e["source"], e["target"]) for e in edges}
    assert de._undirected_key("notes", "rag") not in keys


def test_default_exclusion_analytics_identical(tmp_path):
    root, wiki = _make_wiki(tmp_path)
    nodes = {"rag": {"label": "RAG", "linkCount": 1},
             "retrieval": {"label": "Retrieval", "linkCount": 0},
             "notes": {"label": "Notes", "linkCount": 1}}
    edges = [("notes", "rag")]  # the only wikilink edge

    before = detect_communities_for_insights(nodes, edges)
    de.generate_derived_edges(root, min_shared_sources=2)
    after = detect_communities_for_insights(nodes, edges)
    # The derived layer existing on disk changes nothing for default consumers.
    assert before == after


def test_include_derived_off_by_default(tmp_path):
    root, _wiki = _make_wiki(tmp_path)
    de.generate_derived_edges(root, min_shared_sources=2)
    # No consumer reads the layer unless it explicitly calls load_derived_edges.
    # (Contract: the default insights/community path never imports it.)
    import llm_wiki.graph.insights as insights_mod
    src = insights_mod.__file__
    with open(src, encoding="utf-8") as f:
        assert "derived_edges" not in f.read()  # default path does not import it


def test_gate_allows_when_not_degrading(tmp_path):
    # A derived edge INSIDE an existing community should not degrade modularity.
    nodes = [{"id": n} for n in ["a", "b", "c", "d", "e", "f"]]
    wikilink = [
        {"source": "a", "target": "b", "weight": 1},
        {"source": "b", "target": "c", "weight": 1},
        {"source": "a", "target": "c", "weight": 1},
        {"source": "d", "target": "e", "weight": 1},
        {"source": "e", "target": "f", "weight": 1},
        {"source": "d", "target": "f", "weight": 1},
    ]
    intra = [{"source": "a", "target": "c", "weight": 1, "rel_type": de.REL_SIMILAR,
              "layer": "derived"}]  # within community {a,b,c}
    include, report = de.should_include_derived(nodes, wikilink, intra)
    assert include is True
    assert report["with_derived_modularity"] >= report["baseline_modularity"]


def test_gate_fail_closed_when_degrading(tmp_path):
    # Dense cross-community derived edges collapse the two clusters → refuse.
    nodes = [{"id": n} for n in ["a", "b", "c", "d", "e", "f"]]
    wikilink = [
        {"source": "a", "target": "b", "weight": 1},
        {"source": "b", "target": "c", "weight": 1},
        {"source": "a", "target": "c", "weight": 1},
        {"source": "d", "target": "e", "weight": 1},
        {"source": "e", "target": "f", "weight": 1},
        {"source": "d", "target": "f", "weight": 1},
    ]
    # Flood every cross-community pair — classic community-blobbing case.
    bridging = [{"source": s, "target": t, "weight": 5, "rel_type": de.REL_SIMILAR,
                 "layer": "derived"}
                for s in ["a", "b", "c"] for t in ["d", "e", "f"]]
    include, report = de.should_include_derived(nodes, wikilink, bridging)
    assert include is False
    assert "fail-closed" in report["reason"]


def test_empty_derived_layer_refused(tmp_path):
    include, report = de.should_include_derived([{"id": "a"}], [], [])
    assert include is False
