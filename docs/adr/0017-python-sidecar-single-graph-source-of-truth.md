# ADR 0017: Python Sidecar as the Single Graph Source of Truth

- **Status:** accepted
- **Date:** 2026-08-06
- **Context:** LWM_024 (v0.4.0 graph consolidation) fixed a two-divergent-community-engines defect: `llm-wiki insights` used a greedy label-propagation pass while the TypeScript graph-engine used Louvain, producing different communities and different "surprising connections" for the same wiki. The repo's ADR-0012 suite cross-validates the two implementations — but a single canonical algorithm removes the divergence at the root.

## Decision

The **Python sidecar owns the canonical graph computation**; the TypeScript side consumes it and never re-derives community logic on a divergent path:

- `graph/louvain.py::detect_communities(nodes, edges, seed=42)` is the canonical engine. The label-propagation `communities()` in `graph/insights.py` was **deleted**; `llm-wiki insights` routes every community assignment through the canonical Louvain (insights.py:85-90, LWM_024 / ADR-0017).
- The TypeScript graph-engine's own Louvain is kept as a deterministic, seeded implementation (mulberry32 PRNG, default seed 42 — previously non-deterministic via `Math.random`) and is held in lockstep with the Python engine by the ADR-0012 verification suite, whose parity threshold was **raised from NMI/ARI > 0.95 to exact agreement (NMI == 1.0 and ARI == 1.0)** across the 7-topology × 5-seed matrix (ADR-0012 amendment).
- The untyped-page node-type default was aligned to `concept` in both languages; `graph-data.json` shape is unchanged.
- §engine-selection: Louvain is the canonical algorithm; later engines (e.g. the opt-in Leiden sidecar, ADR-0025) implement the identical `detect_communities` contract and never replace the default without a gated switch.

## Delivered State (defe7e0)

Implemented per commit ffb6b90 (v0.4.0 lane B): label-propagation removed (grep-encoded test), insights route through `graph/louvain.py`, TS `louvain.ts` seeded and deterministic, node-type default `concept` in both languages, `graph-data.json` shape unchanged, Python insights == TS insights on the shared fixture. The ADR-0012 suite (7 topologies × 5 seeds, NMI/ARI == 1.0) is the ongoing parity gate. No remediation batch is outstanding for this ADR.

## Consequences

**Easier:** one canonical algorithm means community IDs, surprising connections, and gaps agree between `llm-wiki insights`, the graph-engine, and the MCP tools. Builds are reproducible. **Harder:** any future community-algorithm change must preserve the exact `CommunityDetectionResult` contract and pass the exact-parity suite before the default may move (see ADR-0025's default-switch policy).
