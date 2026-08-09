"""AD-5: every community's induced subgraph is internally connected.

Runs over ALL ``tests/fixtures/graphs/*.json`` topologies:

- Louvain (the default engine): the connectivity assertion is the baseline and
  is never skip-gated — it must hold on every fixture.
- Leiden (skip-gated on the ``[leiden]`` extra): the connectivity guarantee it
  advertises (ADR-0025) must hold on every fixture too.

Also asserts that no node is dropped from the partition (AD-18 regression —
degree-0 nodes and multi-component graphs must not silently disappear).
"""

import json
import os

import pytest

from llm_wiki.graph import leiden
from llm_wiki.graph.louvain import detect_communities as louvain_detect

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "graphs")

# Same seed set as the LWM_08B verification suite.
SEEDS = [42, 123, 456, 789, 0]


def _load_fixtures() -> list[pytest.param]:
    params = []
    for fname in sorted(os.listdir(FIXTURES_DIR)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(FIXTURES_DIR, fname)) as f:
            data = json.load(f)
        params.append(pytest.param(data["name"], data, id=data["name"]))
    return params


def _nodes_from_ids(node_ids: list[str]) -> list[dict]:
    return [{"id": nid, "label": nid, "linkCount": 0} for nid in node_ids]


def _assert_connected_and_complete(name, graph, assignments, communities):
    """Assert no dropped nodes and every community's induced subgraph connected."""
    assert set(assignments) == set(graph["nodes"]), (
        f"{name}: nodes dropped from partition "
        f"({sorted(set(graph['nodes']) - set(assignments))})"
    )
    for c in communities:
        members = {nid for nid, cid in assignments.items() if cid == c["id"]}
        assert leiden._induced_connected(members, graph["edges"]), (
            f"{name}: community {c['id']} ({len(members)} nodes) is internally "
            f"disconnected"
        )


@pytest.mark.parametrize("name,graph", _load_fixtures())
def test_louvain_communities_internally_connected(name, graph):
    """Baseline: Louvain partitions must be connected on every fixture topology."""
    nodes = _nodes_from_ids(graph["nodes"])
    for seed in SEEDS:
        assignments, communities = louvain_detect(nodes, graph["edges"], seed=seed)
        _assert_connected_and_complete(name, graph, assignments, communities)


@pytest.mark.parametrize("name,graph", _load_fixtures())
@pytest.mark.skipif(
    not leiden.is_leiden_available(), reason="[leiden] extra not installed"
)
def test_leiden_communities_internally_connected(name, graph):
    """Leiden's connectivity guarantee holds on every fixture topology."""
    nodes = _nodes_from_ids(graph["nodes"])
    for seed in SEEDS:
        assignments, communities = leiden.detect_communities(
            nodes, graph["edges"], seed=seed
        )
        _assert_connected_and_complete(name, graph, assignments, communities)


def test_multicomponent_graph_with_degree_zero_nodes():
    """AD-18 regression: two edge-bearing components + degree-0 nodes.

    Passing the whole graph to ``hierarchical_leiden`` drops isolate nodes
    (graspologic warns and omits them); the per-component split must assign
    every node, keep communities connected, and be deterministic.
    """
    nodes = [
        {"id": f"n{i}", "label": f"n{i}", "linkCount": 0} for i in range(9)
    ]
    edges = (
        [{"source": f"n{i}", "target": f"n{i+1}", "weight": 1} for i in (0, 1, 2)]
        + [{"source": f"n{i}", "target": f"n{i+1}", "weight": 1} for i in (4, 5, 6)]
    )
    if not leiden.is_leiden_available():
        pytest.skip("[leiden] extra not installed")
    assignments, communities = leiden.detect_communities(nodes, edges, seed=42)
    _assert_connected_and_complete("multi-component", {"nodes": [n["id"] for n in nodes], "edges": edges}, assignments, communities)
    assert len(communities) == 5  # two 2-cliques + three singletons
    repeat, _ = leiden.detect_communities(nodes, edges, seed=42)
    assert repeat == assignments  # deterministic
