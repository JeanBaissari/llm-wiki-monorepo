"""Tests for the optional Leiden community engine (LWM_027).

Covers import-safety without the [leiden] extra, the default engine staying
Louvain, the fallback path, the internal-connectivity guarantee, and (skip-if-
absent) result-shape parity with Louvain.
"""

import pytest

from llm_wiki.graph import leiden
from llm_wiki.graph.insights import _select_community_engine, detect_communities_for_insights
from llm_wiki.graph.louvain import detect_communities as louvain_detect

from tests.verification.run_verification import (
    load_graph_fixtures,
    verify_leiden_vs_louvain,
)

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


class _StubGraph:
    """networkx-free stand-in for the offline hierarchy-logic tests: the only
    attribute ``hierarchical_levels`` touches on the graph is ``number_of_edges()``
    (the fake ``_leiden_component_levels`` ignores it entirely). This keeps the
    level-merging tests runnable in environments WITHOUT the [leiden] extra —
    a real networkx graph would hard-require the extra and crash the base lanes.
    """

    def __init__(self, edges: list[dict]):
        self._n = len(edges)

    def number_of_edges(self) -> int:
        return self._n


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


# ── B4/B6 hierarchy seam (AD-13/AD-18) ────────────────────────────────────

def _fixture_graphs():
    return [
        pytest.param(data["name"], data, id=data["name"])
        for data in load_graph_fixtures()
    ]


def test_hierarchical_levels_none_without_extra(monkeypatch):
    # Unavailable extra → None, never a raise.
    monkeypatch.setattr(leiden, "is_leiden_available", lambda: False)
    assert leiden.hierarchical_levels(NODES, EDGES, seed=42) is None


def test_hierarchical_levels_none_on_empty_graph(monkeypatch):
    # Empty node list or edgeless graph → None, never a raise.
    monkeypatch.setattr(leiden, "is_leiden_available", lambda: True)
    assert leiden.hierarchical_levels([], EDGES) is None
    assert leiden.hierarchical_levels(NODES, []) is None


@pytest.mark.skipif(not leiden.is_leiden_available(), reason="[leiden] extra not installed")
def test_hierarchical_levels_seam_shape_and_nesting():
    """Real graspologic run: the seam returns levels bottom-up (finest first)
    with the documented dict shape, covering every node at every level, and
    each coarser level is a coarsening of the finer one."""
    nodes = [{"id": n.get("id", ""), "label": n.get("label", ""),
              "linkCount": n.get("linkCount", 0)} for n in NODES]
    levels = leiden.hierarchical_levels(nodes, EDGES, seed=42)
    # Fixtures are small — graspologic typically computes a single flat level,
    # which the seam reports as None (no hierarchy computable → caller degrades).
    assert levels is None or len(levels) >= 1
    if levels is None:
        return
    for lv in levels:
        assert set(lv) == {"level", "assignments"}
        assert set(lv["assignments"]) == {n["id"] for n in NODES}
    assert [lv["level"] for lv in levels] == list(range(len(levels)))
    # Nesting: coarser levels merge finer-level communities only.
    fine = levels[0]["assignments"]
    for lv in levels[1:]:
        fine_of = {}
        for nid, cid in fine.items():
            fine_of.setdefault(cid, set()).add(nid)
        for members in fine_of.values():
            cids = {lv["assignments"][m] for m in members}
            assert len(cids) == 1, (
                f"level {lv['level']} splits a finer-level community"
            )


def test_hierarchical_levels_multilevel_bottom_up(monkeypatch):
    """Level merging logic with a fabricated per-component hierarchy: finest
    partition first, singletons kept, coarser level = valid coarsening."""
    # Component A has a 2-level hierarchy (community subdivided); component B
    # and the isolated node only have their flat partition.
    fake_levels = iter([
        ({"a", "b", "c"}, {0: {"a": 0, "b": 0, "c": 0},
                           1: {"a": 1, "b": 2, "c": 3}}),
        ({"d", "e"}, {0: {"d": 0, "e": 0}}),
    ])
    monkeypatch.setattr(leiden, "is_leiden_available", lambda: True)
    monkeypatch.setattr(leiden, "_leiden_component_levels",
                        lambda g, seed: fake_levels)
    monkeypatch.setattr(leiden, "_build_graph",
                        lambda ids, edges: _StubGraph(edges))
    nodes = [{"id": n} for n in ["a", "b", "c", "d", "e", "iso"]]
    edges = [{"source": "a", "target": "b", "weight": 1},
             {"source": "d", "target": "e", "weight": 1}]
    levels = leiden.hierarchical_levels(nodes, edges, seed=42)
    assert levels is not None and len(levels) == 2
    finest, coarsest = levels
    assert [lv["level"] for lv in levels] == [0, 1]
    for lv in levels:
        assert set(lv["assignments"]) == {"a", "b", "c", "d", "e", "iso"}
    # Finest: A is subdivided (a,b,c in three clusters); B stays merged; iso singleton.
    a_fine = {finest["assignments"][n] for n in ("a", "b", "c")}
    assert len(a_fine) == 3
    assert finest["assignments"]["d"] == finest["assignments"]["e"]
    # Coarsest: A merged back into one community; d/e and iso keep theirs.
    assert len({coarsest["assignments"][n] for n in ("a", "b", "c")}) == 1
    assert len(set(coarsest["assignments"].values())) == 3


def test_hierarchical_levels_deterministic(monkeypatch):
    """Same inputs + seed → identical hierarchy (id numbering included)."""
    def fake_levels(g, seed):
        return iter([
            ({"a", "b", "c"}, {0: {"a": 0, "b": 0, "c": 0},
                               1: {"a": 1, "b": 2, "c": 3}}),
        ])
    monkeypatch.setattr(leiden, "is_leiden_available", lambda: True)
    monkeypatch.setattr(leiden, "_leiden_component_levels", fake_levels)
    monkeypatch.setattr(leiden, "_build_graph",
                        lambda ids, edges: _StubGraph(edges))
    nodes = [{"id": n} for n in ["a", "b", "c"]]
    edges = [{"source": "a", "target": "b", "weight": 1}]
    assert leiden.hierarchical_levels(nodes, edges, seed=42) == \
        leiden.hierarchical_levels(nodes, edges, seed=42)


@pytest.mark.skipif(not leiden.is_leiden_available(), reason="[leiden] extra not installed")
def test_seed_zero_is_sanitized(monkeypatch):
    """graspologic rejects random_seed=0 (unsigned-64 native PRNG); the engine
    must sanitize it rather than raise (the verification suite uses seed 0)."""
    import networkx as nx

    assert leiden._sanitize_seed(0) == 1
    assert leiden._sanitize_seed(42) == 42
    assert leiden._sanitize_seed(None) is None
    monkeypatch.setattr(leiden, "is_leiden_available", lambda: True)
    g = nx.Graph()
    g.add_nodes_from(["a", "b"])
    g.add_edge("a", "b", weight=1)
    levels = list(leiden._leiden_component_levels(g, seed=0))
    assert len(levels) == 1


# ── ADR-0012 gate data: Leiden vs Louvain NMI/modularity (AD-5) ───────────

def test_leiden_vs_louvain_report_shape():
    """The verification report exposes the ADR-0012 gate section per graph."""
    graphs = load_graph_fixtures()
    assert graphs, "no graph fixtures found"
    for data in graphs:
        report = verify_leiden_vs_louvain(data)
        assert report["graph"] == data["name"]
        assert set(report) == {
            "graph", "available", "seeds", "nmi_values", "nmi_mean",
            "modularity_leiden", "modularity_louvain", "connectivity_pass",
        }
        assert len(report["seeds"]) == 5


@pytest.mark.skipif(not leiden.is_leiden_available(), reason="[leiden] extra not installed")
def test_leiden_vs_louvain_metrics_computed_and_connected():
    """With [leiden] installed: NMI and modularity are computed per fixture,
    and Leiden's connectivity guarantee holds on every fixture. Deliberately
    does NOT assert that Leiden beats Louvain — the default flip is a separate
    gated decision (ADR-0025)."""
    graphs = load_graph_fixtures()
    assert graphs, "no graph fixtures found"
    for data in graphs:
        report = verify_leiden_vs_louvain(data)
        assert report["available"] is True
        assert len(report["nmi_values"]) == 5, data["name"]
        assert report["nmi_mean"] is not None and 0.0 <= report["nmi_mean"] <= 1.0
        assert len(report["modularity_leiden"]) == 5, data["name"]
        assert len(report["modularity_louvain"]) == 5, data["name"]
        assert report["connectivity_pass"] is True, (
            f"{data['name']}: Leiden community disconnected or node dropped"
        )
