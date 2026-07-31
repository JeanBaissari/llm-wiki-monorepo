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

## What is this?

LLM Wiki is a **production-grade knowledge engine** that turns raw documents into a living, cross-linked Markdown wiki. Instead of re-retrieving documents on every query (RAG), the system **incrementally builds and maintains** a persistent knowledge base. Sources are compiled once, kept current, and compound over time.

It's everything needed to run a self-building wiki in one monorepo: a Python CLI package, an MCP server, a knowledge graph engine with community detection, a Chrome web clipper, a web viewer, an Obsidian plugin, and 20 domain templates — wired through an agent skill that works with any LLM.

---


## Features

- **Two-Step Ingest** — LLM analyzes sources first, then generates structured wiki pages. SHA256 caching skips unchanged files. Streaming progress, multi-provider support (OpenAI, Anthropic, DeepSeek), and agent-native mode that needs zero API keys.

- **Agent-Native Provider** — route ingest through Hermes, Claude Code, or Codex directly. No external API keys required when running inside an AI agent session.

- **Structured Output** — Pydantic-typed parsing via instructor. No regex guesswork. Retry with exponential backoff on transient failures. Token counting and cost estimation per operation.

- **Concurrency Control** — per-page advisory locking, atomic writes (temp → fsync → rename), SHA256 conflict detection, and three-tier conflict management with automatic cleanup. Multiple agents can safely operate on the same wiki.

- **Knowledge Graph Engine** — Louvain community detection with full Blondel et al. modularity. 4-signal relevance model with precomputed adjacency. Surprising connection discovery and knowledge gap detection. Pure Python fallback included.

- **15-Pass Automated Lint** — dead links, orphans, frontmatter validation, contradictions, source drift, unresolved conflicts, and stale page detection when raw sources change.

- **SQLite FTS5 Search** — full-text search with SHA256 freshness detection. Pre-builds at startup, incremental updates, BM25 fallback. Rebuild with `--rebuild`.

- **Inverted Entity Index** — dual-map entity→pages + page→entities for O(1) link suggestions. 4-signal scoring with automatic wikilink insertion.

- **MCP Server** — 14 stdio tools for programmatic wiki access. Direct Python sidecar with zero subprocess overhead. Integrates with Claude Desktop, Codex, Cursor, and any MCP-compatible client.

- **Community Verification Suite** — NMI/ARI cross-validation across 5 seeds, statistical similarity metrics, modularity tolerance within 1% relative error.

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

# Start MCP server (14 tools via stdio)
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
      ├── MCP Server (stdio)              → 14 tools, modular: tools/,
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
| `skill/` | Python + Markdown | adapter | Agent skill (8 operations) + 20+ scripts + 12 reference docs |
| `src/llm_wiki/` | Python | core | PyPI package — CLI, LLM providers, concurrency, search, graph insights |
| `mcp-server/` | TypeScript | programmatic-access | MCP server — 14 tools, direct sidecar integration |
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
| `docs/reference/cli.md` | Full CLI reference — all 15 commands with flags and examples |
| `docs/reference/mcp-tools.md` | All 14 MCP tools with schemas and usage examples |
| `AGENTS.md` | Architecture, conventions, build/test commands, Python Dependency Policy |
| `docs/release/changelog.md` | Full version history — all features, changes, and breaking changes |
| `docs/reference/file-map.md` | Complete file tree with descriptions |
| `docs/release/versioning.md` | Semantic versioning policy and release process |
| `docs/architecture/overview.md` | Why this system exists — design philosophy and goals |
| `docs/adr/` | Architecture Decision Records — 14 design decisions with tradeoffs |
| `skill/references/` | 12 detailed reference guides including concurrency, observability, and ingest |

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

- **`graph-engine/src/relevance.ts`** — Contains code ported from `nashsu/llm_wiki` (GPL-3.0). See [docs/legal/provenance.md](./docs/legal/provenance.md) for disposition status.
- **`graph-engine/src/insights.ts`** — Contains code ported from `nashsu/llm_wiki` (GPL-3.0). See [docs/legal/provenance.md](./docs/legal/provenance.md) for disposition status.
- **`graph-engine/src/louvain.ts`** — Implements the Louvain community detection algorithm (Blondel et al. 2008) via the MIT-licensed `graphology-communities-louvain` library.

### Related Projects

- [nashsu/llm_wiki](https://github.com/nashsu/llm_wiki) — Cross-platform Tauri desktop app with graph visualization, vector search, and rich chat interface. Licensed GPL-3.0.
- [anzal1/quicky-wiki](https://github.com/anzal1/quicky-wiki) — MIT-licensed CLI/dashboard for claim extraction, confidence scoring, and metabolism.

### Upstream License Notice

This project may include code derived from GPL-3.0-licensed upstream sources (`graph-engine/src/relevance.ts`, `graph-engine/src/insights.ts`). A **provenance review** is required before public release. See [CONTRIBUTING.md](./CONTRIBUTING.md#release-blocker-gpl-provenance-review) and the full [docs/legal/provenance.md](./docs/legal/provenance.md) ledger for details.

## License

MIT
