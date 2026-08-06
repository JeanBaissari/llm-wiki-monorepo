"""LWM_024: `llm-wiki insights` uses the canonical Louvain engine.

Proves the legacy label-propagation path is gone and insights community
assignments match graph.louvain.detect_communities (the same engine the
TypeScript graph-engine mirrors), so the two engines no longer diverge.
"""

import warnings
from pathlib import Path

import pytest

import llm_wiki.graph.insights as ins
from llm_wiki.graph.insights import compute_insights, detect_communities_for_insights
from llm_wiki.graph.louvain import detect_communities


def test_label_propagation_function_removed():
    # The old greedy label-propagation `communities()` must be gone.
    assert not hasattr(ins, "communities")


def test_insights_assignments_match_canonical_louvain():
    # Two disjoint triangles → two communities under Louvain.
    nodes = {
        f"n{i}": {"id": f"n{i}", "label": f"N{i}", "type": "concept",
                  "path": f"n{i}.md", "linkCount": 2}
        for i in range(6)
    }
    edges = [
        ("n0", "n1"), ("n1", "n2"), ("n0", "n2"),
        ("n3", "n4"), ("n4", "n5"), ("n3", "n5"),
    ]
    comm = detect_communities_for_insights(nodes, edges)

    node_list = [{"id": k, "label": v["label"], "linkCount": v["linkCount"]}
                 for k, v in nodes.items()]
    edge_list = [{"source": s, "target": t, "weight": 1} for s, t in edges]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        canonical, _ = detect_communities(node_list, edge_list, seed=42)

    assert comm == canonical                 # insights == canonical Louvain
    assert len(set(comm.values())) == 2      # two triangles → two communities
    # the two triangles are separated
    assert comm["n0"] == comm["n1"] == comm["n2"]
    assert comm["n3"] == comm["n4"] == comm["n5"]
    assert comm["n0"] != comm["n3"]


def test_isolated_nodes_get_an_assignment():
    nodes = {
        "a": {"id": "a", "label": "A", "type": "concept", "path": "a.md", "linkCount": 0},
        "b": {"id": "b", "label": "B", "type": "concept", "path": "b.md", "linkCount": 0},
    }
    comm = detect_communities_for_insights(nodes, [])  # no edges
    assert set(comm) == {"a", "b"}


def test_compute_insights_runs_on_fixture():
    fixture = Path("tests/fixtures/wikis/populated")
    if not fixture.is_dir():
        pytest.skip("populated fixture not present")
    res = compute_insights(str(fixture), fmt="json")
    assert res["summary"]["communityCount"] >= 1
    assert isinstance(res["surprisingConnections"], list)
