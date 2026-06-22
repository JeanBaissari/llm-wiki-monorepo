# LLM Wiki Monorepo

Complete LLM Wiki operating system — build, maintain, and query persistent knowledge bases using AI agents.

**One repo. Pull anywhere. Works everywhere.**

## What's inside

| Package | Purpose |
|---------|---------|
| `skill/` | Hermes/Claude/Codex agent skill — SKILL.md + Python scripts |
| `mcp-server/` | Standalone MCP server — 8 tools, works against any wiki directory |
| `graph-engine/` | Knowledge graph engine — relevance model, Louvain communities, insights |
| `templates/` | 19 project templates with PURPOSE.md + SCHEMA.md per domain |
| `web-viewer/` | Local Node.js preview server with mermaid, KaTeX, feedback popover |
| `extension/` | Chrome browser extension — clip web pages to your wiki |
| `audit-shared/` | Shared TypeScript library for audit file format |
| `plugins/obsidian-audit/` | Obsidian plugin — file feedback from inside your vault |
| `rust-backend/` | Optional: multi-format document parsing (PDF, Office, etc.) |

## Quick start

```bash
# 1. Scaffold a new wiki
python3 skill/scripts/scaffold.py ~/my-wiki "My Topic" --template research

# 2. Ingest a source
python3 skill/scripts/ingest.py ~/my-wiki raw/articles/my-article.md

# 3. Ask questions
# (via your AI agent with the skill loaded)

# 4. Lint periodically
python3 skill/scripts/lint_wiki.py ~/my-wiki

# 5. Run deep research
python3 skill/scripts/deep_research.py ~/my-wiki "attention mechanisms"

# 6. Get graph insights
python3 skill/scripts/graph_insights.py ~/my-wiki

# 7. Start MCP server
npm run mcp -- --wiki ~/my-wiki

# 8. Start web viewer
npm run web -- --wiki ~/my-wiki --port 4175
```

## Install as Hermes skill

```bash
ln -s $(pwd)/skill ~/.hermes/skills/research/llm-wiki
```

## Install as MCP server (for Claude Desktop, Codex, etc.)

```json
{
  "mcpServers": {
    "llm-wiki": {
      "command": "node",
      "args": ["/path/to/llm-wiki-monorepo/mcp-server/dist/index.js", "--wiki", "/path/to/your-wiki"]
    }
  }
}
```

## Templates

Choose a template when scaffolding: `--template <name>`

```
research, codebase, finance, algorithmic-trading, cybersecurity,
machine-learning, prompt-engineering, copywriting, marketing,
design-systems, architecture, crypto, commodities, decompilers,
medicine, developer-tools, personal-growth, reading, business
```

Each template includes:
- `PURPOSE.md` — the project's reason for existing
- `SCHEMA.md` — page types, naming conventions, frontmatter rules
- Extra directories customized for the domain

## Architecture

```
wiki/ directory  ← the shared state (markdown files)
     │
     ├── Agent Skill + Python Scripts   (in-conversation workflows)
     ├── MCP Server                     (programmatic access, 8 tools)
     ├── Graph Engine                   (relevance model, Louvain communities)
     ├── Web Viewer + Obsidian Plugin   (human browsing + feedback)
     ├── Browser Extension              (web clipping)
     └── Rust Backend (optional)        (multi-format document parsing)
```

All components work standalone or interconnected through the wiki directory.

## License

MIT
