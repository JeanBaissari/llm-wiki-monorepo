# LLM Wiki Monorepo

Complete LLM Wiki operating system — build, maintain, and query persistent AI-maintained knowledge bases. One `git clone`. Works with any AI agent. Pull anywhere.

## What is this?

Instead of RAG (re-retrieving raw docs on every query), the LLM **compiles** raw sources into a persistent, cross-linked Markdown wiki. Knowledge compounds over time. The wiki stays current because the LLM does all the maintenance.

This monorepo provides the entire toolchain: agent skill, MCP server, knowledge graph engine, domain-specific templates, browser extension, web viewer, and Obsidian plugin.

## Quick Start

```bash
git clone https://github.com/JeanBaissari/llm-wiki-monorepo.git
cd llm-wiki-monorepo

# Scaffold a wiki
python3 skill/scripts/scaffold.py ~/my-wiki "My Topic" --template research

# Ingest a source
python3 skill/scripts/ingest.py ~/my-wiki raw/articles/my-article.md

# Run lint (14 automated checks)
python3 skill/scripts/lint_wiki.py ~/my-wiki

# Get graph insights
python3 skill/scripts/graph_insights.py ~/my-wiki

# Deep research
python3 skill/scripts/deep_research.py ~/my-wiki "attention mechanisms"

# Start MCP server (for Claude Desktop, Codex, etc.)
npm install
npm run build
node mcp-server/dist/index.js --wiki ~/my-wiki

# Install as Hermes agent skill
ln -s $(pwd)/skill ~/.hermes/skills/research/llm-wiki
```

## Packages

| Package | Language | Purpose |
|---------|----------|---------|
| `skill/` | Python + Markdown | Agent skill with 8 operations, 5 Python scripts, 10 reference docs |
| `mcp-server/` | TypeScript | Standalone MCP server — 8 tools against any wiki directory |
| `graph-engine/` | TypeScript | Knowledge graph — relevance model, Louvain communities, insights |
| `templates/` | Markdown + JSON | 19 domain-specific project templates |
| `web-viewer/` | TypeScript | Local Node.js preview server with mermaid + KaTeX |
| `extension/` | JavaScript | Chrome browser extension — web clipper |
| `audit-shared/` | TypeScript | Shared audit file format library |
| `plugins/obsidian-audit/` | TypeScript | Obsidian plugin — file feedback from vault |
| `rust-backend/` | Rust | Optional: multi-format document parsing |

## Templates (19 domains)

`research` `codebase` `finance` `algorithmic-trading` `cybersecurity` `machine-learning` `prompt-engineering` `copywriting` `marketing` `design-systems` `architecture` `crypto` `commodities` `decompilers` `medicine` `developer-tools` `personal-growth` `reading` `business`

Each template provides: `PURPOSE.md` (project purpose), `SCHEMA.md` → `CLAUDE.md` (conventions), `extra-dirs.json` (domain directories).

## Architecture

```
wiki/ directory  ← shared state (markdown files)
     │
     ├── Agent Skill + Python Scripts   → in-conversation workflows
     ├── MCP Server (stdio)             → programmatic access, 8 tools
     ├── Graph Engine (Node.js)         → relevance model, Louvain, insights
     ├── Web Viewer + Obsidian Plugin   → human browsing + feedback
     ├── Browser Extension              → web clipping
     └── Rust Backend (optional)        → multi-format doc parsing
```

All components work standalone or interconnected through the wiki directory.

## Key Features

- **Two-step chain-of-thought ingest** — Stage 1 analysis → Stage 2 generation, with SHA256 caching
- **14-pass automated lint** — dead links, orphans, frontmatter, staleness, confidence, contradictions, SHA256 drift, page size, log rotation
- **4-signal relevance model** — direct links, source overlap, Adamic-Adar neighbors, type affinity
- **Louvain community detection** — automatic topic clustering with cohesion scoring
- **Graph insights** — surprising connections + knowledge gaps (isolated, sparse, bridge nodes)
- **Bidirectional review system** — AI flags issues during ingest, human files feedback via Obsidian/web
- **Deep research** — web search → source fetch → auto-ingest → synthesis
- **BM25 full-text search** — pure TypeScript, no external dependencies
- **19 domain templates** — scaffold a domain-specific wiki in one command
- **Browser extension** — clip any webpage to your wiki with auto-frontmatter

## Documentation

- `README.md` — You are here
- `INDEX.md` — Complete file tree with descriptions
- `QUICKGUIDE.md` — Hands-on command reference with examples
- `AGENTS.md` — Architecture and conventions for AI agents
- `PURPOSE.md` — Why this system exists
- `skill/references/` — 11 detailed reference guides

## Requirements

- **Python 3.10+** — for skill scripts
- **Node.js 18+** — for MCP server, graph engine, web viewer
- **npm** — for package management

## License

MIT
