# LLM Wiki Monorepo

[![CI](https://github.com/JeanBaissari/llm-wiki-monorepo/actions/workflows/ci.yml/badge.svg)](https://github.com/JeanBaissari/llm-wiki-monorepo/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/baissarienterprises-llm-wiki.svg)](https://pypi.org/project/baissarienterprises-llm-wiki/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![Node 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org)
[![License MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

> `pip install baissarienterprises-llm-wiki`

**A knowledge base that builds itself.** AI agents compile raw sources into persistent, cross-linked Markdown wikis. Instead of re-retrieving documents on every query (RAG), the system incrementally builds and maintains a living wiki from your sources. Knowledge compounds over time. No database. No API lock-in. One repo. Any agent. Any machine.

---

## Features

- **Two-Step Chain-of-Thought Ingest** — LLM analyzes sources first, then generates structured wiki pages with SHA256 caching, streaming Stage 1 progress, and multi-provider LLM support (OpenAI, Anthropic, DeepSeek, or agent-native with zero API keys)
- **Agent-Native LLM Provider** — routes ingest calls through Hermes, Claude Code, or Codex models directly — no external API keys required when running inside an AI agent session
- **Structured Output** — Pydantic-typed FILE and REVIEW blocks via instructor — no fragile regex parsing. Retry with exponential backoff on transient failures. Token counting and cost estimation per operation
- **Concurrency Control** — per-page advisory locking, atomic writes (temp → fsync → rename), content-hash conflict detection (SHA256 in frontmatter), and three-tier conflict management with automatic cleanup
- **15-Pass Automated Lint** — dead links, orphans, frontmatter validation, contradictions, source drift, unresolved conflicts, stale page detection when raw sources change
- **Knowledge Graph Engine** — Louvain community detection with full Blondel et al. modularity, 4-signal relevance model with precomputed adjacency, surprising connection discovery, and knowledge gap detection. Pure Python fallback included
- **SQLite FTS5 Search** — full-text search with SHA256 freshness detection, pre-build at startup, incremental updates, BM25 fallback. `--rebuild` flag for full reindex
- **Inverted Entity Index** — dual-map entity→pages + page→entities for O(1) link suggestion lookups. 4-signal scoring with automatic wikilink insertion (`--apply`)
- **MCP Server** — 10 stdio tools for programmatic wiki access. Direct Python sidecar with zero subprocess overhead. Integrates with Claude Desktop, Codex, Cursor, and any MCP-compatible client
- **Community Verification Suite** — NMI/ARI cross-validation across 5 seeds, statistical similarity metrics, modularity tolerance within 1% relative error
- **Backup & Recovery** — tar.gz snapshots with restore, integrity verification, and automatic pruning. One-command `--auto` for safe state
- **19 Domain Templates** — research, codebase, finance, machine learning, cybersecurity, medicine, algorithmic trading, and more. Every template provides PURPOSE.md, SCHEMA.md → CLAUDE.md, and extra-dirs.json
- **Deep Research** — web search → fetch → ingest → synthesize. Multi-source compilation into structured wiki pages
- **Chrome Web Clipper** — one-click web page capture with Readability + Turndown, auto-trigger ingest after clip
- **CI/CD Pipeline** — pytest + vitest matrix across Python 3.10–3.12 and Node 18–22, coverage reporting, caching, benchmark artifacts

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

## Templates (19 domains)

`research` `codebase` `finance` `algorithmic-trading` `cybersecurity` `machine-learning` `prompt-engineering` `copywriting` `marketing` `design-systems` `architecture` `crypto` `commodities` `decompilers` `medicine` `developer-tools` `personal-growth` `reading` `business`

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

The foundational methodology comes from **Andrej Karpathy**'s [llm-wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) pattern — using LLMs to incrementally build and maintain a personal wiki from raw sources. This project is a production-grade implementation with concurrency control, multi-provider LLM support, FTS5 search, MCP integration, and community detection.

## License

MIT
