# ADR 0027: Derived-Edge Layer Separation + NMI/Modularity Inclusion Gate

- **Status:** accepted
- **Date:** 2026-08-07
- **Context:** LWM_029 (v0.5.0) discovered two latent edge kinds the wikilink graph cannot see — embedding-similarity edges and shared-source/entity co-occurrence edges. The obvious fix — merge them into `edges[]` — was tried and **rejected in the v0.4.0 audit**: dense similarity edges blob Louvain/Leiden communities, make "surprising connections" vanish (every pair becomes trivially cross-community and low-weight), and destroy isolated-node gap detection (a single similarity edge lifts every page above the `deg ≤ 1` floor). The value only survives if derived edges are **quarantined by construction** and inclusion is gated on community quality.

## Decision

**Derived edges live in a separate sibling layer (`.index/derived-edges.json`), excluded by default from ALL analytics** — `build.ts`, `graph-data.json`'s `edges[]`, `linkCount`, community detection, insights, and gap detection never open it (`src/llm_wiki/graph/derived_edges.py`):

- **Two derived kinds** (typed via ADR-0026's `rel_type` vocabulary):
  - `similar_to` — cosine-KNN over the v0.4.0 page vectors (cos ≥ tau = 0.80, top-m = 5 per node). Reuses `semantic.vectorstore`; asserts `embed_meta` and is **skipped (never corrupted)** when the `[semantic]` extra / vectors / meta are absent — co-occurrence still runs.
  - `co_occurs_with` — page pairs sharing ≥ 1 frontmatter source OR ≥ 2 registry entities. Pure lexical/structural; runs on the base install.
- **Default-exclusion is guaranteed by construction** — the layer is a new artifact nothing opens; inclusion is **opt-in per consumer** (e.g. `--include-derived`) and **fail-closed on the gate**.
- **§gate:** inclusion is allowed only when the derived-influenced partition explains the curated wikilink structure **at least as well as the wikilink-only baseline**: the with-derived partition must satisfy **NMI ≥ 1 − tol AND modularity ≥ baseline modularity**, with **both partitions scored on the SAME (wikilink) graph** — apples-to-apples. On any degradation, or an empty derived layer, inclusion is **refused** (`should_include_derived` returns `(False, report)` with the reason).
- Derived edges duplicating an existing wikilink edge are dropped — the wikilink is canonical.

## Delivered State (defe7e0)

The generator and the quarantined layer are fully implemented (`llm-wiki derive-edges`, default-exclusion by construction). **The gate is currently modularity-only** (`should_include_derived` compares `with_derived_modularity ≥ baseline_modularity` on the wikilink graph). **Remediation batch B7 upgrades the gate to NMI + modularity** (NMI ≥ 1 − tol AND modularity ≥ baseline, per the ADR-0012 NMI/ARI machinery + LWM_022 harness) and **wires `--include-derived`** for consumers. This ADR records the full NMI+modularity gate as the intended contract; the code matches it by tag time.

## Consequences

**Easier:** derived edges are valuable but harmless — they can never silently degrade communities/insights/gaps, and the base graph stays byte-identical. **Harder:** the gate is deliberately conservative (fail-closed), so on noisy wikis derived edges may be refused and require threshold tuning (tau/top-m/min-shared) via the generator params; consumers must pass the gate explicitly on every inclusion.
