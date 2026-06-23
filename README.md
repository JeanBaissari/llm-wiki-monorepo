# LLM Wiki Monorepo

[![CI](https://github.com/JeanBaissari/llm-wiki-monorepo/actions/workflows/ci.yml/badge.svg)](https://github.com/JeanBaissari/llm-wiki-monorepo/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/baissarienterprises-llm-wiki.svg)](https://pypi.org/project/baissarienterprises-llm-wiki/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![Node 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org)
[![License MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

> `pip install baissarienterprises-llm-wiki`

**A production-grade knowledge base operating system.** AI agents compile raw sources into persistent, cross-linked Markdown wikis. Knowledge compounds over time. No database. No API lock-in. Just files.

Instead of re-retrieving raw documents on every query (RAG), this system **compiles** sources into a living wiki that agents maintain automatically. Clone anywhere, run with any AI agent, pull on any machine.

---

## Features

| Area | Capabilities |
|------|-------------|
| **Ingestion** | Two-stage chain-of-thought ingest with SHA256 caching. Multi-step agent loop. Batch processing. Deep research (web search → fetch → ingest → synthesize). |
| **Quality** | 15-pass automated lint: dead links, orphans, frontmatter validation, contradictions, source drift, page size, log rotation, stale page detection when raw sources change. |
| **Graph** | Knowledge graph engine (TypeScript): Louvain community detection, 4-signal relevance model, surprising connections, knowledge gaps. Pure Python fallback. |
| **Backup** | Snapshot, restore, integrity verification, automatic pruning. One-command `--auto` for safe state. |
| **Link Suggestions** | Entity extraction from frontmatter/headings/bold terms. 4-signal scoring. Automatic wikilink insertion (`--apply`). |
| **Search** | BM25 full-text search (TypeScript, zero deps). Web viewer search bar with ranked results. Graph search. |
| **MCP Server** | 8 stdio tools for programmatic access. Multi-wiki mode (`--projects`). Integrates with Claude Desktop, Codex, Cursor. |
| **Templates** | 19 domain-specific wiki scaffolds with consistent schemas. Research, codebase, finance, ML, cybersecurity, medicine, and more. |
| **Web Viewer** | Local preview with KaTeX, mermaid, wikilink resolution. Search bar and graph insights panel. |
| **Browser Extension** | Chrome web clipper with Readability + Turndown. Auto-trigger ingest after clip. |
| **CI/CD** | GitHub Actions: Python syntax checks, TypeScript builds, full integration test (scaffold → lint → graph build → insights). |

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

# Check quality
llm-wiki lint ~/my-wiki

# Discover connections
llm-wiki insights ~/my-wiki

# Start MCP server (for Claude Desktop, Codex, etc.)
llm-wiki serve ~/my-wiki
```

## Architecture

```
wiki/ directory  ← shared state (Markdown files)
     │
      ├── Agent Skill + Python Scripts   → 13 scripts: scaffold, ingest, lint,
      │                                     discover, insights, backup,
      │                                     link-suggest, deep-research, audit,
      │                                     benchmark, migrate-log, test-e2e
     ├── MCP Server (stdio)             → programmatic access, 8 tools,
     │                                     single or multi-wiki mode
     ├── Graph Engine (Node.js)         → relevance model, Louvain, insights
     ├── Web Viewer + Obsidian Plugin   → human browsing + feedback
     ├── Browser Extension              → web clipping + auto-ingest
     └── templates/                     → 19 domain schemas
```

## Packages

| Package | Language | Purpose |
|---------|----------|---------|
| `skill/` | Python + Markdown | Agent skill (8 operations) + 13 Python scripts + 10 reference docs |
| `mcp-server/` | TypeScript | MCP server — 8 tools, single or multi-wiki mode |
| `graph-engine/` | TypeScript | Knowledge graph — relevance, Louvain communities, insights |
| `templates/` | Markdown + JSON | 19 domain-specific project templates (audited, consistent) |
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
| `AGENTS.md` | Architecture, conventions, build/test commands |
| `INDEX.md` | Complete file tree with descriptions |
| `VERSIONING.md` | Semantic versioning policy and release process |
| `PURPOSE.md` | Why this system exists |
| `skill/references/` | 10 detailed reference guides |

## Requirements

- **Python 3.10+** — for all skill scripts
- **Node.js 18+** — for MCP server, graph engine, web viewer
- **npm** — for package management

## License

MIT
