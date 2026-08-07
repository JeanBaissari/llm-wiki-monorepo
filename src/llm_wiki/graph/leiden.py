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
    """True iff the optional ``[leiden]`` extra (graspologic) is importable."""
    try:
        import graspologic  # noqa: F401
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


def detect_communities(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    seed: int | None = 42,
) -> CommunityDetectionResult:
    """Leiden community detection with the same output contract as ``louvain.detect_communities``.

    Returns ``(assignments, communities)`` with communities renumbered
    size-descending. Requires the ``[leiden]`` extra — callers should gate on
    ``is_leiden_available()`` and fall back to Louvain otherwise.
    """
    if not nodes:
        return {}, []

    import networkx as nx
    from graspologic.partition import hierarchical_leiden

    node_ids = [n.get("id", "") for n in nodes]
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

    # Leiden runs per connected component; isolated/edgeless nodes each form a
    # singleton community (mirrors Louvain's handling of isolated nodes).
    raw: dict[str, int] = {}
    next_cid = 0
    if g.number_of_edges() > 0:
        clusters = hierarchical_leiden(g, random_seed=seed)
        final = {}
        for c in clusters:
            # Keep the deepest (final) level assignment per node.
            if getattr(c, "is_final_cluster", True):
                final[c.node] = c.cluster
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
