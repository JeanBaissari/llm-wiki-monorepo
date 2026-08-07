#!/usr/bin/env python3
"""leiden.py — Optional Leiden community engine (LWM_027). See ADR-0025.

A sibling to ``graph/louvain.py`` with the *identical* ``detect_communities()``
contract, backed by ``graspologic.hierarchical_leiden`` (MIT — chosen over the
GPLv3 ``leidenalg`` to honor the repo's license policy). Leiden guarantees
internally-connected communities (Traag, Waltman & van Eck 2019), which Louvain
cannot; this module reuses Louvain's ``compute_cohesion`` / ``build_top_nodes`` /
``_renumber_size_descending`` so the emitted ``CommunityInfo`` shape and
``graph-data.json`` layout are byte-identical to the default engine.

Importing this module is always safe: ``is_leiden_available()`` returns ``False``
without the optional ``[leiden]`` extra, and the engine selector falls back to
Louvain — Louvain stays the default until the ADR-0012 NMI/modularity gate proves
Leiden ≥ Louvain on the disjoint gate set (default-switch policy in ADR-0025).
The ``graspologic`` import is deferred to the call site, never at module import.
"""

from __future__ import annotations

from llm_wiki.graph.louvain import (
    CommunityDetectionResult,
    CommunityInfo,
    GraphEdge,
    GraphNode,
    build_top_nodes,
    compute_cohesion,
)


def is_leiden_available() -> bool:
    """True iff the optional ``[leiden]`` extra (graspologic + networkx) is importable."""
    try:
        import graspologic  # noqa: F401
        import networkx  # noqa: F401
    except ImportError:
        return False
    return True


def _induced_connected(members: set, edges: list[GraphEdge]) -> bool:
    """True iff the induced subgraph over ``members`` is connected (Leiden's guarantee)."""
    if len(members) <= 1:
        return True
    adj: dict = {m: set() for m in members}
    for e in edges:
        s, t = e.get("source"), e.get("target")
        if s in members and t in members and s != t:
            adj[s].add(t)
            adj[t].add(s)
    start = next(iter(members))
    seen = {start}
    stack = [start]
    while stack:
        n = stack.pop()
        for nb in adj[n]:
            if nb not in seen:
                seen.add(nb)
                stack.append(nb)
    return seen == members


def _build_graph(node_ids: list[str], edges: list[GraphEdge]):
    """Build the undirected weighted graph shared by all Leiden entry points."""
    import networkx as nx

    g = nx.Graph()
    g.add_nodes_from(node_ids)
    for e in edges:
        s, t = e.get("source"), e.get("target")
        if s is None or t is None or s == t:
            continue
        w = float(e.get("weight", 1.0) or 1.0)
        if g.has_edge(s, t):
            g[s][t]["weight"] += w
        else:
            g.add_edge(s, t, weight=w)
    return g


def _sanitize_seed(seed: int | None) -> int | None:
    """graspologic's native PRNG is an unsigned 64-bit int and rejects seed 0."""
    if seed is None:
        return None
    return seed if seed > 0 else 1


def _leiden_component_levels(g, seed: int | None = 42):
    """Run ``hierarchical_leiden`` per connected component (AD-18).

    graspologic drops isolate (degree-0) nodes from its output and warns; on a
    whole multi-component graph those nodes would silently disappear. Splitting
    into connected components first and running Leiden per component (only
    components with ≥2 nodes — singletons become their own communities directly)
    keeps every node accounted for.

    Yields ``(component_members, levels)`` for each component with ≥2 nodes,
    where ``levels`` maps graspologic level → {node_id: cluster_id}. Level 0 is
    the initial partition; deeper levels refine communities that exceeded
    ``max_cluster_size``. All members of a component appear at level 0 — asserted
    so a silent drop fails loudly instead of producing a corrupted partition.
    """
    import networkx as nx
    from graspologic.partition import hierarchical_leiden

    random_seed = _sanitize_seed(seed)
    for comp in nx.connected_components(g):
        if len(comp) < 2:
            continue
        sub = nx.Graph(g.subgraph(comp))
        clusters = hierarchical_leiden(sub, random_seed=random_seed)
        levels: dict[int, dict[str, int]] = {}
        for c in clusters:
            levels.setdefault(c.level, {})[c.node] = c.cluster
        # AD-18: the whole component must be covered at level 0 (the initial
        # partition). Fail loudly rather than silently dropping nodes.
        missing = comp - set(levels.get(0, {}))
        if missing:
            raise AssertionError(
                f"hierarchical_leiden dropped nodes {sorted(missing)} from a "
                f"{len(comp)}-node component — violates AD-18 (all nodes assigned)."
            )
        yield comp, levels


def _flat_partition(levels: dict[int, dict[str, int]]) -> dict[str, int]:
    """Merge graspologic levels into the final (deepest) partition per node."""
    final: dict[str, int] = {}
    for level_map in levels.values():
        final.update(level_map)
    return final


def detect_communities(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    seed: int | None = 42,
) -> CommunityDetectionResult:
    """Leiden community detection with the same output contract as ``louvain.detect_communities``.

    Runs ``hierarchical_leiden`` per connected component (components with ≥2
    nodes; isolated nodes become their own singleton communities directly), so
    multi-component graphs and degree-0 nodes are handled without relying on
    graspologic's isolate handling (AD-18).

    Returns ``(assignments, communities)`` with communities renumbered
    size-descending. Requires the ``[leiden]`` extra — callers should gate on
    ``is_leiden_available()`` and fall back to Louvain otherwise.
    """
    if not nodes:
        return {}, []

    node_ids = [n.get("id", "") for n in nodes]
    g = _build_graph(node_ids, edges)

    # Leiden runs per connected component; isolated/edgeless nodes each form a
    # singleton community (mirrors Louvain's handling of isolated nodes).
    raw: dict[str, int] = {}
    next_cid = 0
    if g.number_of_edges() > 0:
        for comp, levels in _leiden_component_levels(g, seed):
            final = _flat_partition(levels)
            # Map graspologic cluster ids to a dense 0..k range.
            remap: dict = {}
            for nid in node_ids:
                if nid in final:
                    cl = final[nid]
                    if cl not in remap:
                        remap[cl] = next_cid
                        next_cid += 1
                    raw[nid] = remap[cl]
    for nid in node_ids:
        raw.setdefault(nid, next_cid)
        if raw[nid] == next_cid:
            next_cid += 1

    from llm_wiki.graph.louvain import _renumber_size_descending

    assignments = _renumber_size_descending(raw)

    community_ids = sorted(set(assignments.values()))
    communities: list[CommunityInfo] = []
    for cid in community_ids:
        members = {nid for nid, c in assignments.items() if c == cid}
        # Leiden's core guarantee — assert rather than silently emit a bad partition.
        if not _induced_connected(members, edges):
            raise AssertionError(
                f"Leiden emitted an internally-disconnected community {cid} "
                f"({len(members)} nodes) — violates the connectivity guarantee (ADR-0025)."
            )
        top_nodes = build_top_nodes(nodes, assignments, cid, top_n=5)
        cohesion = compute_cohesion(edges, assignments, cid)
        communities.append({
            "id": cid,
            "nodeCount": len(members),
            "cohesion": round(cohesion, 4),
            "topNodes": top_nodes,
        })

    communities.sort(key=lambda c: (-c["nodeCount"], c["id"]))
    renumbered: list[CommunityInfo] = []
    id_map: dict[int, int] = {}
    for new_id, comm in enumerate(communities):
        id_map[comm["id"]] = new_id
        comm["id"] = new_id
        renumbered.append(comm)
    assignments = {nid: id_map[cid] for nid, cid in assignments.items()}
    return assignments, renumbered


def hierarchical_levels(
    node_list: list[GraphNode],
    edge_list: list[GraphEdge],
    seed: int | None = 42,
) -> list[dict] | None:
    """B6 hierarchy seam (consumed by ``summarize._hierarchy_from_leiden``).

    Runs ``hierarchical_leiden`` per connected component (same helper as
    ``detect_communities``) and exposes the per-component partitions as a
    bottom-up hierarchy — finest partition first, coarsest last — with every
    node assigned at every level (singletons keep their own community):

        [{"level": 0, "assignments": {node_id: cid}},      # finest
         {"level": 1, "assignments": {node_id: cid}},      # coarser
         ...]

    Level 0 equals the flat ``detect_communities`` partition. Deeper levels
    exist only when graspologic subdivided communities larger than
    ``max_cluster_size`` (default 1000); components without a level-L partition
    carry their coarsest (level-0) partition upward, so each level is a valid
    coarsening of the previous one.

    Returns ``None`` (never raises) when the ``[leiden]`` extra is unavailable,
    the graph is empty (no nodes or no edges), or Leiden computed only a single
    flat level — in all of these cases no hierarchy exists and the caller
    (summarize) degrades to its flat/agglomerated path.
    """
    if not is_leiden_available():
        return None
    if not node_list:
        return None

    node_ids = [n.get("id", "") for n in node_list]
    g = _build_graph(node_ids, edge_list)
    if g.number_of_edges() == 0:
        return None

    component_levels = list(_leiden_component_levels(g, seed))
    if not component_levels:
        return None

    max_level = max(max(levels) for _, levels in component_levels)
    if max_level == 0:
        # Single flat partition — no hierarchy to expose; callers degrade.
        return None

    # Assign singleton (isolated) nodes their own community at every level.
    singleton_ids = set(node_ids)
    for _, levels in component_levels:
        singleton_ids -= set(_flat_partition(levels))

    levels_out: list[dict] = []
    # Bottom-up: finest (deepest graspologic level) first.
    for level_idx, gi in enumerate(range(max_level, -1, -1)):
        assignments: dict[str, int] = {}
        next_cid = 0
        for _, levels in component_levels:
            # Components with no level-gi partition (community not subdivided)
            # keep their coarsest partition — nested hierarchy preserved.
            level_map = levels.get(gi, levels[0])
            # Deterministic per-component cluster-id numbering.
            remap = {cl: i + next_cid for i, cl in enumerate(sorted(set(level_map.values())))}
            assignments.update({nid: remap[cl] for nid, cl in level_map.items()})
            next_cid += len(remap)
        for nid in sorted(singleton_ids):
            assignments[nid] = next_cid
            next_cid += 1
        levels_out.append({"level": level_idx, "assignments": assignments})

    return levels_out
