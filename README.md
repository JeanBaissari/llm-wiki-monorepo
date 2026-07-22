# LLM Wiki Monorepo

<p align="center">
  <strong>A knowledge base that builds itself.</strong><br>
  AI agents read your documents, build a structured wiki, and keep it current — no database, no API lock-in, one repo.
</p>

<p align="center">
  <a href="#what-is-this">What is this?</a> •
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#packages">Packages</a> •
  <a href="#templates">Templates</a> •
  <a href="#credits">Credits</a> •
  <a href="#license">License</a>
</p>

<p align="center">
  <a href="https://github.com/JeanBaissari/llm-wiki-monorepo/actions/workflows/ci.yml"><img src="https://github.com/JeanBaissari/llm-wiki-monorepo/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+"></a>
  <a href="https://nodejs.org"><img src="https://img.shields.io/badge/node-18+-green.svg" alt="Node 18+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-yellow.svg" alt="License MIT"></a>
  <a href="https://deepwiki.com/JeanBaissari/llm-wiki-monorepo"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"></a>
</p>

---

```bash
pip install baissarienterprises-llm-wiki
```

## What is this?

LLM Wiki is a **production-grade knowledge engine** that turns raw documents into a living, cross-linked Markdown wiki. Instead of re-retrieving documents on every query (RAG), the system **incrementally builds and maintains** a persistent knowledge base. Sources are compiled once, kept current, and compound over time.

It's a monorepo of everything needed to run a self-building wiki: a Python CLI package, an MCP server for programmatic access, a knowledge graph engine with community detection, a Chrome web clipper, a web viewer, an Obsidian plugin, and 20 domain templates — all wired together through an agent skill that works with any LLM.

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

- **MCP Server** — 10 stdio tools for programmatic wiki access. Direct Python sidecar with zero subprocess overhead. Integrates with Claude Desktop, Codex, Cursor, and any MCP-compatible client.

- **Community Verification Suite** — NMI/ARI cross-validation across 5 seeds, statistical similarity metrics, modularity tolerance within 1% relative error.

- **Backup & Recovery** — tar.gz snapshots with restore, integrity verification, and automatic pruning. One-command `--auto` for safe state.

- **19 Domain Templates** — research, codebase, finance, machine learning, cybersecurity, medicine, algorithmic trading, and more. Every template ships with PURPOSE.md, SCHEMA.md → CLAUDE.md, and extra-dirs.json.

- **Deep Research** — web search → fetch → ingest → synthesize. Multi-source compilation into structured wiki pages.

- **Chrome Web Clipper** — one-click web page capture with Readability + Turndown, auto-triggering ingest after clip.

- **CI/CD Pipeline** — pytest + vitest matrix across Python 3.10–3.12 and Node 18–22, coverage reporting, caching, benchmark artifacts.

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

# Start MCP server
llm-wiki serve ~/my-wiki
```

## Architecture

```
wiki/ directory  ← shared state (Markdown files)
     │
     ├── Agent Skill + Python Scripts   → 20+ scripts: scaffold, ingest, lint,
     │                                     discover, insights, backup, link-suggest,
     │                                     deep-research, audit, benchmark, sidecar,
     │                                     lock_wiki, atomic_write, content_hash,
     │                                     index_wiki, louvain, health_check, wiki_logging
     ├── LLM Provider Layer             → openai, anthropic, litellm, opencode
     │   (src/llm_wiki/ + skill/scripts/providers/)
     ├── MCP Server (stdio)             → programmatic access, 10 tools,
     │                                     direct sidecar (zero subprocess)
     ├── Graph Engine (Node.js)         → relevance model, Louvain, insights,
     │                                     graphology bridge, verification suite
     ├── Web Viewer + Obsidian Plugin   → human browsing + feedback
     ├── Browser Extension              → web clipping + auto-ingest
     └── templates/                     → 19 domain schemas
```

## Packages

| Package | Language | Purpose |
|---------|----------|---------|
| `skill/` | Python + Markdown | Agent skill (8 operations) + 20+ scripts + 12 reference docs |
| `src/llm_wiki/` | Python | PyPI package — CLI, LLM providers, concurrency, search, graph insights |
| `mcp-server/` | TypeScript | MCP server — 10 tools, direct sidecar integration |
| `graph-engine/` | TypeScript | Knowledge graph — relevance, Louvain communities, insights, verification |
| `templates/` | Markdown + JSON | 19 domain-specific project templates |
| `tests/` | Python + TypeScript | pytest (ingest, lint, concurrency, search, opencode) + vitest (graph, mcp) |
| `web-viewer/` | TypeScript | Preview server with search + graph insights panel |
| `extension/` | JavaScript | Chrome web clipper with auto-ingest |
| `audit-shared/` | TypeScript | Shared audit file format library |
| `plugins/obsidian-audit/` | TypeScript | Obsidian plugin — file feedback from vault |

## Templates (20 domains)

`research` `codebase` `finance` `algorithmic-trading` `algorithmic-trading-mql4` `cybersecurity` `machine-learning` `prompt-engineering` `copywriting` `marketing` `design-systems` `architecture` `crypto` `commodities` `decompilers` `medicine` `developer-tools` `personal-growth` `reading` `business`

Every template provides: `PURPOSE.md` (scope + goals), `SCHEMA.md` → `CLAUDE.md` (page types, conventions, frontmatter, cross-referencing, contradiction handling), `extra-dirs.json` (domain directories).

## Documentation

| File | What it covers |
|------|---------------|
| `README.md` | You are here |
| `QUICKGUIDE.md` | Every command with real examples |
| `AGENTS.md` | Architecture, conventions, build/test commands, Python Dependency Policy |
| `CHANGELOG.md` | Full version history — all features, changes, and breaking changes |
| `INDEX.md` | Complete file tree with descriptions |
| `VERSIONING.md` | Semantic versioning policy and release process |
| `PURPOSE.md` | Why this system exists |
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

- **`graph-engine/src/relevance.ts`** — Contains code ported from `nashsu/llm_wiki` (GPL-3.0). See [THIRD_PARTY.md](./THIRD_PARTY.md) for disposition status.
- **`graph-engine/src/insights.ts`** — Contains code ported from `nashsu/llm_wiki` (GPL-3.0). See [THIRD_PARTY.md](./THIRD_PARTY.md) for disposition status.
- **`graph-engine/src/louvain.ts`** — Implements the Louvain community detection algorithm (Blondel et al. 2008) via the MIT-licensed `graphology-communities-louvain` library.

### Related Projects

- [nashsu/llm_wiki](https://github.com/nashsu/llm_wiki) — Cross-platform Tauri desktop app with graph visualization, vector search, and rich chat interface. Licensed GPL-3.0.
- [anzal1/quicky-wiki](https://github.com/anzal1/quicky-wiki) — MIT-licensed CLI/dashboard for claim extraction, confidence scoring, and metabolism.

### Upstream License Notice

This project may include code derived from GPL-3.0-licensed upstream sources (`graph-engine/src/relevance.ts`, `graph-engine/src/insights.ts`). A **provenance review** is required before public release. See [CONTRIBUTING.md](./CONTRIBUTING.md#release-blocker-gpl-provenance-review) and the full [THIRD_PARTY.md](./THIRD_PARTY.md) ledger for details.

## License

MIT
