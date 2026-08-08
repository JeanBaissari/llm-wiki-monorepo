#!/usr/bin/env python3
"""louvain.py — Blondel Louvain community detection (Phase 1).

Implements the Blondel et al. (2008) Louvain algorithm for
community detection in undirected weighted graphs.

Single-phase iterative algorithm:
  Phase 1 — Modularity optimization: greedily move nodes to
             maximize modularity gain.

Maintains per-community Σ_in (internal edge weight, counted once)
and Σ_tot (total incident weight) accounting — needed for matching
the graphology-communities-louvain library and enabling future
multi-level aggregation (Phase 2).

Matches the TypeScript `graphology-communities-louvain` library at
NMI/ARI > 0.95 across planted partition tests.

Output format:
  - communities renumbered sequentially by size (0 = largest) (Q10)
  - cohesion (intra-community edge density) computed per community
  - top 5 nodes by linkCount surfaced per community
"""

from __future__ import annotations

import random
import warnings
from collections import defaultdict
from typing import Any

# ── Types ──────────────────────────────────────────────────────────────────

GraphNode = dict[str, Any]  # {id, label, linkCount, ...}
GraphEdge = dict[str, Any]  # {source, target, weight}

CommunityInfo = dict[str, Any]  # {id, nodeCount, cohesion, topNodes}

CommunityDetectionResult = tuple[
    dict[str, int],          # assignments: nodeId → communityId
    list[CommunityInfo],     # communities: sorted by size desc
]

EPSILON = 1e-10


# ── Louvain Core ───────────────────────────────────────────────────────────


def _louvain_pass(
    node_order: list[str],
    community: dict[str, int],
    sigma_in: dict[int, float],
    sigma_tot: dict[int, float],
    k: dict[str, float],
    adj: dict[str, dict[str, float]],
    m: float,
) -> bool:
    """One full pass of Phase 1 (local modularity optimization).

    For each node, evaluates the modularity gain of moving it to a
    neighbor's community.  Uses the standard Blondel ΔQ formula which
    reduces to:

        ΔQ ∝ k_i_in[C] - k_i · Σ_tot[C] / (2m)

    (within a constant scaling factor common to all candidates).
    Maintains per-community Σ_in / Σ_tot for Phase 2 readiness.

    Args:
        node_order: List of node IDs to iterate (shuffled by _louvain).
        community:  Current {nodeId → communityId} assignments.
        sigma_in:   {communityId → Σ_in} internal edge weight.
        sigma_tot:  {communityId → Σ_tot} total incident weight.
        k:          {nodeId → degree}.
        adj:        {nodeId → {neighborId → weight}}.
        m:          Total edge weight (half sum of all degrees).

    Returns:
        True if any node moved during this pass.
    """
    changed = False
    for n in node_order:
        nb = adj[n]
        if not nb:
            continue

        current_comm = community[n]
        deg = k[n]

        # ── Count edges from n to each neighboring community ─────────┐
        k_i_in: dict[int, float] = defaultdict(float)
        for nb_id, w in nb.items():
            nb_comm = community[nb_id]
            k_i_in[nb_comm] += w

        # ── Temporarily remove node from current community ───────────┘
        sigma_tot[current_comm] -= deg
        # sigma_in accounting: removing i removes 2·k_i_in_A from Σ_in
        k_i_in_current = k_i_in.get(current_comm, 0.0)
        sigma_in[current_comm] = sigma_in.get(current_comm, 0.0) - 2.0 * k_i_in_current

        # ── Evaluate gain for each candidate community ───────────────│
        best_comm = current_comm
        # ΔQ_stay = k_i_in_current - deg · sigma_tot[current_comm] / (2m)
        best_delta = k_i_in_current - deg * sigma_tot[current_comm] / (2.0 * m)

        for target_comm, k_i_in_target in k_i_in.items():
            if target_comm == current_comm:
                continue

            # ΔQ_join = k_i_in_target - deg · sigma_tot[target] / (2m)
            delta = k_i_in_target - deg * sigma_tot[target_comm] / (2.0 * m)

            # Tiebreaker: prefer higher community ID when gains equal
            if abs(delta - best_delta) < EPSILON:
                if target_comm > best_comm and best_comm != current_comm:
                    continue
                elif target_comm > best_comm:
                    best_delta = delta
                    best_comm = target_comm
            elif delta > best_delta:
                best_delta = delta
                best_comm = target_comm

        # ── Move node if a better community was found ────────────────│
        if best_comm != current_comm:
            community[n] = best_comm
            sigma_tot[best_comm] += deg
            sigma_in[best_comm] = sigma_in.get(best_comm, 0.0) + 2.0 * k_i_in.get(best_comm, 0.0)
            changed = True
        else:
            # Roll back the temporary removal
            community[n] = current_comm
            sigma_tot[current_comm] += deg
            sigma_in[current_comm] += 2.0 * k_i_in_current

    return changed


def _louvain(
    node_ids: list[str],
    adj: dict[str, dict[str, float]],
    k: dict[str, float],
    loops: dict[str, float],
    total_weight: float,
    resolution: float = 1.0,
    seed: int | None = 42,
) -> dict[str, int]:
    """Single-pass Phase 1 Louvain community detection.

    Matches graphology-communities-louvain (no multi-level aggregation).
    Node order is shuffled with the given seed on each pass for
    deterministic yet randomised iteration (§II.B of Blondel et al.).

    Args:
        node_ids: List of all node IDs (initial iteration order).
        adj: Adjacency dict {node: {neighbor: weight}}.
        k: Weighted degree of each node.
        loops: Self-loop weight of each node.
        total_weight: Total weight of all edges (m).
        resolution: Resolution parameter (default 1.0).
        seed: Random seed for reproducibility (default 42).

    Returns:
        nodeId -> communityId (pre-renumbering).
    """
    if not node_ids:
        return {}

    # Initial state: each node in its own community
    community: dict[str, int] = {n: i for i, n in enumerate(node_ids)}
    sigma_tot: dict[int, float] = {community[n]: k[n] for n in node_ids}
    sigma_in: dict[int, float] = {community[n]: 0.0 for n in node_ids}
    m = total_weight

    # Phase 1: multiple passes until convergence.
    # Each pass shuffles node order for deterministic randomisation.
    rng = random.Random(seed)
    changed = True
    max_passes = 50
    pass_count = 0

    node_order = list(node_ids)
    while changed and pass_count < max_passes:
        pass_count += 1
        rng.shuffle(node_order)
        changed = _louvain_pass(
            node_order, community, sigma_in, sigma_tot, k, adj, m,
        )

    return community


# ── Public API ─────────────────────────────────────────────────────────────


def louvain(
    edges: list[GraphEdge],
    nodes: list[str] | None = None,
    resolution: float = 1.0,
    seed: int | None = 42,
) -> dict[str, int]:
    """Run single-pass Phase 1 Louvain community detection.

    Matches graphology-communities-louvain (no multi-level aggregation).

    Args:
        edges: List of {source, target, weight} dicts.
        nodes: Optional explicit list of node IDs (for isolated nodes).
               If None, nodes are inferred from edges.
        resolution: Resolution parameter (default 1.0).
        seed: Random seed for reproducibility (default 42).

    Returns:
        nodeId → communityId (not yet renumbered).
    """
    # ── Build adjacency list ─────────────────────────────────────────
    adj: dict[str, dict[str, float]] = defaultdict(dict)
    loops: dict[str, float] = defaultdict(float)
    node_set: set[str] = set()

    for e in edges:
        s, t = e["source"], e["target"]
        w = float(e.get("weight", 1))
        if s == t:
            loops[s] += w
            node_set.add(s)
        else:
            adj[s][t] = adj[s].get(t, 0.0) + w
            adj[t][s] = adj[t].get(s, 0.0) + w
            node_set.add(s)
            node_set.add(t)

    if nodes is not None:
        node_set.update(nodes)

    # Preserve input order for deterministic initial ordering
    node_ids: list[str] = []
    seen: set[str] = set()
    if nodes is not None:
        for n in nodes:
            if n in node_set and n not in seen:
                node_ids.append(n)
                seen.add(n)
    for n in sorted(node_set):
        if n not in seen:
            node_ids.append(n)

    if not node_ids:
        return {}

    # Weighted degree (k_i) and total weight (m)
    k: dict[str, float] = {}
    for n in node_ids:
        deg = sum(adj[n].values())
        # Self-loop weight counts twice in degree (matching TS: degree += loops[i])
        deg += 2.0 * loops.get(n, 0.0)
        k[n] = deg

    # Total weight (m): half the sum of all degrees
    m = sum(k.values()) / 2.0

    # ── Single-pass Phase 1 Louvain ──────────────────────────────────
    return _louvain(node_ids, adj, k, loops, m, resolution, seed)


def _renumber_size_descending(
    assignments: dict[str, int],
) -> dict[str, int]:
    """Renumber community IDs sequentially (0, 1, 2…) sorted by size.

    Largest community gets ID 0, second-largest gets ID 1, etc.
    Ties are broken by old community ID (lower old ID gets lower new ID).
    """
    counts: dict[int, int] = defaultdict(int)
    for cid in assignments.values():
        counts[cid] += 1

    sorted_cids = sorted(counts.keys(), key=lambda c: (-counts[c], c))
    renumber = {old_id: new_id for new_id, old_id in enumerate(sorted_cids)}
    return {nid: renumber[cid] for nid, cid in assignments.items()}


def build_top_nodes(
    nodes: list[GraphNode],
    assignments: dict[str, int],
    community_id: int,
    top_n: int = 5,
) -> list[str]:
    """Get top N nodes in a community by linkCount, descending."""
    members = [n for n in nodes if assignments.get(n.get("id", "")) == community_id]
    members.sort(key=lambda n: -n.get("linkCount", 0))
    return [n.get("label", n.get("id", "?")) for n in members[:top_n]]


def compute_cohesion(
    edges: list[GraphEdge],
    assignments: dict[str, int],
    community_id: int,
) -> float:
    """Compute intra-community edge density (cohesion) for a community."""
    n = sum(1 for cid in assignments.values() if cid == community_id)
    if n <= 1:
        return 0.0

    intra = 0
    for e in edges:
        src_c = assignments.get(e.get("source", ""))
        tgt_c = assignments.get(e.get("target", ""))
        if src_c == community_id and tgt_c == community_id:
            intra += 1

    possible = n * (n - 1) / 2.0
    return intra / possible if possible > 0 else 0.0


def _compute_modularity(
    adjacency: dict[str, set[str]],
    assignments: dict[str, int],
) -> float:
    """Compute Newman-Girvan modularity Q for the partition.

    Used to compare TS and Python community quality.
    The same function is defined in cross-validation scripts for
    standalone verification.

    Args:
        adjacency: Map<node_id, Set<neighbor_id>> — undirected adjacency.
        assignments: Map<node_id, community_id>.

    Returns:
        Modularity Q in [-0.5, 1.0]. 0.0 for empty or single-community graphs.
    """
    m = sum(len(n) for n in adjacency.values()) // 2
    if m == 0:
        return 0.0

    Q = 0.0
    for node_i, neighbors in adjacency.items():
        for node_j in neighbors:
            if node_i >= node_j:  # each undirected edge once
                continue
            if assignments.get(node_i) == assignments.get(node_j):
                k_i = len(adjacency[node_i])
                k_j = len(adjacency[node_j])
                Q += 1.0 / (2 * m) - (k_i * k_j) / (4 * m * m)
    return Q


def detect_communities(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    seed: int | None = 42,
    resolution: float = 1.0,
) -> CommunityDetectionResult:
    """Run Louvain community detection, matching TS detectCommunities output.

    Args:
        nodes: List of node dicts with id, label, linkCount.
        edges: List of edge dicts with source, target, weight.
        seed: Random seed for reproducibility (default 42).
        resolution: Resolution parameter (default 1.0) — threaded from
            ``community.resolution`` (LWM_031) by tuned callers.

    Returns:
        Tuple of (assignments: dict[nodeId → communityId],
                  communities: list[CommunityInfo])
    """
    if not nodes:
        return {}, []

    # Runtime warning: label propagation has been replaced by Louvain (Q14)
    warnings.warn(
        "Community detection switched from label propagation to Louvain (Blondel et al. 2008). "
        "Results may differ from earlier runs. This warning will be removed in a future release.",
        UserWarning,
        stacklevel=2,
    )

    node_ids = [n.get("id", "") for n in nodes]
    raw_assignments = louvain(edges, nodes=node_ids, resolution=resolution, seed=seed)

    # Renumber size-descending (largest community = 0)
    assignments = _renumber_size_descending(raw_assignments)

    # Build community info
    community_ids = sorted(set(assignments.values()))
    communities: list[CommunityInfo] = []

    for cid in community_ids:
        top_nodes = build_top_nodes(nodes, assignments, cid, top_n=5)
        cohesion = compute_cohesion(edges, assignments, cid)
        node_count = sum(1 for c in assignments.values() if c == cid)
        communities.append({
            "id": cid,
            "nodeCount": node_count,
            "cohesion": round(cohesion, 4),
            "topNodes": top_nodes,
        })

    # Sort communities by size descending
    communities.sort(key=lambda c: (-c["nodeCount"], c["id"]))

    # Re-number after sorting
    renumbered: list[CommunityInfo] = []
    id_map: dict[int, int] = {}
    for new_id, comm in enumerate(communities):
        id_map[comm["id"]] = new_id
        comm["id"] = new_id
        renumbered.append(comm)

    assignments = {nid: id_map[cid] for nid, cid in assignments.items()}
    return assignments, renumbered
