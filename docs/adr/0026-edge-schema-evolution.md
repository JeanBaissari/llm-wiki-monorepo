# ADR 0026: Edge-Schema Evolution — Typed + Directed + Bitemporal (Additive)

- **Status:** accepted
- **Date:** 2026-08-07
- **Context:** LWM_028 (v0.5.0) needed to give edges meaning (type), direction, and time — the pre-v0.5.0 `GraphEdge` was just `{source, target, weight}` and every consumer (dedup, community detection, insights) assumed an undirected, untyped, timeless edge. The v0.4.0 audit and the derived-edge work (LWM_029) both need a richer vocabulary. Any on-disk format change is load-bearing: `graph-data.json` (ADR-0005 two-file output) is consumed by every analytics path, and the undirected default must stay byte-identical.

## Decision

**Additive, optional fields on `GraphEdge`** (`packages/shared-types/src/index.ts`, canonical for both languages):

- `relType?: string` — open vocabulary (e.g. `is-a | part-of | cites | contradicts`).
- `directed?: boolean` — absent/false = undirected (default); true = `A→B ≠ B→A`.
- `validFrom?` / `validTo?: string` — **validity time**: the interval the relationship holds (ISO-8601 UTC).
- `observedAt?: string` — **transaction time**: when the edge was recorded.
- All optional: a legacy `{source, target, weight}` edge stays type-valid, and absent fields are **omitted** from `graph-data.json` — so the undirected default is byte-identical (camelCase on disk, matching shared-types).
- **§dedup-guard:** `build.ts::edgeDedupKey` sorts the two ids on the undirected default (`A↔B` and `B↔A` collapse — verbatim pre-v0.5.0 behavior); when a producer opts into `directed: true`, the key includes orientation + `relType`, so `A→B ≠ B→A` and `A→B#is-a ≠ A→B#cites`. No wikilink producer sets `directed`, so default output is byte-identical.
- **§once-only format change:** the on-disk edge record is extended exactly once, additively; future schema changes must be additive/versioned (references ADR-0005). Python edge carriers (`graph/louvain.py` `GraphEdge` dict, `insights.py` record path) accept and ignore the new fields on the undirected default.
- **Inert under the default:** the community partition is unchanged (NMI/ARI = 1.0 pre/post on unchanged wikis) — schema addition is inert for undirected graphs.

## Delivered State (defe7e0)

Implemented (commit fad199f, v0.5.0 lane G): `GraphEdge` in `packages/shared-types/src/index.ts:13-25`; `edgeDedupKey` + dedup guard in `graph-engine/src/build.ts:14-26, 301`; Python carriers tolerate the fields. `graph-data.json` remains byte-identical on the undirected default. No remediation batch is outstanding for this ADR.

## Consequences

**Easier:** consumers can express type/direction/time without breaking any legacy producer; the dedup guard keeps the default deterministic and byte-identical; the additive schema means no migration of existing data. **Harder:** `directed` semantics must be respected by every dedup/merge site (a missed branch would silently collapse directed edges); bitemporal fields carry no enforcement — consumers must agree on what "absent" means.
