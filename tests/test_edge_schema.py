"""Tests for the additive edge schema on the Python side (LWM_028).

The Python community engine treats edges as ``dict[str, Any]`` and must accept +
ignore the new optional fields (relType/directed/valid_from/valid_to/observed_at)
on the undirected default path, leaving the community partition unchanged.
"""

from llm_wiki.graph.louvain import detect_communities

NODES = [
    {"id": "a", "label": "A", "linkCount": 2},
    {"id": "b", "label": "B", "linkCount": 2},
    {"id": "c", "label": "C", "linkCount": 2},
    {"id": "d", "label": "D", "linkCount": 1},
]
PLAIN_EDGES = [
    {"source": "a", "target": "b", "weight": 1},
    {"source": "b", "target": "c", "weight": 1},
    {"source": "a", "target": "c", "weight": 1},
    {"source": "c", "target": "d", "weight": 1},
]
# Same topology, but every edge also carries the new optional fields.
ANNOTATED_EDGES = [
    {**e, "relType": "cites", "directed": False,
     "valid_from": "2020-01-01T00:00:00Z", "observed_at": "2026-08-07T00:00:00Z"}
    for e in PLAIN_EDGES
]
# The FULL additive schema: directed opt-in + all bitemporal fields.
FULL_ANNOTATED_EDGES = [
    {**e, "relType": "is-a", "directed": True,
     "valid_from": "2020-01-01T00:00:00Z", "valid_to": "2021-01-01T00:00:00Z",
     "observed_at": "2026-08-07T00:00:00Z"}
    for e in PLAIN_EDGES
]


def test_optional_fields_default_absent_and_partition_stable():
    plain_assign, plain_comms = detect_communities(NODES, PLAIN_EDGES, seed=42)
    ann_assign, ann_comms = detect_communities(NODES, ANNOTATED_EDGES, seed=42)
    # The extra fields are inert on the undirected default: identical partition.
    assert plain_assign == ann_assign
    assert plain_comms == ann_comms


def test_legacy_edge_still_works():
    # A bare {source,target,weight} edge remains fully valid.
    assign, comms = detect_communities(NODES, PLAIN_EDGES, seed=42)
    assert set(assign) == {"a", "b", "c", "d"}
    for c in comms:
        assert set(c) == {"id", "nodeCount", "cohesion", "topNodes"}


def test_full_additive_fields_are_inert_with_partition_stability():
    # Edges carrying the FULL additive schema (relType + directed + the
    # valid_from/valid_to/observed_at bitemporal trio) are accepted by the
    # community engine and leave the undirected default partition unchanged.
    plain_assign, plain_comms = detect_communities(NODES, PLAIN_EDGES, seed=42)
    full_assign, full_comms = detect_communities(NODES, FULL_ANNOTATED_EDGES, seed=42)
    assert plain_assign == full_assign
    assert plain_comms == full_comms
    # The carriers survive untouched — no field coercion, no dropping.
    for e in FULL_ANNOTATED_EDGES:
        assert e["directed"] is True and e["relType"] == "is-a"
        assert e["valid_from"] == "2020-01-01T00:00:00Z"
        assert e["valid_to"] == "2021-01-01T00:00:00Z"
        assert e["observed_at"] == "2026-08-07T00:00:00Z"
