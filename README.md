# LLM Wiki Monorepo

<p align="center">
  <strong>Agent-native knowledge compiler.</strong><br>
  AI agents turn raw documents into persistent, cross-linked Markdown wikis.<br>
  No database. No API lock-in. One <code>git clone</code>.
</p>

<p align="center">
  <a href="#what-is-this">What</a> •
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#packages">Packages</a> •
  <a href="#templates">Templates</a> •
  <a href="#documentation">Docs</a> •
  <a href="#credits">Credits</a> •
  <a href="#license">License</a>
</p>

<p align="center">
  <a href="https://github.com/JeanBaissari/llm-wiki-monorepo/actions/workflows/ci.yml"><img src="https://github.com/JeanBaissari/llm-wiki-monorepo/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/baissarienterprises-llm-wiki/"><img src="https://img.shields.io/pypi/v/baissarienterprises-llm-wiki.svg" alt="PyPI"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+"></a>
  <a href="https://nodejs.org"><img src="https://img.shields.io/badge/node-18+-green.svg" alt="Node 18+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-yellow.svg" alt="License MIT"></a>
  <a href="https://deepwiki.com/JeanBaissari/llm-wiki-monorepo"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"></a>
</p>

---

```bash
pip install baissarienterprises-llm-wiki
```

## What's New in v0.3.0

**Modular architecture.** The Python package has been reorganized from 28 flat modules into 10 domain-organized packages — `core/`, `quality/`, `ingest/`, `providers/`, `graph/`, `search/`, `ops/`, `wiki/`, `research/`, `contracts/`. Every module now answers: what domain owns this? What category within that domain? What specific function?

**MCP server modularized.** The 1,287-line `index.ts` is gone. The MCP server is now 20 focused files: per-tool handlers under `tools/`, adapters under `adapters/`, project scanning under `projects/`, path safety under `security/`. All 14 tool names, schemas, and responses preserved byte-for-byte.

**Shared TypeScript types.** Canonical `GraphNode`/`GraphEdge` types extracted into `packages/shared-types/` — a single source of truth for 3 packages that previously defined near-identical interfaces independently.

**Documentation taxonomy.** Root-level docs reorganized into `docs/architecture/`, `docs/getting-started/`, `docs/reference/`, `docs/legal/`, `docs/release/`. README.md and AGENTS.md kept at root for PyPI packaging and AI agent auto-discovery.

**7 pre-existing test failures eliminated.** OpenCode imports fixed. MCP integration tests now match the sidecar response schema. Link suggest optimization added. 472 tests pass (up from 445).

## What's New in v0.6.0 — "Epistemic & Surface"

**One-command setup.** `llm-wiki setup <root> [--title]` scaffolds/validates a wiki and registers the MCP server with every detected client — claude, codex, opencode, hermes — idempotently, with `--dry-run`/`--uninstall` and a health + `tools/list` smoke test (LWM_035).

**Ask this wiki.** `llm-wiki ask <root> "<question>"` answers questions grounded in the wiki — hybrid retrieval over pages + community summaries with a summary-aware rerank, exactly one structured LLM call on the agent-native `$0.00` default, a `--no-llm` deterministic offline mode, and a faithfulness contract (answer entities ⊆ cited pages). MCP `llm_wiki_ask` included (LWM_033).

**Contradictions + evidence confidence.** `llm-wiki contradictions <root> detect|list|apply|unapply` extracts typed claims, detects contradictions (unit-normalized numerics, polarity, exclusive categories) suggest-only, and computes evidence-grounded confidence (high/medium/low + `evidence_score`) into the `confidence`/`contested`/`contradictions` frontmatter fields — author-overridable via `confidence_source: evidence|author` (LWM_034).

**Demo wiki.** `llm-wiki demo <dest>` materializes a committed, lint-clean "Redis Internals" playground (8 pages) from the installed package or repo, in one command (LWM_036).

**Recommended extras + GLiNER local path.** `pip install -e ".[recommended]"` = `semantic` + `leiden` + `entity-resolution`; `[ner]` gains a documented torch-free ONNX model-cache path with a measured disk budget (LWM_037).

**Web-viewer derived overlay + Sigma.js + exports.** The quarantined derived layer renders as an off-by-default dashed overlay (byte-identical when off), with a Sigma.js WebGL view and JSON Canvas / JSON-LD exports — web-viewer-only diff, no backend change (LWM_038).

**Standing gold-set curation.** `scripts/curate_gold_set.py` + a release-certify `gate_search_goldset_fresh` gate make per-minor gold-set growth a procedure, not a decision (LWM_039 §A).

## What's New in v0.5.0 — "Graph Precision"

**Entity resolution.** `llm-wiki entities resolve|list|unmerge` collapses variant surface forms ("GPT-4" / "GPT 4" / "gpt-4") into one canonical id through a reversible canonical↔alias table (JSONL source of truth + additive SQLite alias tables). Every merge is reversible; no page prose is ever rewritten. ER-F1 on a committed gold set gates it (ADR-0024).

**Leiden community detection.** Optional `[leiden]` sidecar (graspologic) with hierarchical levels — guaranteed-connected communities, NMI/modularity verification against Louvain, TS still only consumes (no TS Leiden, ADR-0025).

**Typed + directed + bitemporal edges.** One additive edge-schema evolution (`relType`/`directed`/`validFrom`/`validTo`/`observedAt`) — the undirected default output is byte-identical (ADR-0026).

**Derived edges, quarantined.** The graph discovers similarity + co-occurrence edges into a separate layer, excluded from all analytics by default and included only when the NMI+modularity gate passes (fail-closed, ADR-0027).

**Hierarchical community summaries.** `llm-wiki summarize-communities` writes first-class `community-summary` pages per community level + a global summary, with faithfulness filtering and stale-page cleanup (LWM_030).

**Tuning constants → config.** Every precision constant (relevance weights + type-affinity matrix, insights thresholds + signal scores, community resolution/seed, RRF k, BM25 k1/b, claim penalties — 52 settable keys) lives in one canonical `TuningConfig` surfaced by `llm-wiki tuning` with CLI > env > file > default precedence, emitted to the graph-engine via `--tuning-json` (ADR-0028).

**Hybrid search is the default.** Search fuses BM25 + semantic KNN via RRF by default, degrades to keyword byte-identically without the `[semantic]` extra, and keeps `--keyword` as the escape hatch — certified by a committed search gold set + gate (ADR-0020).

## What is this?

LLM Wiki is a **production-grade knowledge engine** that turns raw documents into a living, cross-linked Markdown wiki. Instead of re-retrieving documents on every query (RAG), the system **incrementally builds and maintains** a persistent knowledge base. Sources are compiled once, kept current, and compound over time.

It's everything needed to run a self-building wiki in one monorepo: a Python CLI package, an MCP server, a knowledge graph engine with community detection, a Chrome web clipper, a web viewer, an Obsidian plugin, and 20 domain templates — wired through an agent skill that works with any LLM.

---

## Five ways to run this

One repo, five entry surfaces — all reading and writing the same `wiki/` directory. Pick the one that fits your setup.

### 1. CLI (Python package)

```bash
pip install baissarienterprises-llm-wiki
llm-wiki search ~/my-wiki "attention"
```

Scripts, CI, and humans get the full command surface — run `llm-wiki <command> --help` to explore. See the [CLI reference](docs/reference/cli.md).

### 2. MCP server (any MCP client)

```bash
npx llm-wiki-mcp --wiki ~/my-wiki
claude mcp add llm-wiki -- npx llm-wiki-mcp --wiki ~/my-wiki
```

Programmatic wiki access for any MCP client (Claude, Codex, Cursor, opencode) via 15 stdio tools. Register it with `claude mcp add`, the opencode `.mcp.json` form, or `llm-wiki setup` (one-command wiring, v0.6.0). Requires a built mcp-server: `cd mcp-server && npm run build` (or `bash install.sh`). See the [MCP tools reference](docs/reference/mcp-tools.md).

### 3. Hermes skill (in-conversation agent workflow)

```bash
ln -sf /path/to/llm-wiki-monorepo/skill ~/.hermes/skills/research/llm-wiki
```

Loads the 8-operation skill for Claude/Hermes sessions — agent-native, no API keys needed. See [skill/SKILL.md](skill/SKILL.md).

### 4. Cron / automation

```bash
0 3 * * * cd ~/wikis/my-project && llm-wiki ingest raw/ --provider opencode
```

Schedule maintenance like ingest, lint, or backup. `portalocker` advisory locks make concurrent agent runs safe — multiple agents or CI jobs can operate on the same wiki without corrupting pages. See the [concurrency reference](skill/references/concurrency.md) and the [quickstart](docs/getting-started/quickstart.md).

### 5. Web preview (local browsing)

```bash
llm-wiki serve ~/my-wiki
```

Opt-in local preview server for human browsing (mermaid, KaTeX, audit feedback). Local-only by default — see the [security boundary](docs/operations/security-and-boundaries.md) before exposing it. See the [CLI reference](docs/reference/cli.md).

---


## Features

- **Two-Step Ingest** — LLM analyzes sources first, then generates structured wiki pages. SHA256 caching skips unchanged files. Streaming progress, multi-provider support (OpenAI, Anthropic, DeepSeek), and agent-native mode that needs zero API keys.

- **Agent-Native Provider** — route ingest through Hermes, Claude Code, or Codex directly. No external API keys required when running inside an AI agent session.

- **Structured Output** — Pydantic-typed parsing via instructor. No regex guesswork. Retry with exponential backoff on transient failures. Token counting and cost estimation per operation.

- **Concurrency Control** — per-page advisory locking, atomic writes (temp → fsync → rename), SHA256 conflict detection, and three-tier conflict management with automatic cleanup. Multiple agents can safely operate on the same wiki.

- **Knowledge Graph Engine** — Louvain community detection with full Blondel et al. modularity. 4-signal relevance model with precomputed adjacency. Surprising connection discovery and knowledge gap detection. Pure Python fallback included.

- **15-Pass Automated Lint** — dead links, orphans, frontmatter validation, contradictions, source drift, unresolved conflicts, and stale page detection when raw sources change.

- **SQLite FTS5 Search** — full-text search with SHA256 freshness detection. Pre-builds at startup, incremental updates, BM25 fallback. Rebuild with `--rebuild`.

- **Inverted Entity Index** — dual-map entity→pages + page→entities for O(1) link suggestions. 4-signal scoring with automatic wikilink insertion. Reversible entity resolution (canonical↔alias) collapses duplicate surface forms.

- **MCP Server** — 15 stdio tools for programmatic wiki access. Direct Python sidecar with zero subprocess overhead. Integrates with Claude Desktop, Codex, Cursor, and any MCP-compatible client.

- **Hybrid Search (default)** — BM25 + semantic vector KNN fused via RRF with a `--keyword` escape hatch; degrades to keyword byte-identically without the `[semantic]` extra. Gold-set gate certifies no keyword regression.

- **Tuning Config Surface** — `llm-wiki tuning` exposes every precision constant (relevance weights + type-affinity matrix, insights signal scores, community resolution/seed, RRF k, BM25 k1/b, claim penalties) with CLI > env > file > default precedence and a `--emit` boundary for the graph-engine.

- **Community Verification Suite** — NMI/ARI cross-validation across 5 seeds, statistical similarity metrics, modularity tolerance within 1% relative error. Optional Leiden engine with hierarchical levels (graspologic, `[leiden]` extra).

- **Derived-Edge Layer** — similarity + co-occurrence edges the graph discovers into a separate quarantined layer, excluded from analytics by default and NMI+modularity-gated on inclusion (fail-closed).

- **Hierarchical Community Summaries** — opt-in LLM summaries per community level + global summary as first-class generated pages, with faithfulness filtering and orphan cleanup.

- **Backup & Recovery** — tar.gz snapshots with restore, integrity verification, and automatic pruning. One-command `--auto` for safe state.

- **20 Domain Templates** — research, codebase, finance, machine learning, cybersecurity, medicine, algorithmic trading, and more. Every template ships with PURPOSE.md, SCHEMA.md → CLAUDE.md, and extra-dirs.json.

- **Deep Research** — web search → fetch → ingest → synthesize. Multi-source compilation into structured wiki pages.

- **Chrome Web Clipper** — one-click web page capture with Readability + Turndown, auto-triggering ingest after clip.

- **Claim & Epistemic Tracking** — optional sidecar model: claims, epistemic events (created/reinforced/challenged/weakened/superseded/resolved), and contradiction records with JSONL storage. Health reports and diffs between wiki states.

- **Modular Architecture** — 28 flat modules reorganized into 10 domain packages: `core/` (primitives), `quality/{claims,lint,audit}/`, `ingest/` (pipeline), `providers/` (LLM adapters), `graph/` (louvain, insights, suggestions), `search/` (FTS5), `ops/` (health, serve, benchmark), `wiki/` (scaffold, backup), `research/` (deep-research), `contracts/` (schema validation). MCP server split from 1,287-line monolith into 20 focused files.

- **CI/CD Pipeline** — pytest + vitest matrix across Python 3.10–3.12 and Node 18–22, coverage reporting, trusted OIDC publishing to PyPI on tag push.

## Quick Start

```bash
# Install from PyPI
pip install baissarienterprises-llm-wiki

# Or install from source
git clone https://github.com/JeanBaissari/llm-wiki-monorepo.git
cd llm-wiki-monorepo
bash install.sh

# Scaffold a wiki
llm-wiki scaffold ~/my-wiki "My Research" --template research

# Ingest a source (two-step agent loop)
llm-wiki ingest ~/my-wiki raw/articles/my-source.md

# Use agent-native provider (no API keys — inside Hermes/Claude Code/Codex)
llm-wiki ingest ~/my-wiki raw/articles/my-source.md --llm opencode

# Check quality
llm-wiki lint ~/my-wiki

# Clean up old conflicts automatically
llm-wiki lint ~/my-wiki --clean-conflicts

# Build search index
llm-wiki index ~/my-wiki

# Discover hidden connections
llm-wiki insights ~/my-wiki

# Health check
llm-wiki health ~/my-wiki

# Claim tracking (optional sidecar)
llm-wiki claims health ~/my-wiki

# Start MCP server (15 tools via stdio)
llm-wiki serve ~/my-wiki
```

## Architecture

 ```
 wiki/ directory  ← shared state (Markdown files)
      │
      ├── Agent Skill + Python Scripts   → 20+ scripts: scaffold, ingest, lint,
      │                                     discover, insights, backup, link-suggest,
      │                                     deep-research, audit, benchmark, serve
      ├── Python Package (src/llm_wiki/)  → modular: core/ (primitives),
      │   ├── core/                       quality/ (claims, lint, audit),
      │   ├── quality/                    ingest/ (pipeline), providers/,
      │   ├── ingest/ + providers/        graph/ (louvain, insights),
      │   ├── graph/ + search/            search/ (FTS5), ops/ (health, serve),
      │   ├── ops/ + wiki/ + research/    wiki/ (scaffold, backup),
      │   └── contracts/                  research/ (deep-research)
      ├── MCP Server (stdio)              → 15 tools, modular: tools/,
      │                                     adapters/, projects/, security/
      ├── Graph Engine (Node.js)          → relevance model, Louvain, insights
      ├── shared-types (TS)               → canonical GraphNode/GraphEdge types
      ├── Web Viewer + Obsidian Plugin    → human browsing + feedback
      ├── Browser Extension               → web clipping + auto-ingest
      └── templates/                      → 20 domain schemas
 ```

## Packages

| Package | Language | Tier | Purpose |
|---------|----------|------|---------|
| `skill/` | Python + Markdown | adapter | Agent skill (8 operations) + 20+ scripts + 13 reference docs |
| `src/llm_wiki/` | Python | core | PyPI package — CLI, LLM providers, concurrency, search, graph insights |
| `mcp-server/` | TypeScript | programmatic-access | MCP server — 15 tools, direct sidecar integration |
| `graph-engine/` | TypeScript | analysis | Knowledge graph — relevance, Louvain communities, insights, verification |
| `templates/` | Markdown + JSON | core | 20 domain-specific project templates |
| `tests/` | Python + TypeScript | core | pytest (ingest, lint, concurrency, search, opencode) + vitest (graph, mcp) |
| `web-viewer/` | TypeScript | optional | Preview server with search + graph insights panel |
| `extension/` | JavaScript | optional | Chrome web clipper with auto-ingest |
| `audit-shared/` | TypeScript | core | Shared audit file format library |
| `plugins/obsidian-audit/` | TypeScript | optional | Obsidian plugin — file feedback from vault |
| `graph-bridge/` | TypeScript | adapter | AST extraction + graph merger bridge |
| `packages/shared-types/` | TypeScript | core | Canonical GraphNode/GraphEdge type definitions |

## Templates (20 domains)

`research` `codebase` `finance` `algorithmic-trading` `algorithmic-trading-mql4` `cybersecurity` `machine-learning` `prompt-engineering` `copywriting` `marketing` `design-systems` `architecture` `crypto` `commodities` `decompilers` `medicine` `developer-tools` `personal-growth` `reading` `business`

Every template provides: `PURPOSE.md` (scope + goals), `SCHEMA.md` → `CLAUDE.md` (page types, conventions, frontmatter, cross-referencing, contradiction handling), `extra-dirs.json` (domain directories).

## Documentation

| File | What it covers |
|------|---------------|
| `README.md` | You are here |
| `docs/getting-started/quickstart.md` | Every command with real examples |
| `docs/reference/cli.md` | Full CLI reference — all 27 commands with flags and examples |
| `docs/reference/mcp-tools.md` | All 15 MCP tools with schemas and usage examples |
| `AGENTS.md` | Architecture, conventions, build/test commands, Python Dependency Policy |
| `docs/release/changelog.md` | Full version history — all features, changes, and breaking changes |
| `docs/reference/file-map.md` | Complete file tree with descriptions |
| `docs/reference/tuning.md` | Tuning config surface — every constant, precedence, emit boundary |
| `docs/operations/` | Operations runbooks — hybrid-default search migration note, index |
| `docs/operations/security-and-boundaries.md` | Per-wiki auth/visibility boundary — filesystem + git permissions, no network surface |
| `docs/release/versioning.md` | Semantic versioning policy and release process |
| `docs/architecture/overview.md` | Why this system exists — design philosophy and goals |
| `docs/adr/` | Architecture Decision Records — ADRs 0001–0028 + index + decision register |
| `skill/references/` | 13 detailed reference guides including concurrency, observability, and ingest |

## Requirements

- **Python 3.10+** — for all skill scripts and PyPI package
- **Node.js 18+** — for MCP server, graph engine, web viewer
- **npm** — for TypeScript package management
- **pip dependencies** — openai, anthropic, litellm, instructor, tenacity, tiktoken, python-dotenv, pydantic, portalocker (auto-installed via `pip install`)

## Credits

### Inspirations

The foundational methodology is **inspired by** **Andrej Karpathy**'s [llm-wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) pattern (MIT) — using LLMs to incrementally build and maintain a personal wiki from raw sources. This project is an independent, production-grade implementation with concurrency control, multi-provider LLM support, FTS5 search, MCP integration, and community detection. No code from Karpathy's gist is used.

Additional design patterns and API methodology were informed by [nashsu/llm_wiki](https://github.com/nashsu/llm_wiki) (GPL-3.0) and [nashsu/llm_wiki_skill](https://github.com/nashsu/llm_wiki_skill) (GPL-3.0). Concepts from [anzal1/quicky-wiki](https://github.com/anzal1/quicky-wiki) (MIT) influenced linting and claim-management design.

### Code Derivations

- **`graph-engine/src/relevance.ts`** — 4-signal relevance model with configurable weights, source indexing, and type-safe interfaces. Substantially rewritten in v0.3.3. See [docs/legal/provenance.md](./docs/legal/provenance.md).
- **`graph-engine/src/insights.ts`** — Surprising connection detection and knowledge gap discovery with extensible signal registry. Substantially rewritten in v0.3.3. See [docs/legal/provenance.md](./docs/legal/provenance.md).
- **`graph-engine/src/louvain.ts`** — Implements the Louvain community detection algorithm (Blondel et al. 2008) via the MIT-licensed `graphology-communities-louvain` library.

### Related Projects

- [nashsu/llm_wiki](https://github.com/nashsu/llm_wiki) — Cross-platform Tauri desktop app with graph visualization, vector search, and rich chat interface. Licensed GPL-3.0.
- [anzal1/quicky-wiki](https://github.com/anzal1/quicky-wiki) — MIT-licensed CLI/dashboard for claim extraction, confidence scoring, and metabolism.

### Upstream License Notice

This project was inspired by concepts from GPL-3.0-licensed upstream projects. Code previously derived from `nashsu/llm_wiki` has been substantially rewritten and expanded in v0.3.3 with configurable weights, extensible signal registries, and performance optimizations. See [docs/legal/provenance.md](./docs/legal/provenance.md) for full provenance ledger.

## License

MIT
