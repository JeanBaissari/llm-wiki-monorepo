# Quick Guide — llm-wiki-monorepo

Hands-on command reference. Every operation you can run, with real examples.

## 1. Scaffold a Wiki

```bash
# Default research template
python3 skill/scripts/scaffold.py ~/my-wiki "My Research Topic"

# Domain-specific template
python3 skill/scripts/scaffold.py ~/my-codebase-wiki "My Project" --template codebase

# Algorithmic trading wiki (for quant strategies)
python3 skill/scripts/scaffold.py ~/strat-wiki "Strategy Lab" --template algorithmic-trading

# List all 19 templates
python3 skill/scripts/scaffold.py --list-templates

# Force overwrite existing wiki
python3 skill/scripts/scaffold.py ~/my-wiki "New Topic" --template codebase --force
```

**What it creates:**
```
<wiki-root>/
├── PURPOSE.md      ← Why this wiki exists
├── CLAUDE.md       ← Schema: conventions, page types, naming rules
├── log/            ← Per-day operation log
├── audit/          ← Human feedback inbox
├── raw/            ← Immutable source documents
├── wiki/           ← LLM-generated knowledge pages
└── outputs/        ← Query answers, charts
```

## 2. Ingest Sources

```bash
# Two-step chain-of-thought ingest (recommended for complex sources)
python3 skill/scripts/ingest.py ~/my-wiki raw/articles/my-article.md

# Force re-ingest (skip cache)
python3 skill/scripts/ingest.py ~/my-wiki raw/articles/my-article.md --force

# Batch ingest a directory
python3 skill/scripts/ingest.py ~/my-wiki raw/articles/ --batch
```

**How two-step ingest works:**
1. Stage 1 (Analysis): LLM extracts entities, concepts, claims, relationships, contradictions
2. Stage 2 (Generation): LLM produces FILE blocks (wiki pages) + REVIEW blocks (issues to fix)
3. Result: pages created/updated, review items generated, index + log updated

## 3. Lint the Wiki

```bash
# Run all 14 automated checks
python3 skill/scripts/lint_wiki.py ~/my-wiki

# Show help
python3 skill/scripts/lint_wiki.py --help
```

**14 checks:** dead wikilinks, orphan pages, missing index entries, unlinked concepts, log/ shape, audit/ shape, audit targets, frontmatter validation, stale pages (>90 days), confidence signals, contradiction signals, page size (>200 lines), log rotation, SHA256 source drift

## 4. Get Graph Insights

```bash
# Surprising connections + knowledge gaps
python3 skill/scripts/graph_insights.py ~/my-wiki

# Limit results
python3 skill/scripts/graph_insights.py ~/my-wiki --connections 10 --gaps 10

# JSON output (for scripts)
python3 skill/scripts/graph_insights.py ~/my-wiki --format json
```

## 5. Deep Research

```bash
# Research a topic — web search + source fetch + auto-ingest + synthesis
python3 skill/scripts/deep_research.py ~/my-wiki "transformer attention mechanisms"

# With specific URLs
python3 skill/scripts/deep_research.py ~/my-wiki "topic" --urls "https://arxiv.org/abs/1706.03762,https://example.com/article"

# Control depth
python3 skill/scripts/deep_research.py ~/my-wiki "topic" --depth 3 --sources 10
```

## 6. Knowledge Graph Engine

```bash
# Install deps (one time)
cd graph-engine && npm install && cd ..

# Build graph from wiki
node graph-engine/dist/index.js --wiki ~/my-wiki --action build

# Get insights (requires build first)
node graph-engine/dist/index.js --wiki ~/my-wiki --action insights

# Search graph
node graph-engine/dist/index.js --wiki ~/my-wiki --action search --query "strategy"

# Get related nodes
node graph-engine/dist/index.js --wiki ~/my-wiki --action relevance --node "entities/xau-swinger"
```

## 7. MCP Server

```bash
# Install deps (one time)
cd mcp-server && npm install && cd ..

# Build
cd mcp-server && npx tsc && cd ..

# Start server
node mcp-server/dist/index.js --wiki ~/my-wiki

# Or via env var
LLM_WIKI_PATH=~/my-wiki node mcp-server/dist/index.js
```

**8 MCP Tools:**
- `llm_wiki_status` — Health, page count, last ingest, open reviews
- `llm_wiki_files` — File tree listing (wiki/sources/all)
- `llm_wiki_read_file` — Read any file (120KB limit)
- `llm_wiki_reviews` — List review items (open/resolved/all)
- `llm_wiki_search` — BM25 full-text search
- `llm_wiki_graph` — Graph operations (build/insights/search)
- `llm_wiki_lint` — Run automated lint checks
- `llm_wiki_ingest` — Trigger two-step ingest on a source

**Claude Desktop config:**
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

## 8. Web Viewer

```bash
cd web-viewer
npm install
npm run build
npm start -- --wiki ~/my-wiki --port 4175
# Open http://127.0.0.1:4175
```

## 9. Browser Extension

1. Open Chrome → `chrome://extensions`
2. Enable "Developer mode"
3. Click "Load unpacked" → select `extension/` directory
4. Click the extension icon on any webpage → clips to markdown with frontmatter

## 10. Audit Reviews

```bash
# List open reviews
python3 skill/scripts/audit_review.py ~/my-wiki --open

# List resolved reviews
python3 skill/scripts/audit_review.py ~/my-wiki --resolved

# List all
python3 skill/scripts/audit_review.py ~/my-wiki --all
```

## 11. Migrate Old Wikis

```bash
# Convert v1 log.md → v2 log/ directory
python3 skill/scripts/migrate_log.py ~/my-old-wiki
```

## 12. Hermes Agent Install

```bash
# Symlink skill into Hermes
ln -sf $(pwd)/skill ~/.hermes/skills/research/llm-wiki

# Verify
ls ~/.hermes/skills/research/llm-wiki/SKILL.md
```

## Common Workflows

### Start a new research project
```bash
python3 skill/scripts/scaffold.py ~/research-topic "Topic Name" --template research
python3 skill/scripts/deep_research.py ~/research-topic "key research question"
python3 skill/scripts/lint_wiki.py ~/research-topic
python3 skill/scripts/graph_insights.py ~/research-topic
```

### Add a codebase to a software wiki
```bash
python3 skill/scripts/scaffold.py ~/project-wiki "Project Name" --template codebase
# Copy your project docs into raw/articles/
python3 skill/scripts/ingest.py ~/project-wiki raw/articles/architecture.md
python3 skill/scripts/ingest.py ~/project-wiki raw/articles/api-docs.md
python3 skill/scripts/lint_wiki.py ~/project-wiki
```

### Weekly health check (cron)
```bash
python3 skill/scripts/lint_wiki.py ~/my-wiki
node graph-engine/dist/index.js --wiki ~/my-wiki --action build
node graph-engine/dist/index.js --wiki ~/my-wiki --action insights
python3 skill/scripts/audit_review.py ~/my-wiki --open
```
