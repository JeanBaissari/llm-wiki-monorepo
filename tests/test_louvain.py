"""test_louvain.py — Unit tests for the Python Louvain community detection.

Requirements:
- Two-clique graph → two communities
- Star graph → one community
- Empty graph → each node its own community
- Deterministic output with seed=42
- Modularity score matches expected range
- _renumber_size_descending assigns community 0 to largest cluster
- _compute_modularity returns float in [-0.5, 1.0]
- NMI > 0.95 AND ARI > 0.95 between Python and TS on planted graphs
"""

import sys
from collections import defaultdict

# conftest.py adds src to sys.path, so louvain is importable
from llm_wiki.graph.louvain import (
    detect_communities,
    louvain,
    _renumber_size_descending,
    _compute_modularity,
    compute_cohesion,
    build_top_nodes,
)


# ── Helper ─────────────────────────────────────────────────────────────────


def _build_adjacency(nodes, edges):
    """Build undirected adjacency dict from nodes+edges."""
    adj = {n["id"]: set() for n in nodes}
    for e in edges:
        s, t = e["source"], e["target"]
        adj[s].add(t)
        adj[t].add(s)
    return adj


# ── Test Cases ─────────────────────────────────────────────────────────────


def test_empty_graph():
    """Empty graph returns empty assignments and communities."""
    assignments, communities = detect_communities([], [])
    assert assignments == {}
    assert communities == []


def test_single_node():
    """Single isolated node → one community with one node."""
    nodes = [{"id": "a", "label": "A", "linkCount": 0}]
    assignments, communities = detect_communities(nodes, [])
    assert len(assignments) == 1
    assert assignments["a"] == 0
    assert len(communities) == 1
    assert communities[0]["nodeCount"] == 1
    assert communities[0]["cohesion"] == 0.0


def test_two_cliques():
    """Two fully connected cliques with a weak bridge → two communities."""
    nodes = [
        {"id": "a", "label": "A", "linkCount": 2},
        {"id": "b", "label": "B", "linkCount": 2},
        {"id": "c", "label": "C", "linkCount": 3},
        {"id": "d", "label": "D", "linkCount": 3},
        {"id": "e", "label": "E", "linkCount": 2},
        {"id": "f", "label": "F", "linkCount": 2},
    ]
    edges = [
        {"source": "a", "target": "b", "weight": 10},
        {"source": "b", "target": "c", "weight": 10},
        {"source": "a", "target": "c", "weight": 8},
        {"source": "d", "target": "e", "weight": 10},
        {"source": "e", "target": "f", "weight": 10},
        {"source": "d", "target": "f", "weight": 8},
        {"source": "c", "target": "d", "weight": 1},
    ]
    assignments, communities = detect_communities(nodes, edges, seed=42)

    # Two communities
    assert len(communities) == 2, f"Expected 2 communities, got {len(communities)}"
    assert communities[0]["nodeCount"] == 3
    assert communities[1]["nodeCount"] == 3

    # Correct membership: a,b,c together; d,e,f together
    assert assignments["a"] == assignments["b"] == assignments["c"]
    assert assignments["d"] == assignments["e"] == assignments["f"]
    assert assignments["a"] != assignments["d"]

    # Cohesion = 1.0 for fully connected 3-node cliques
    assert communities[0]["cohesion"] == 1.0
    assert communities[1]["cohesion"] == 1.0


def test_star_graph():
    """Star graph — center connected to all leaves — tends to merge into one."""
    nodes = [
        {"id": f"n{i}", "label": f"N{i}", "linkCount": 1 if i > 0 else 5}
        for i in range(6)
    ]
    edges = [
        {"source": "n0", "target": f"n{i}", "weight": 1}
        for i in range(1, 6)
    ]
    assignments, communities = detect_communities(nodes, edges, seed=42)

    # Star has no clear community structure; should produce ≥1 community
    total_nodes = sum(c["nodeCount"] for c in communities)
    assert total_nodes == 6, f"Expected 6 nodes total, got {total_nodes}"
    # should not produce 6 singleton communities (star merges at least center+leaves)
    assert len(communities) < 6, f"Star should merge, got {len(communities)} communities"


def test_deterministic_output():
    """Same seed produces identical output on repeated runs."""
    nodes = [
        {"id": "a", "label": "A", "linkCount": 2},
        {"id": "b", "label": "B", "linkCount": 2},
        {"id": "c", "label": "C", "linkCount": 2},
    ]
    edges = [
        {"source": "a", "target": "b", "weight": 1},
        {"source": "b", "target": "c", "weight": 1},
    ]

    assign1, _ = detect_communities(nodes, edges, seed=42)
    assign2, _ = detect_communities(nodes, edges, seed=42)
    assign3, _ = detect_communities(nodes, edges, seed=42)

    assert assign1 == assign2 == assign3, "Deterministic seed should produce identical results"


def test_different_seeds_may_differ():
    """Different seeds may produce different assignments (stochastic algorithm).

    Uses a 8-node two-clique graph where modularity clearly benefits
    from merging — small graphs (n < 5) have null-model penalty that
    can dominate, making singletons optimal even for full cliques.
    """
    # Two cliques of 4, connected by a single weak edge
    nodes = [
        {"id": f"a{i}", "label": f"A{i}", "linkCount": 4}
        for i in range(4)
    ] + [
        {"id": f"b{i}", "label": f"B{i}", "linkCount": 4}
        for i in range(4)
    ]
    edges = []
    for i in range(4):
        for j in range(i + 1, 4):
            edges.append({"source": f"a{i}", "target": f"a{j}", "weight": 10})
            edges.append({"source": f"b{i}", "target": f"b{j}", "weight": 10})
    edges.append({"source": "a0", "target": "b0", "weight": 1})  # weak bridge

    assign_seed42, communities42 = detect_communities(nodes, edges, seed=42)
    assign_seed99, communities99 = detect_communities(nodes, edges, seed=99)

    # Both seeds should produce sensible 2-community structure
    assert len(communities42) == 2, f"seed=42: expected 2 communities, got {len(communities42)}"
    assert len(communities99) == 2, f"seed=99: expected 2 communities, got {len(communities99)}"

    # Assignments may differ between seeds (stochastic), but both are valid
    # seed-independent: each community has exactly 4 nodes
    assert communities42[0]["nodeCount"] == 4
    assert communities42[1]["nodeCount"] == 4
    assert communities99[0]["nodeCount"] == 4
    assert communities99[1]["nodeCount"] == 4


def test_four_disconnected_cliques():
    """Four completely separate cliques → four communities."""
    nodes = [
        {"id": f"n{i}", "label": f"N{i}", "linkCount": 2}
        for i in range(12)
    ]
    edges = []
    for clique in range(4):
        base = clique * 3
        for i in range(3):
            for j in range(i + 1, 3):
                edges.append({"source": f"n{base + i}", "target": f"n{base + j}", "weight": 10})

    assignments, communities = detect_communities(nodes, edges, seed=42)
    assert len(communities) == 4, f"Expected 4 communities, got {len(communities)}"
    total = sum(c["nodeCount"] for c in communities)
    assert total == 12


# ── _renumber_size_descending ──────────────────────────────────────────────


def test_renumber_size_descending():
    """Largest community gets ID 0."""
    raw = {"a": 5, "b": 5, "c": 5, "d": 2, "e": 2}
    renumbered = _renumber_size_descending(raw)
    # Community with 3 members → ID 0, community with 2 members → ID 1
    assert renumbered["a"] == 0
    assert renumbered["b"] == 0
    assert renumbered["c"] == 0
    assert renumbered["d"] == 1
    assert renumbered["e"] == 1


def test_renumber_tiebreaker():
    """Ties broken by original community ID (lower old ID gets lower new ID)."""
    raw = {"a": 10, "b": 10, "c": 5, "d": 5}
    renumbered = _renumber_size_descending(raw)
    # Both community 10 and 5 have size 2; 5 is lower old ID → gets new ID 0
    assert renumbered["c"] == 0, f"Community 5 should get new ID 0, got {renumbered}"
    assert renumbered["d"] == 0
    assert renumbered["a"] == 1
    assert renumbered["b"] == 1


# ── _compute_modularity ────────────────────────────────────────────────────


def test_modularity_empty():
    """Empty graph → 0.0."""
    assert _compute_modularity({}, {}) == 0.0


def test_modularity_perfect_partition():
    """Perfect partition on two cliques → positive modularity."""
    adjacency = {
        "a": {"b", "c"},
        "b": {"a", "c"},
        "c": {"a", "b"},
        "d": {"e", "f"},
        "e": {"d", "f"},
        "f": {"d", "e"},
    }
    assignments = {"a": 0, "b": 0, "c": 0, "d": 1, "e": 1, "f": 1}
    Q = _compute_modularity(adjacency, assignments)
    # Perfect 2-clique partition should give positive modularity
    assert 0.0 < Q < 1.0, f"Expected modularity in (0,1), got {Q}"


def test_modularity_in_range():
    """Modularity always returns a float in [-0.5, 1.0]."""
    # Single community (all in one)
    adjacency = {
        "a": {"b", "c"},
        "b": {"a", "c"},
        "c": {"a", "b"},
    }
    Q_single = _compute_modularity(adjacency, {"a": 0, "b": 0, "c": 0})
    assert -0.5 <= Q_single <= 1.0

    # All singletons (each node its own community)
    Q_all = _compute_modularity(adjacency, {"a": 0, "b": 1, "c": 2})
    assert -0.5 <= Q_all <= 1.0


# ── build_top_nodes / compute_cohesion ─────────────────────────────────────


def test_build_top_nodes():
    """Top nodes sorted by linkCount descending within a community."""
    nodes = [
        {"id": "a", "label": "A", "linkCount": 10},
        {"id": "b", "label": "B", "linkCount": 5},
        {"id": "c", "label": "C", "linkCount": 20},
    ]
    assignments = {"a": 0, "b": 0, "c": 1}
    # Community 0: A (10), B (5) — sorted descending → A, B
    top = build_top_nodes(nodes, assignments, 0, top_n=2)
    assert top == ["A", "B"]


def test_compute_cohesion():
    """Cohesion = edges_intra / possible_edges."""
    edges = [
        {"source": "a", "target": "b", "weight": 1},
        {"source": "b", "target": "c", "weight": 1},
    ]
    assignments = {"a": 0, "b": 0, "c": 0}
    # 3 nodes → 3 possible edges; 2 intra edges → 2/3
    coh = compute_cohesion(edges, assignments, 0)
    assert abs(coh - 2.0 / 3.0) < 1e-9

    # Single node → 0 cohesion
    coh_single = compute_cohesion([], {"a": 0}, 0)
    assert coh_single == 0.0
