# docs/reference/file-map.md — Complete File Map

Every file in the llm-wiki-monorepo, organized by package with descriptions.

## Root

| File | Purpose |
|------|---------|
| `README.md` | Project overview, quick start, architecture |
| `docs/getting-started/quickstart.md` | Installation and first wiki — quick start guide |
| `docs/reference/cli.md` | Full CLI command reference with examples |
| `docs/reference/mcp-tools.md` | MCP server, web viewer, browser extension reference |
| `docs/reference/tuning.md` | Tuning-config surface — every precision constant, precedence, emit boundary (LWM_031/ADR-0028) |
| `docs/reference/file-map.md` | This file — complete file tree |
| `docs/operations/index.md` | Operations notes index (runbooks for shipped behavior changes) |
| `docs/operations/hybrid-default-search.md` | Hybrid-search default migration note — what changed, how to opt back to keyword (LWM_032/ADR-0020) |
| `docs/operations/security-and-boundaries.md` | Per-wiki auth/visibility boundary statement — files-first trust model, stdio-local MCP, recommended patterns (LWM_039 §C) |
| `AGENTS.md` | Architecture and conventions for AI agents |
| `docs/architecture/overview.md` | Why this system exists, core principles, success criteria |
| `docs/release/versioning.md` | Semantic versioning policy and release process |
| `install.sh` | One-command install — detects deps, builds, creates wrappers |
| `package.json` | NPM workspace root — scripts for build/test/run |
| `.gitignore` | Git ignore rules |
| `.github/workflows/ci.yml` | GitHub Actions CI — syntax checks, builds, integration tests, eval gates, release certify |
| `tests/eval/gold/GOLD_SET.md` | Search-eval gold-set provenance and regeneration rules (LWM_032) |
| `docs/adr/index.md` + `docs/adr/decision-register.md` | ADR index and decision register — every ADR 0001–0028 plus deliberate gaps |

---

## `skill/` — Agent Skill

The Hermes/Claude/Codex agent skill. Symlinked into `~/.hermes/skills/research/llm-wiki`.

### `skill/SKILL.md`
Main skill file. 8 operations: compile, ingest, ingest-2step, query, lint, audit, research, insights. Includes graphify integration, EOW cron pipeline, template system, MCP server reference.

### `skill/references/` — 10 reference guides

| File | Purpose |
|------|---------|
| `schema-guide.md` | CLAUDE.md schema template — scope, conventions, frontmatter, research questions |
| `article-guide.md` | How to write wiki articles — length targets, structure templates, diagrams, formulas, provenance markers |
| `audit-guide.md` | Audit file format, anchor strategy, processing workflow for human feedback |
| `log-guide.md` | Log/ directory convention — one file per day, op format, grep patterns |
| `tooling-tips.md` | Obsidian setup, Web Clipper, qmd search, plugin + web viewer installation |
| `ingest-guide.md` | Two-step chain-of-thought ingest architecture — Stage 1 analysis + Stage 2 generation |
| `graphify-pipeline.md` | Graphify knowledge graph integration — AST extraction, semantic extraction, output structure |
| `graph-construction-strategies.md` | When to use full graphify vs wikilinks-only graph construction |
| `eow-cron-pipeline.md` | Weekly automated maintenance — discover repos, assess health, conditional graph rebuild, lint, report |
| `migration-guide.md` | Migrating v1 wikis (flat structure, log.md) to v2 format (log/ directory, wiki/ subdirectory) |

### `skill/scripts/` — 26 Python scripts

All scripts are thin wrappers that delegate to `src/llm_wiki/` modules.

| File | Lines | Purpose |
|------|-------|---------|
| `scaffold.py` | 330 | Bootstrap new wiki — `--template` picks from 20 domain templates, `--force` overwrites |
| `ingest.py` | 233 | Thin wrapper — delegates to `llm_wiki.ingest.pipeline` |
| `lint_wiki.py` | 557 | Thin wrapper — delegates to `llm_wiki.quality.lint` |
| `deep_research.py` | 209 | Agent-driven research — web search, source fetch, auto-ingest, synthesis page |
| `discover.py` | 350 | Thin wrapper — delegates to `llm_wiki.core.layout` |
| `graph_insights.py` | 240 | Pure Python wikilink graph analysis — community detection, surprising connections, knowledge gaps |
| `link_suggest.py` | 351 | Suggest missing wikilinks — entity extraction, 4-signal scoring, `--apply` auto-add |
| `backup.py` | 411 | Snapshot, restore, integrity verification, prune — `--auto` one-command safe state |
| `benchmark.py` | ~280 | Performance benchmarks — synthetic wikis at 10/100/500/1000/5000 pages, CSV output |
| `audit_review.py` | 147 | Group open/resolved audit files by target for processing |
| `migrate_log.py` | 117 | Convert v1 log.md to v2 log/ directory format |
| `health_check.py` | — | Thin wrapper — delegates to `llm_wiki.ops.health` |
| `index_wiki.py` | — | Thin wrapper — delegates to `llm_wiki.search` (FTS5 index build/rebuild) |
| `serve.py` | — | Thin wrapper — delegates to `llm_wiki.ops.serve` (MCP server entry) |
| `sidecar.py` | — | Python sidecar used by the MCP server (long-lived process; `ask` RPC, v0.6.0) |
| `setup.py` | — | Thin wrapper — `llm-wiki setup` one-command client wiring (LWM_035) |
| `demo.py` | — | Thin wrapper — `llm-wiki demo` materialize the committed playground (LWM_036) |
| `ask.py` | — | Thin wrapper — grounded QA over summaries + pages (LWM_033) |
| `contradictions.py` | — | Thin wrapper — contradiction detection + evidence confidence (LWM_034) |
| `atomic_write.py`, `content_hash.py`, `lock_wiki.py`, `wiki_logging.py` | — | Shared primitives delegated to `core/` |
| `louvain.py` | — | Thin wrapper — delegates to `llm_wiki.graph.louvain` |
| `regenerate_fixtures.py` / `validate_fixtures.py` | — | Fixture regeneration / validation used by CI |
| `providers/` | — | LLM provider wrapper scripts |

---

## `src/llm_wiki/` — Python Package (core)

PyPI package — CLI dispatch (`cli.py`), 27 commands via `COMMANDS`, domain-organized packages. All skill scripts delegate here.

| Module | Purpose |
|------|---------|
| `cli.py` | Unified CLI entry — `COMMANDS` dict (27 commands) + aliases, dispatches to module `main()` |
| `setup/` | `llm-wiki setup` — scaffold/validate + idempotent MCP client wiring (claude/codex/opencode/hermes), `--dry-run`/`--uninstall` (LWM_035/ADR-0031) |
| `wiki/demo.py` + `wiki/demo_wiki/` | `llm-wiki demo` — materialize the committed Redis-Internals playground fixture (8 pages, lint-clean, deterministic) from the package or repo (LWM_036) |
| `graph/ask.py` | `llm-wiki ask` — grounded QA: hybrid retrieval + summary-aware rerank, faithfulness contract, `--no-llm` offline mode (LWM_033/ADR-0029) |
| `graph/extract.py` | Pluggable entity extractor — regex default, optional GLiNER `[ner]` backend with fail-soft degradation (LWM_026) |
| `graph/resolve.py` | Entity-resolution pipeline — normalize → block → two-signal score → merge (LWM_025/ADR-0024) |
| `graph/alias_store.py` | Reversible canonical↔alias store — append-only JSONL source of truth + additive `.index/wiki.db` alias tables with `alias_meta` guard |
| `graph/entities.py` | `llm-wiki entities resolve/list/unmerge` CLI |
| `graph/leiden.py` | Optional Leiden community engine (`[leiden]` extra) + hierarchical levels seam (LWM_027) |
| `graph/derived_edges.py` | Quarantined derived-edge layer — similar_to + co_occurs_with, NMI+modularity fail-closed gate (LWM_029/ADR-0027) |
| `graph/summarize.py` | `llm-wiki summarize-communities` — hierarchical community summaries as first-class pages, faithfulness filtering (LWM_030) |
| `graph/suggest.py` / `louvain.py` / `insights.py` / `alias_store.py` | Link suggestions, Louvain communities, insights, alias persistence |
| `quality/contradictions.py` | `llm-wiki contradictions` — typed claim extractor + suggest-only detector + evidence-grounded confidence (author-overridable `confidence_source`), unit normalization (LWM_034/ADR-0030) |
| `quality/claims/` | Claims subsystem reused by contradictions — `Claim`/`Contradiction` models + `.llm-wiki/claims/` JSONL sidecar (`ClaimsManager`, idempotent batch writers) |
| `semantic/ner_onnx.py` | Torch-free GLiNER ONNX runner — onnxruntime-direct decode, `LLM_WIKI_GLINER_MODEL` cache, never imports gliner/torch (LWM_037/ADR-0032) |
| `core/config.py` | Canonical `TuningConfig` — all 22 constants + type-affinity matrix + signal scores (LWM_031/ADR-0028) |
| `core/tuning.py` | `llm-wiki tuning` CLI — resolve/precedence/`--set`/`--emit` to graph-engine JSON |
| `eval/er_metrics.py` | Pairwise merge precision/recall/F1 (ER-F1 gate, LWM_025) |
| `eval/cluster_metrics.py` | Community NMI/modularity metrics (Leiden verification, LWM_027) |
| `eval/search_baseline.py` | Search-eval harness — goldset splits, hybrid/keyword baseline, `search_eval_gate` (LWM_032) |
| `eval/ask_baseline.py` | Ask-eval harness — ask goldset splits, citation precision@k baseline + fail-on-drop (LWM_033) |
| `eval/contradiction_baseline.py` | Contradiction + confidence gold-wiki builder and gates (LWM_034) |
| `eval/goldset.py` / `baseline.py` / `metrics.py` / `harness.py` / `cli.py` | Eval harness core — gold-set load/splits, committed baselines, `llm-wiki eval` CLI |

---

## `tests/` — Python Test Suite

pytest. Run from the repo root with `PYTHONPATH=src`.

| File / Dir | Purpose |
|------|---------|
| `tests/eval/gold/` | Committed gold sets: `er_goldset.json` (ER, disjoint tune/gate), `search_goldset.json`, `split_manifest.json` (SHA256 freeze), `GOLD_SET.md`, `growth_meta.json` (grow-or-justify record, LWM_039), `ask_goldset.json` (LWM_033), `contradiction_goldset.json` + `confidence_goldset.json` (LWM_034) |
| `tests/eval/baseline/` | Committed gate baselines: `er_baseline.json`, `search_eval_baseline.json`, `eval_baseline.json`, `tuning_defaults.json`, `ask_baseline.json` (LWM_033), `contradiction_baseline.json` + `confidence_baseline.json` (LWM_034) |
| `tests/eval/test_derived_edge_nmi_gate.py` | Derived-edge NMI+modularity gate — inclusion/refusal, fail-closed (LWM_029) |
| `tests/eval/test_search_goldset_integrity.py` | Goldset disjointness, manifest SHA256 freeze, query→pages labels (LWM_032) |
| `tests/eval/test_real_wiki_gate.py` | Real-wiki gate lane with the real `[semantic]` embedder (CI `semantic` job only) |
| `tests/test_setup.py` | `llm-wiki setup` — dry-run-writes-nothing, per-client idempotency + no-clobber, uninstall round-trip, no-secrets (LWM_035) |
| `tests/test_demo.py` | `llm-wiki demo` — fixture lint-clean, byte-identical copy minus caches, no symlinks, `--force` (LWM_036) |
| `tests/test_ask.py` + `tests/test_ask_eval.py` | Grounded ask — citations real pages, `--no-llm` zero calls, hallucination rejected, keyword fallback byte-identical, agent-native $0.00, goldset baseline fail-on-drop (LWM_033) |
| `tests/test_contradictions.py` + `tests/test_contradiction_eval.py` + `tests/test_confidence_eval.py` | Claim extraction deterministic, suggest-only/apply/unapply round-trip, lint pattern, unit normalization, contradiction + confidence goldset gates (LWM_034) |
| `tests/test_recommended_extra.py` | `[recommended]` extra resolves to semantic+leiden+entity-resolution and never imports gliner/torch (LWM_037) |
| `tests/test_gliner_local_path.py` | Torch-free ONNX runner — skip-gated local success path + fake-session decode (LWM_037) |
| `tests/test_curate_gold_set.py` | Standing gold-set curation loop — hygiene check, freeze, rebaseline, growth record (LWM_039 §A) |
| `tests/test_cross_platform_edge.py` | Cross-platform edge suite — symlink paths, CRLF, cp1252, atomic writes, UTF-8 stdio (LWM_039 §X) |
| `tests/test_entity_resolution.py` | Normalization, blocking (sub-quadratic), two-signal rule, reversibility, alias-meta guard (LWM_025) |
| `tests/test_er_eval.py` | ER-F1 fail-on-drop gate + must-not-merge negatives + GLiNER-holds-ER-F1 (LWM_025/026) |
| `tests/test_extract.py` | Extractor import-safety, regex baseline, GLiNER fail-soft, no-download base path (LWM_026) |
| `tests/test_leiden.py` | Leiden selector, hierarchy seam, NMI/modularity vs Louvain (LWM_027) |
| `tests/test_communities_internally_connected.py` | Connectivity over `tests/fixtures/graphs/*.json` — Louvain + Leiden |
| `tests/test_derived_edges.py` | Derived-layer persistence, default exclusion, wikilink dupes, gate (LWM_029) |
| `tests/test_community_summaries.py` | Summaries — dry-run, idempotence, hierarchy, faithfulness, orphan cleanup (LWM_030) |
| `tests/test_tuning_config.py` + `test_tuning_config_defaults.py` | All 22 constants + matrix + signal scores configurable; defaults golden snapshot (LWM_031) |
| `tests/test_search_hybrid.py` / `test_search_eval_gate.py` / `test_search_baseline_reproducible.py` | Hybrid default, RRF, keyword escape hatch, gibberish→empty, gate fail-closed, baseline reproducibility (LWM_032) |
| `tests/test_eval_regression.py` | Committed-baseline regression — lexical, derived-edge gate, summary faithfulness |
| `tests/test_edge_schema.py` | Additive edge fields inert on the Python default path; partition stable (LWM_028) |
| `tests/test_verification.py` + `tests/verification/run_verification.py` | Community verification suite — NMI/ARI across seeds |
| `tests/fixtures/graphs/*.json` | Topology fixtures (barbell, ring_of_cliques, sbm, star, …) for community verification |
| `tests/` others | ingest, lint, concurrency, link-suggest, scaffold, MCP transcripts/benchmark, semantic, claims, docs-examples, CLI snapshots |

---

## `mcp-server/` — Standalone MCP Server

TypeScript. 15 MCP tools via stdio transport. Single-wiki (`--wiki`) or multi-wiki (`--projects`) mode.

| File | Purpose |
|------|---------|
| `package.json` | Dependencies: `@modelcontextprotocol/sdk` |
| `tsconfig.json` | TypeScript config — ES2022, strict mode |
| `src/main.ts` | Main server — 15 tool handlers, JSON-RPC via stdio |
| `src/registry.ts` | Tool registry — 15 TOOL_DEFINITIONS with schemas and handler mappings |
| `src/types.ts` | Shared types: WikiProject, FileNode, SearchResult, ReviewItem, GraphNode, LintIssue |
| `src/wiki-fs.ts` | Filesystem adapter — list, read, write, find, fileExists, ensureDir |
| `src/search.ts` | BM25 search engine — pure TypeScript, no dependencies, ranked results with snippets |
| `src/review.ts` | Bidirectional review system — create, list, resolve, getOpenForFile |
| `src/lint.ts` | Sidecar bridge to quality.lint — delegates via PythonSidecar (not subprocess) |
| `src/graph.ts` | Sidecar bridge to graph-engine — build, insights, search via PythonSidecar |
| `src/storage.ts` | TTL-based cache layer — raw/.cache/<key>.json with expiry |
| `src/cleanup.ts` | Soft cascade cleanup — strip source refs on deletion, report orphans |
| `src/discover.ts` | Sidecar bridge to core.layout — delegates via PythonSidecar, typed fallback |
| `src/tools/` | 15 tool handler modules — one file per MCP tool (incl. `ask.ts` for `llm_wiki_ask`, LWM_033) |
| `src/adapters/` | Adapter layer — sidecar.ts (PythonSidecar), fts5.ts, graph-engine.ts |
| `src/projects/` | Multi-project support — workspace scanning and project management |
| `src/security/` | Security middleware — path traversal prevention, input validation |

---

## `graph-engine/` — Knowledge Graph Engine

TypeScript. Relevance model, Louvain communities, graph insights.

| File | Purpose |
|------|---------|
| `package.json` | Dependencies: `graphology`, `graphology-communities-louvain` |
| `tsconfig.json` | TypeScript config — ES2022, strict mode |
| `src/types.ts` | Shared types: GraphNode, GraphEdge, CommunityInfo, SurprisingConnection, KnowledgeGap |
| `src/build.ts` | Wiki markdown → graph construction — frontmatter parsing, wikilink extraction, node/edge building |
| `src/relevance.ts` | 4-signal relevance model — direct links (3.0), source overlap (4.0), Adamic-Adar (1.5), type affinity (1.0) |
| `src/louvain.ts` | Louvain community detection via graphology — cohesion scoring, top nodes, sequential renumbering |
| `src/insights.ts` | Surprising connections (cross-community, peripheral-to-hub) + knowledge gaps (isolated, sparse, bridge) |
| `src/search.ts` | Token-based graph filtering — match nodes by label/id/type/path |
| `src/index.ts` | CLI wrapper + public API — `--action build|insights|search|relevance`, JSON output; `--tuning-json` consumes the Python-emitted tuning profile |
| `test/tuning-parity.test.ts` | TS-resolved tuning options == Python-resolved profile (non-default + default golden) |
| `test/test_edge_schema.test.ts` | Edge dedup key (undirected byte-identical / directed opt-in), optional-field round-trip, golden build-through snapshot |
| `test/fixtures/graph-data.golden.json` | Golden graph build output — byte-identity freeze through `build` (AD-15) |

---

## `templates/` — 20 Domain Templates

Each template directory contains:

| File | Purpose |
|------|---------|
| `PURPOSE.md` | Domain-specific project purpose, scope, success criteria |
| `SCHEMA.md` | Page types, naming conventions, frontmatter rules, cross-referencing → becomes CLAUDE.md |
| `extra-dirs.json` | JSON array of additional wiki/ subdirectories |

### Template index

| Template | Extra Directories | Use Case |
|----------|-------------------|----------|
| `research/` | methodology, findings, thesis | General research deep-dive |
| `codebase/` | architecture, modules, apis, decisions | Software/quant dev projects |
| `finance/` | markets, instruments, strategies, reports | Financial research, market analysis |
| `algorithmic-trading/` | strategies, backtests, indicators, risk, modules | Quant strategies, backtests |
| `algorithmic-trading-mql4/` | architecture, decisions, graphs | MQL4/5 trading projects with source code |
| `cybersecurity/` | vulnerabilities, exploits, tools, advisories | Security audits, vuln research |
| `machine-learning/` | models, datasets, experiments, benchmarks | ML training, fine-tuning |
| `prompt-engineering/` | techniques, evaluations, templates, providers | Prompt research |
| `copywriting/` | copy, frameworks, personas, campaigns | Copy research, swipe files |
| `marketing/` | channels, campaigns, analytics, competitors | Marketing strategy |
| `design-systems/` | tokens, components, patterns, guidelines | Design tokens, components |
| `architecture/` | diagrams, services, infrastructure, decisions | System architecture, ADRs |
| `crypto/` | protocols, tokens, defi, regulations | Cryptocurrency research |
| `commodities/` | metals, energy, agriculture, correlations | Commodity markets |
| `decompilers/` | formats, opcodes, tools, findings | Reverse engineering, EX4 |
| `medicine/` | conditions, treatments, studies, terminology | Medical research |
| `developer-tools/` | tools, workflows, benchmarks, integrations | Dev tool comparisons |
| `personal-growth/` | goals, habits, reflections, journal | Personal development |
| `reading/` | characters, themes, plot-threads, chapters | Book reading companion |
| `business/` | meetings, decisions, projects, stakeholders | Team wiki, ADRs |
| `_shared/` | base-schema.md | Shared template primitives |

---

## `web-viewer/` — Local Preview Server

Express + markdown-it + KaTeX + mermaid. Search bar + graph insights panel.

| File | Purpose |
|------|---------|
| `package.json` | Dependencies and build scripts (incl. sigma + graphology, LWM_038) |
| `server/index.ts` | Express server entry point |
| `server/config.ts` | Server configuration |
| `server/render/markdown.ts` | Markdown rendering with KaTeX |
| `server/render/wikilinks.ts` | Wikilink resolution |
| `server/routes/pages.ts` | Page serving |
| `server/routes/graph.ts` | Graph data + graph-insights API |
| `server/routes/derived.ts` | Derived-edge overlay API — reads `.index/derived-edges.json`, resolves stems→ids, `layer:"derived"` (LWM_038/ADR-0033) |
| `server/routes/exports.ts` | JSON Canvas 1.0 + JSON-LD exports of the graph (layer-labeled) (LWM_038) |
| `server/routes/search.ts` | TF-based search API — tokenizes, scores, returns ranked results |
| `server/routes/audit.ts` | Audit CRUD API |
| `server/routes/tree.ts` | File tree API |
| `client/index.html` | SPA entry point with tabs (Pages/Search/Graph) |
| `client/main.ts` | Client-side app — search, tab switching, graph loading, derived-edge toggle (off by default) + SVG|WebGL view switch |
| `client/graph.ts` | Graph visualization (d3-force SVG renderer + derived-edge overlay renderer) |
| `client/sigma-view.ts` | Sigma.js WebGL graph view (zoomable/panable, SVG fallback) (LWM_038) |
| `client/feedback.ts` | Selection → audit feedback |

---

## `extension/` — Browser Extension

Chrome Manifest V3 web clipper. Uses Readability.js + Turndown.js. Optional auto-ingest after clip.

| File | Purpose |
|------|---------|
| `manifest.json` | Extension manifest |
| `popup.html` | Popup UI |
| `popup.js` | Clip logic — extract + save to wiki |
| `Readability.js` | Mozilla's readability extraction |
| `Turndown.js` | HTML → Markdown conversion |

---

## `audit-shared/` — Shared Audit Library

TypeScript library for audit file format. Used by web-viewer and obsidian-audit plugin.

| File | Purpose |
|------|---------|
| `src/schema.ts` | Audit entry Zod schema |
| `src/anchor.ts` | Text-based anchor algorithm |
| `src/id.ts` | Audit ID generation |
| `src/serialize.ts` | YAML frontmatter serialization |

---

## `plugins/obsidian-audit/` — Obsidian Plugin

Select text → file feedback → writes to audit/. Shares audit-shared with web-viewer.

| File | Purpose |
|------|---------|
| `src/main.ts` | Plugin entry — commands, settings |
| `src/settings.ts` | Plugin settings tab |
| `src/writer.ts` | Audit file writer |
| `src/feedback-modal.ts` | Feedback input modal |
| `manifest.json` | Obsidian plugin manifest |

---

## `rust-backend/` — Document Parsing (Coming Soon)

Multi-format document parsing (PDF, DOCX, EPUB) — planned for future implementation.

*(Directory removed — was an empty stub.)*
