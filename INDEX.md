# INDEX.md — Complete File Map

Every file in the llm-wiki-monorepo, organized by package with descriptions.

## Root

| File | Purpose |
|------|---------|
| `README.md` | Project overview, quick start, architecture |
| `QUICKGUIDE.md` | Hands-on command reference with examples |
| `INDEX.md` | This file — complete file tree |
| `AGENTS.md` | Architecture and conventions for AI agents |
| `PURPOSE.md` | Why this system exists, core principles, success criteria |
| `VERSIONING.md` | Semantic versioning policy and release process |
| `install.sh` | One-command install — detects deps, builds, creates wrappers |
| `package.json` | NPM workspace root — scripts for build/test/run |
| `.gitignore` | Git ignore rules |
| `.github/workflows/ci.yml` | GitHub Actions CI — syntax checks, builds, integration tests |

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

### `skill/scripts/` — 13 Python scripts

| File | Lines | Purpose |
|------|-------|---------|
| `scaffold.py` | 330 | Bootstrap new wiki — `--template` picks from 19 domain templates, `--force` overwrites |
| `ingest.py` | 233 | Two-step chain-of-thought ingest — Stage 1 analysis + Stage 2 generation with SHA256 caching |
| `lint_wiki.py` | 557 | 15-pass automated health check with auto-discovered layout — dead links, orphans, frontmatter, staleness, source drift |
| `deep_research.py` | 209 | Agent-driven research — web search, source fetch, auto-ingest, synthesis page |
| `discover.py` | 350 | Auto-discover wiki structure — pages, sources, logs, audits, page types, frontmatter conventions |
| `graph_insights.py` | 240 | Pure Python wikilink graph analysis — community detection, surprising connections, knowledge gaps |
| `link_suggest.py` | 351 | Suggest missing wikilinks — entity extraction, 4-signal scoring, `--apply` auto-add |
| `backup.py` | 411 | Snapshot, restore, integrity verification, prune — `--auto` one-command safe state |
| `benchmark.py` | ~280 | Performance benchmarks — synthetic wikis at 10/100/500/1000/5000 pages, CSV output |
| `audit_review.py` | 147 | Group open/resolved audit files by target for processing |
| `migrate_log.py` | 117 | Convert v1 log.md to v2 log/ directory format |
| `test_ingest_blocks.py` | ~150 | Unit test for FILE/REVIEW block parsing in ingest.py |
| `test_ingest_e2e.py` | ~350 | End-to-end multi-step agent loop integration test for ingest.py |

---

## `mcp-server/` — Standalone MCP Server

TypeScript. 8 MCP tools via stdio transport. Single-wiki (`--wiki`) or multi-wiki (`--projects`) mode.

| File | Purpose |
|------|---------|
| `package.json` | Dependencies: `@modelcontextprotocol/sdk` |
| `tsconfig.json` | TypeScript config — ES2022, strict mode |
| `src/index.ts` | Main server — 8 tool handlers, JSON-RPC via stdio |
| `src/types.ts` | Shared types: WikiProject, FileNode, SearchResult, ReviewItem, GraphNode, LintIssue |
| `src/wiki-fs.ts` | Filesystem adapter — list, read, write, find, fileExists, ensureDir |
| `src/search.ts` | BM25 search engine — pure TypeScript, no dependencies, ranked results with snippets |
| `src/review.ts` | Bidirectional review system — create, list, resolve, getOpenForFile |
| `src/lint.ts` | Bridge to lint_wiki.py — subprocess call with structured output parsing + TS fallback |
| `src/graph.ts` | Bridge to graph-engine — build, insights, search via subprocess |
| `src/storage.ts` | TTL-based cache layer — raw/.cache/<key>.json with expiry |
| `src/cleanup.ts` | Soft cascade cleanup — strip source refs on deletion, report orphans |
| `src/discover.ts` | TypeScript bridge to discover.py — calls Python discover module, typed fallback |

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
| `src/index.ts` | CLI wrapper + public API — `--action build|insights|search|relevance`, JSON output |

---

## `templates/` — 19 Domain Templates

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
| `package.json` | Dependencies and build scripts |
| `server/index.ts` | Express server entry point |
| `server/config.ts` | Server configuration |
| `server/render/markdown.ts` | Markdown rendering with KaTeX |
| `server/render/wikilinks.ts` | Wikilink resolution |
| `server/routes/pages.ts` | Page serving |
| `server/routes/graph.ts` | Graph data + graph-insights API |
| `server/routes/search.ts` | TF-based search API — tokenizes, scores, returns ranked results |
| `server/routes/audit.ts` | Audit CRUD API |
| `server/routes/tree.ts` | File tree API |
| `client/index.html` | SPA entry point with tabs (Pages/Search/Graph) |
| `client/main.ts` | Client-side app — search, tab switching, graph loading |
| `client/graph.ts` | Graph visualization |
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
