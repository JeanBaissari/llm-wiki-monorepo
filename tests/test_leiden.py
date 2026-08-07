"""Tests for the optional Leiden community engine (LWM_027).

Covers import-safety without the [leiden] extra, the default engine staying
Louvain, the fallback path, the internal-connectivity guarantee, and (skip-if-
absent) result-shape parity with Louvain.
"""

import pytest

from llm_wiki.graph import leiden
from llm_wiki.graph.insights import _select_community_engine, detect_communities_for_insights
from llm_wiki.graph.louvain import detect_communities as louvain_detect

NODES = [
    {"id": "a", "label": "A", "linkCount": 3},
    {"id": "b", "label": "B", "linkCount": 2},
    {"id": "c", "label": "C", "linkCount": 2},
    {"id": "d", "label": "D", "linkCount": 1},
    {"id": "e", "label": "E", "linkCount": 1},
    {"id": "f", "label": "F", "linkCount": 1},
]
# Two triangles bridged once — a classic two-community topology.
EDGES = [
    {"source": "a", "target": "b", "weight": 1},
    {"source": "b", "target": "c", "weight": 1},
    {"source": "a", "target": "c", "weight": 1},
    {"source": "d", "target": "e", "weight": 1},
    {"source": "e", "target": "f", "weight": 1},
    {"source": "d", "target": "f", "weight": 1},
    {"source": "c", "target": "d", "weight": 1},
]


def test_import_safe_without_extra():
    # Importing + probing must never raise regardless of whether graspologic exists.
    assert isinstance(leiden.is_leiden_available(), bool)


def test_default_engine_is_louvain():
    # No selector / unknown selector → Louvain (byte-identical default).
    assert _select_community_engine() is louvain_detect
    assert _select_community_engine("nope") is louvain_detect


def test_leiden_selector_falls_back_without_extra():
    # Selecting leiden without the extra installed must degrade to Louvain.
    if not leiden.is_leiden_available():
        assert _select_community_engine("leiden") is louvain_detect
    else:
        assert _select_community_engine("leiden") is leiden.detect_communities


def test_insights_default_unchanged_by_selector():
    # The insights community map is identical whether engine is unset or "louvain".
    nodes = {n["id"]: {"label": n["label"], "linkCount": n["linkCount"]} for n in NODES}
    edges = [(e["source"], e["target"]) for e in EDGES]
    a = detect_communities_for_insights(nodes, edges)
    b = detect_communities_for_insights(nodes, edges, engine="louvain")
    assert a == b


def test_induced_connected_helper():
    # {a,b,c} is a connected triangle; {a,d} share no internal edge → disconnected.
    assert leiden._induced_connected({"a", "b", "c"}, EDGES) is True
    assert leiden._induced_connected({"a", "d"}, EDGES) is False
    assert leiden._induced_connected({"a"}, EDGES) is True


@pytest.mark.skipif(not leiden.is_leiden_available(), reason="[leiden] extra not installed")
def test_leiden_shape_matches_louvain_and_is_connected():
    l_assign, l_comms = leiden.detect_communities(NODES, EDGES, seed=42)
    lo_assign, lo_comms = louvain_detect(NODES, EDGES, seed=42)
    # Same keys / community-info shape (not necessarily same partition).
    assert set(l_assign) == set(lo_assign)
    for c in l_comms:
        assert set(c) == {"id", "nodeCount", "cohesion", "topNodes"}
    # Connectivity guarantee holds for every emitted community.
    for c in l_comms:
        members = {nid for nid, cid in l_assign.items() if cid == c["id"]}
        assert leiden._induced_connected(members, EDGES)
