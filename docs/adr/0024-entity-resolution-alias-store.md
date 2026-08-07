# ADR 0024: Entity-Resolution Strategy + Reversible Canonical↔Alias Store

- **Status:** accepted
- **Date:** 2026-08-07
- **Context:** LWM_025 (v0.5.0) needed to collapse variant surface forms ("GPT-4", "GPT 4", "gpt-4") into one canonical id without violating the repo's "no DB, files are canonical" moat, and without ever destroying information: a merge must be reversible by a file operation, never a schema migration. It also had to respect the ADR-0021 rule — static-embedding similarity alone must never justify a mutation.

## Decision

**A lightweight normalize → block → score → merge pipeline with a reversible, two-layer store** (`src/llm_wiki/graph/resolve.py` + `alias_store.py`, `llm-wiki entities resolve/list/unmerge`):

- **Pipeline:** `normalize` (NFKC + casefold + separator/punctuation collapse) → blocking (shared token / 3-char prefix; sub-quadratic pair count) → scoring (`difflib` string ratio + embedding cosine via `[semantic]` when present) → union-find merge. Canonical per cluster: longest surface form (tie: sorted).
- **Two-signal merge rule:** a non-identical pair merges **only when two independent signals agree** — string **and** embedding (`ss ≥ 0.85` AND `cos ≥ 0.80`). Embedding alone **never** merges. Without an embedder, only string similarity merges at a **raised bar ≥ 0.92** — so a missing extra never causes looser merging.
- **Ambiguous/single-signal candidates are review rows, not merges.**
- **Store split (§store):**
  - `.llm-wiki/entities/aliases.jsonl` — the append-only, **git-diffable source of truth**: one JSON event per line (`{event: merge|unmerge, canonical_id, alias, ...}`). Reversibility is appending an `unmerge` event; `resolve_state` replays events into `{alias → canonical_id}`.
  - `.index/wiki.db` derived tables (`entity_aliases`, `entity_canonical`, `alias_meta`) — a **regenerable cache** rebuilt from the JSONL; `alias_meta` (resolver id + threshold + schema version) is asserted by every reader; on mismatch/absence the reader rebuilds rather than serving stale merges (the ADR-0018 `embed_meta` pattern).
- **`--apply` writes only `[[Canonical|surface]]`** — surface form preserved; the `entities` CLI itself never rewrites page prose. `link-suggest --semantic --apply` routes alias mentions to the canonical page (unblocking ADR-0021's auto-applicable path).
- **§extras:** Splink is an optional `[entity-resolution]` extra (v0.5.0 invariant #3: optional extra + fallback), never imported here.

## Delivered State (defe7e0)

Fully implemented (commits d59c5d1 / 6a9f686, v0.5.0 lanes F): `resolve.py`, `alias_store.py`, `entities.py` CLI, alias routing in `graph/suggest.py`, and `eval/er_metrics.py`. GLiNER extraction (LWM_026) feeds cleaner candidates via the pluggable `EntityExtractor` interface under the `[ner]` extra. No remediation batch is outstanding for this ADR.

## Consequences

**Easier:** resolution is fully reversible and auditable (append-only events, git-diffable); the JSONL survives any cache wipe; a missing extra can never loosen merge behavior. **Harder:** string-only resolution is conservative by design (≥ 0.92), so some obvious aliases need the embedding signal to merge; review rows for ambiguous candidates require a human/agent step.
