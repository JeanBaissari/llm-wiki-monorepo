# ADR 0025: Leiden Community Engine — graspologic Sidecar + Default-Switch Policy

- **Status:** accepted
- **Date:** 2026-08-07
- **Context:** LWM_027 (v0.5.0) wanted an alternate community engine with a stronger guarantee than Louvain — internally-connected communities (Traag, Waltman & van Eck 2019), which Louvain cannot provide. Any new engine is an execution-engine change, and the default engine may only move with evidence. The repo's license policy (MIT/Apache-2.0/BSD only) ruled out the standard Leiden library.

## Decision

**Leiden runs as an optional Python sidecar via `graspologic` (MIT) — chosen over `leidenalg` (GPLv3), which is rejected on license grounds** (`src/llm_wiki/graph/leiden.py`):

- **§library-selection:** `graspologic.hierarchical_leiden` (MIT) + `networkx`; `leidenalg`'s GPLv3 is explicitly rejected to honor the repo's dependency-license policy. Both live in the optional `[leiden]` extra; the base install never imports them.
- **Contract parity:** `detect_communities(nodes, edges, seed=42)` returns the *identical* `CommunityDetectionResult` shape as `louvain.py` (`{id, nodeCount, cohesion, topNodes}`, renumbered size-descending), reusing Louvain's `compute_cohesion` / `build_top_nodes` / `_renumber_size_descending` — so `graph-data.json` layout is byte-identical whichever engine emits it.
- **Python sidecar canonical; TS consumes:** the TypeScript graph-engine defines **no TS Leiden**; it reads Python sidecar communities (verified by `no_ts_leiden`).
- **Internal-connectivity guarantee:** every emitted community's induced subgraph must be connected — asserted per community (`_induced_connected`); a disconnected emission raises `AssertionError` (leiden.py:126-130) rather than silently emitting a bad partition.
- **Per-component execution:** Leiden runs per connected component (`hierarchical_leiden` per component; isolated/edgeless nodes form singleton communities, mirroring Louvain's isolated-node handling).
- **§default-switch policy:** **Louvain stays the default** until the ADR-0012 suite (extended to cover Leiden) proves Leiden ≥ Louvain — NMI and modularity on the disjoint gate set — and the flip itself is a separate, gated change. Import is always safe: without the `[leiden]` extra `is_leiden_available()` returns False and the engine selector falls back to Louvain (never raises).

## Delivered State (defe7e0)

Implemented (commit fad199f, v0.5.0 lane G): `graph/leiden.py` with the connectivity assertion, capability probe, engine selector (`insights.py` `engine` param — default Louvain, byte-identical; `summarize.py` honors the same selector); `[leiden]` extra in `pyproject.toml`; default engine is Louvain (never silently flipped). The default-switch parity gate is the extended ADR-0012 verification suite; the flip itself has not been performed. No remediation batch is outstanding for this ADR.

## Consequences

**Easier:** Leiden's connectivity guarantee is enforced, not hoped for; the sidecar pattern keeps the base install pure; community output shape is engine-independent. **Harder:** graspologic+networkx add install weight to the optional extra; Leiden is slower than Louvain on large graphs; the default switch is deliberately deferred to a gated future change.
