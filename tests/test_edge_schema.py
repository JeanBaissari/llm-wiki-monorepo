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


def test_bitemporal_fields_roundtrip_as_plain_dict():
    # Edge carriers are plain dicts; bitemporal fields persist untouched.
    e = {"source": "a", "target": "b", "weight": 1,
         "valid_from": "2020-01-01T00:00:00Z", "valid_to": "2021-01-01T00:00:00Z",
         "observed_at": "2026-08-07T00:00:00Z", "directed": True, "relType": "is-a"}
    assert e["valid_from"] == "2020-01-01T00:00:00Z"
    assert e["directed"] is True
    assert e["relType"] == "is-a"
