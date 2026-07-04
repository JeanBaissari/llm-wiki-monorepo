# LLM Wiki Monorepo

[![CI](https://github.com/JeanBaissari/llm-wiki-monorepo/actions/workflows/ci.yml/badge.svg)](https://github.com/JeanBaissari/llm-wiki-monorepo/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/baissarienterprises-llm-wiki.svg)](https://pypi.org/project/baissarienterprises-llm-wiki/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![Node 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org)
[![License MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-298%2B%20passing-brightgreen.svg)](https://github.com/JeanBaissari/llm-wiki-monorepo/actions)
[![Coverage](https://img.shields.io/badge/coverage-80%25%2B%20Python%20%7C%2070%25%2B%20TS-yellowgreen.svg)](https://github.com/JeanBaissari/llm-wiki-monorepo/actions)

> `pip install baissarienterprises-llm-wiki`

**A production-grade knowledge base operating system — v0.2.0.** AI agents compile raw sources into persistent, cross-linked Markdown wikis with concurrency control, multi-provider LLM integration, FTS5 full-text search, and community detection. Knowledge compounds over time. No database. No API lock-in. Just files.

Instead of re-retrieving raw documents on every query (RAG), this system **compiles** sources into a living wiki that agents maintain automatically. Clone anywhere, run with any AI agent (Hermes, Claude Code, Codex), pull on any machine.

---

## What's New in v0.2.0

- **CI Test Infrastructure** — 298+ tests across pytest + vitest with provider-agnostic mocks
- **Concurrency Control** — per-page advisory locking, atomic writes, conflict detection, three-tier conflict management
- **LLM SDK Integration** — native openai/anthropic SDKs, LiteLLM fallback, instructor structured output, retry with backoff
- **Agent-Native Provider** — routes LLM calls through Hermes/Claude Code/Codex models (no API keys needed)
- **Search Persistence** — SQLite FTS5 with SHA256 freshness, pre-build at startup, incremental updates
- **Graph Optimization** — ≥20x speedup at 5,000 pages via precomputed adjacency
- **Link Suggestion** — inverted entity index with O(1) lookup, ~10x faster
- **Community Detection** — full Louvain with Blondel et al. modularity, NMI/ARI cross-validation
- **MCP Direct Integration** — Python sidecar + direct TypeScript imports, zero subprocess for graph ops
- **New MCP Tools** — suggest_links, backup, discover_entities

## Features

| Area | Capabilities |
|------|-------------|
| **Ingestion** | Two-stage chain-of-thought ingest with SHA256 caching. Multi-step agent loop. Batch processing. Deep research (web search → fetch → ingest → synthesize). **v0.2.0**: Streaming Stage 1 progress, `--llm-timeout` flag, `--max-cost` budget cap. |
| **LLM Providers** | Multi-provider: openai, anthropic, deepseek, together via native SDKs. LiteLLM fallback chain with cost tracking. **v0.2.0**: Agent-native opencode provider (no API keys). Structured output via instructor (Pydantic-typed FILE/REVIEW blocks). Retry with exponential backoff. Token counting. |
| **Concurrency** | Per-page advisory locking (portalocker). Atomic writes (temp → fsync → rename). Content-hash conflict detection (SHA256 in frontmatter). Three-tier conflict management (lint rule, `--clean-conflicts` auto-archive, EOW cron cleanup). |
| **Quality** | 15-pass automated lint: dead links, orphans, frontmatter validation, contradictions, source drift, page size, log rotation, **unresolved conflict detection**, stale page detection when raw sources change. |
| **Graph** | Knowledge graph engine (TypeScript): Louvain community detection (full Blondel et al. modularity), 4-signal relevance model (precomputed adjacency, ≥20x speedup), surprising connections, knowledge gaps. Pure Python fallback. NMI/ARI cross-validation suite. |
| **Search** | **SQLite FTS5** with SHA256 freshness detection. Pre-build at startup. Incremental updates. BM25 full-text search. Web viewer search bar with ranked results. Graph search. `--rebuild` flag. |
| **Backup** | Snapshot, restore, integrity verification, automatic pruning. One-command `--auto` for safe state. |
| **Link Suggestions** | Entity extraction from frontmatter/headings/bold terms. Inverted entity index (O(1) lookup, ~10x faster). 4-signal scoring. Automatic wikilink insertion (`--apply`). |
| **MCP Server** | 10 stdio tools for programmatic access. Multi-wiki mode (`--projects`). **v0.2.0**: Direct Python sidecar (zero subprocess), suggest_links, backup, discover_entities tools. Integrates with Claude Desktop, Codex, Cursor. |
| **Templates** | 19 domain-specific wiki scaffolds with consistent schemas. Research, codebase, finance, ML, cybersecurity, medicine, and more. |
| **CI/CD** | GitHub Actions: pytest + vitest matrix (Python 3.10–3.12, Node 18–22), coverage reporting (≥80% Python, ≥70% TS), caching, integration tests. |
| **Web Viewer** | Local preview with KaTeX, mermaid, wikilink resolution. Search bar and graph insights panel. |
| **Browser Extension** | Chrome web clipper with Readability + Turndown. Auto-trigger ingest after clip. |

## Quick Start

```bash
# Install from PyPI
pip install baissarienterprises-llm-wiki

# Or install from source (for development)
git clone https://github.com/JeanBaissari/llm-wiki-monorepo.git
cd llm-wiki-monorepo
bash install.sh

# Scaffold a wiki
llm-wiki scaffold ~/my-wiki "My Research" --template research

# Ingest a source (two-step agent loop)
llm-wiki ingest ~/my-wiki raw/articles/my-source.md

# Ingest with a specific LLM provider
llm-wiki ingest ~/my-wiki raw/articles/my-source.md --llm openai --model gpt-4o

# Use agent-native provider (no API keys — inside Hermes/Claude Code/Codex)
llm-wiki ingest ~/my-wiki raw/articles/my-source.md --llm opencode

# Check quality (includes conflict detection)
llm-wiki lint ~/my-wiki

# Clean up old conflicts
llm-wiki lint ~/my-wiki --clean-conflicts

# Build search index
llm-wiki index ~/my-wiki

# Discover connections
llm-wiki insights ~/my-wiki

# Health check
llm-wiki health ~/my-wiki

# Start MCP server (for Claude Desktop, Codex, etc.)
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
| `skill/` | Python + Markdown | Agent skill (8 operations) + 20+ Python scripts + 12 reference docs |
| `src/llm_wiki/` | Python | PyPI package — CLI, LLM providers, concurrency, search, graph insights |
| `mcp-server/` | TypeScript | MCP server — 10 tools, direct sidecar integration |
| `graph-engine/` | TypeScript | Knowledge graph — relevance, Louvain communities, insights, verification |
| `templates/` | Markdown + JSON | 19 domain-specific project templates (audited, consistent) |
| `tests/` | Python + TypeScript | 298+ tests — pytest (ingest, lint, concurrency, search, opencode) + vitest (graph, mcp) |
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
| `AGENTS.md` | Architecture, conventions, build/test commands, **Python Dependency Policy** |
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

## License

MIT
