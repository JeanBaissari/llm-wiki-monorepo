# Decision Register

All Architecture Decision Records, ordered by number. Status: **accepted** (final decision), **amended** (a later ADR changed part of it), or **reserved** (number allocated in a PRD registry, record not yet authored — no code citations). Owning PRD refers to the LWM_xxx PRD that raised the decision. One-line decisions; see each ADR file for full context, delivered state, and remediation batches.

| ADR | Date | Title | Status | Owning PRD | Decision |
|-----|------|-------|--------|-----------|----------|
| 0001 | 2026-07-04 | `discover.py` as Single Source of Truth for Wiki Structure | accepted | LWM_001 | All tools discover wiki layout through one module at startup. |
| 0002 | 2026-07-04 | Package Distribution Name vs Import Name Separation | accepted | LWM_002 | Keep distribution and import names separate. |
| 0003 | 2026-07-04 | OIDC Trusted Publishing with Digital Attestations | accepted | — | Publish via OIDC workload identity with signed attestations, no long-lived tokens. |
| 0004 | 2026-07-04 | Templates Shipped Inside Python Package | accepted | — | Ship domain templates inside the Python package. |
| 0005 | 2026-07-04 | Two-File Unified Graph Output (GAP-4 Prerequisite) | accepted | GAP-4 | Emit graph output as two files to keep diffs reviewable. |
| 0006 | 2026-07-04 | Two-Step CoT Ingest with SHA256 Caching | accepted | LWM_005 | Ingest is analysis-then-generation with SHA256-cached Stage 1. |
| 0007 | 2026-07-04 | Concurrency Control — WikiLock + Atomic Writes + SHA256 Conflict Detection | accepted | LWM_006 | Writes are atomic under a wiki lock with SHA256 conflict detection. |
| 0008 | 2026-07-04 | SQLite FTS5 Search with SHA256 Freshness Detection | accepted | LWM_007 | FTS5/BM25 keyword search with SHA256-based index freshness. |
| 0009 | 2026-07-04 | Agent-Native Provider for Zero-API-Key Ingest | accepted | LWM_009 | Pluggable agent-native LLM providers; zero-API-key ingest path. |
| 0010 | 2026-07-04 | MCP Server Architecture — stdio + Python Sidecar | accepted | LWM_010 | MCP server runs over stdio, delegating Python ops to a sidecar. |
| 0011 | 2026-07-04 | Inverted Entity Index for O(1) Link Suggestions | accepted | LWM_011 | Dual-map inverted index makes link-suggestion queries O(1). |
| 0012 | 2026-07-04 | Community Verification Suite — NMI/ARI Cross-Validation | amended | LWM_012 | Automated NMI/ARI suite cross-validates Python vs TS community engines (amended by ADR-0017: exact parity NMI/ARI == 1.0; also extended by ADR-0025 for Leiden). |
| 0013a | 2026-07-04 | v0.3.0 Modularization — Acceptance Criteria | accepted | v0.3.0 | Acceptance criteria for the modular layout (duplicate 0013 file). |
| 0013b | 2026-07-04 | Modular Package Layout by Domain | accepted | v0.3.0 | Repo organized into domain packages. |
| 0014 | 2026-07-31 | Fixture Lane Scope — Core vs Optional Classification | accepted | LWM_012 | Core-tier fixture lanes implemented; optional components get standalone verification. |
| 0015 | — | Semantic-Layer Boundary + Optional `[semantic]` Extra + Fallback Contract | reserved | LWM_013 | Reserved in the v0.4.0 registry; not yet authored (no code citations). |
| 0016 | 2026-08-06 | Vector Substrate — sqlite-vec + Mandatory NumPy KNN Fallback | accepted | LWM_017 | sqlite-vec vec0 when loadable, mandatory pure-numpy KNN fallback, fail-open routing, byte-identical backends. |
| 0017 | 2026-08-06 | Python Sidecar as the Single Graph Source of Truth | accepted | LWM_024 | One canonical Python Louvain; label-propagation deleted; TS Louvain seeded and parity-verified exactly. |
| 0018 | 2026-08-06 | Vector Storage Schema + `embed_meta` Contract | accepted | LWM_014 | Additive vector tables in `.index/wiki.db`; `embed_meta` guard forces keyword fallback on mismatch. |
| 0019 | 2026-08-06 | Default Embedding Model (model2vec) + Pluggable Embedder Interface | accepted | LWM_015 | model2vec potion-retrieval-32M static default behind a pluggable `Embedder` registry. |
| 0020 | 2026-08-07 | Hybrid Search — RRF Ranking + Promotion to Default (Eval-Gated) | accepted | LWM_019/020, LWM_032 | RRF ranks-only fusion; hybrid becomes default only after the search-eval gate proves parity on the held-out GATE split (tol 1e-6); `--keyword`/`mode="keyword"` escape retained; gate green with concept embedder, real-embedder recertification in batch B8. |
| 0021 | 2026-08-06 | No Auto-Apply on Static-Embedding Similarity Alone | amended | LWM_021 | Embedding similarity alone never auto-applies links/merges; only lexical/PPR corroboration enables `--apply` (amended by ADR-0024: alias mentions unblock `--apply`, still `[[Canonical|surface]]` only). |
| 0022 | 2026-08-06 | Eval Gold-Set Tune/Gate Split Methodology | accepted | LWM_022 | tune ∩ gate = ∅ enforced at load; tuning cannot read gate labels; absolute metrics; committed baselines. |
| 0023 | — | v0.4.0 CI Quality-Gate Suite | reserved | LWM_023 | Reserved in the v0.4.0 registry; not yet authored (no code citations). |
| 0024 | 2026-08-07 | Entity-Resolution Strategy + Reversible Canonical↔Alias Store | accepted | LWM_025 | Append-only git-diffable `aliases.jsonl` source of truth + regenerable `.index/wiki.db` cache; two-signal merge (string AND embedding); string-only bar ≥ 0.92; `[[Canonical|surface]]` only. |
| 0025 | 2026-08-07 | Leiden Community Engine — graspologic Sidecar + Default-Switch Policy | accepted | LWM_027 | Leiden via graspologic (MIT, not GPL leidenalg) under optional `[leiden]` extra; connectivity guarantee asserted; Louvain stays default until the NMI/modularity gate. |
| 0026 | 2026-08-07 | Edge-Schema Evolution — Typed + Directed + Bitemporal (Additive) | accepted | LWM_028 | Additive optional `relType`/`directed`/`validFrom`/`validTo`/`observedAt`; undirected default byte-identical via sorted-pair dedup; format change done once. |
| 0027 | 2026-08-07 | Derived-Edge Layer Separation + NMI/Modularity Inclusion Gate | accepted | LWM_029 | Derived edges quarantined in a sibling layer, excluded from all analytics by default; inclusion fail-closed on NMI ≥ 1 − tol AND modularity ≥ baseline (gate fully delivered in batch B7). |
| 0028 | 2026-08-07 | Tuning Constants as Config — Canonical TuningConfig Surface | accepted | LWM_031 | Canonical 22-constant `TuningConfig`; CLI > env > file > code-default precedence; fail-closed unknown keys (exit 2); defaults byte-identical until eval-tuned (all 22 threaded in batch B9). |
