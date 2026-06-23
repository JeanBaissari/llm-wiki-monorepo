# Quick Guide — llm-wiki-monorepo

Hands-on command reference. Every operation you can run, with real examples.

## 1. One-Command Install

```bash
bash install.sh
```

Detects Python/Node versions, installs npm dependencies, builds all TypeScript packages, verifies all Python scripts, and optionally creates Hermes symlinks and PATH wrappers.

## 2. Scaffold a Wiki

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

## 3. Ingest Sources

```bash
# Two-step chain-of-thought ingest (recommended for complex sources)
python3 skill/scripts/ingest.py ~/my-wiki raw/articles/my-article.md

# Force re-ingest (skip cache)
python3 skill/scripts/ingest.py ~/my-wiki raw/articles/my-article.md --force

# Batch ingest a directory
python3 skill/scripts/ingest.py ~/my-wiki raw/articles/ --batch
```

**Agent loop mode** (no API key needed):
```bash
# Pass 1: prints Stage 1 prompt → you respond with analysis → cached
LLM_WIKI_RESPONSE_FILE=~/stage1-response.txt python3 skill/scripts/ingest.py ~/my-wiki source.md

# Pass 2: uses cached analysis → prints Stage 2 prompt → you respond with pages
LLM_WIKI_RESPONSE_FILE=~/stage2-response.txt python3 skill/scripts/ingest.py ~/my-wiki source.md
```

**How two-step ingest works:**
1. Stage 1 (Analysis): LLM extracts entities, concepts, claims, relationships, contradictions
2. Stage 2 (Generation): LLM produces FILE blocks (wiki pages) + REVIEW blocks (issues to fix)
3. Result: pages created/updated, review items generated, index + log updated

## 4. Lint the Wiki

```bash
# Run all 15 automated checks
python3 skill/scripts/lint_wiki.py ~/my-wiki

# JSON output (for scripts)
python3 skill/scripts/lint_wiki.py ~/my-wiki --json

# Show help
python3 skill/scripts/lint_wiki.py --help
```

**15 checks:** dead wikilinks, orphan pages, missing index entries, unlinked concepts, log/ shape, audit/ shape, audit targets, frontmatter validation, stale pages (>90 days), confidence signals, contradiction signals, page size (>200 lines), log rotation, SHA256 source drift, stale wiki pages from source drift.

## 5. Graph Insights

### TypeScript engine (production)
```bash
# Build graph
node graph-engine/dist/index.js --wiki ~/my-wiki --action build

# Get insights (requires build first)
node graph-engine/dist/index.js --wiki ~/my-wiki --action insights

# Search graph
node graph-engine/dist/index.js --wiki ~/my-wiki --action search --query "strategy"

# Get related nodes
node graph-engine/dist/index.js --wiki ~/my-wiki --action relevance --node "entities/xau-swinger"
```

### Python fallback (no deps)
```bash
python3 skill/scripts/graph_insights.py ~/my-wiki

# Limit results
python3 skill/scripts/graph_insights.py ~/my-wiki --connections 10 --gaps 10

# JSON output
python3 skill/scripts/graph_insights.py ~/my-wiki --format json
```

## 6. Link Suggestions

```bash
# Get ranked suggestions for missing wikilinks
python3 skill/scripts/link_suggest.py ~/my-wiki

# Auto-add wikilinks (modifies pages)
python3 skill/scripts/link_suggest.py ~/my-wiki --apply

# Limit to top 10, minimum confidence 0.5
python3 skill/scripts/link_suggest.py ~/my-wiki --limit 10 --min-confidence 0.5

# JSON output
python3 skill/scripts/link_suggest.py ~/my-wiki --format json
```

Entity extraction from frontmatter, headings, and bold terms. 4-signal scoring: frequency, position, type affinity, commonality penalty.

## 7. Deep Research

```bash
# Research a topic — web search + source fetch + auto-ingest + synthesis
python3 skill/scripts/deep_research.py ~/my-wiki "transformer attention mechanisms"

# With specific URLs
python3 skill/scripts/deep_research.py ~/my-wiki "topic" --urls "https://arxiv.org/abs/1706.03762,https://example.com/article"

# Control depth
python3 skill/scripts/deep_research.py ~/my-wiki "topic" --depth 3 --sources 10
```

## 8. Backup & Recovery

```bash
# Create a timestamped snapshot
python3 skill/scripts/backup.py ~/my-wiki --snapshot

# List available backups
python3 skill/scripts/backup.py ~/my-wiki --list

# Restore from a specific backup
python3 skill/scripts/backup.py ~/my-wiki --restore 20260622-143000

# Verify wiki integrity (wikilinks, frontmatter, required files)
python3 skill/scripts/backup.py ~/my-wiki --verify

# Keep only the 5 most recent backups
python3 skill/scripts/backup.py ~/my-wiki --prune 5

# One-command safe state: snapshot + prune to 10 + verify
python3 skill/scripts/backup.py ~/my-wiki --auto
```

## 9. MCP Server

```bash
# Single-wiki mode
node mcp-server/dist/index.js --wiki ~/my-wiki

# Multi-wiki mode (serve all wikis in a directory)
node mcp-server/dist/index.js --projects ~/wikis

# Via env var
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

**Multi-wiki mode:** Add `"project": "project-name"` to tool call arguments.

**Claude Desktop config:**
```json
{
  "mcpServers": {
    "llm-wiki": {
      "command": "node",
      "args": ["/path/to/llm-wiki-monorepo/mcp-server/dist/index.js", "--projects", "/path/to/wikis"]
    }
  }
}
```

## 10. Web Viewer

```bash
cd web-viewer
npm install
npm run build
npm start -- --wiki ~/my-wiki --port 4175
# Open http://127.0.0.1:4175
```

**Features:** Search bar (TF-based ranking), graph insights panel (metrics, surprising connections, knowledge gaps), KaTeX math, mermaid diagrams, wikilink resolution, audit feedback.

## 11. Browser Extension

1. Open Chrome → `chrome://extensions`
2. Enable "Developer mode"
3. Click "Load unpacked" → select `extension/` directory
4. Click the extension icon on any webpage → clips to markdown with frontmatter
5. Check "Auto-ingest after clip" to automatically trigger the ingest pipeline

## 12. Audit Reviews

```bash
# List open reviews
python3 skill/scripts/audit_review.py ~/my-wiki --open

# List resolved reviews
python3 skill/scripts/audit_review.py ~/my-wiki --resolved

# List all
python3 skill/scripts/audit_review.py ~/my-wiki --all
```

## 13. Performance Benchmarks

```bash
# Run benchmarks across 10/100/500/1000/5000 page wikis
python3 skill/scripts/benchmark.py /tmp/benchmark-results.csv
```

Outputs CSV with timing for: lint, graph build, graph insights, Python insights. Includes scaling factor analysis.

## 14. Migrate Old Wikis

```bash
# Convert v1 log.md → v2 log/ directory
python3 skill/scripts/migrate_log.py ~/my-old-wiki
```

## 15. Hermes Agent Install

```bash
# Symlink skill into Hermes (also offered by install.sh)
ln -sf $(pwd)/skill ~/.hermes/skills/research/llm-wiki

# Verify
ls ~/.hermes/skills/research/llm-wiki/SKILL.md
```

## Common Workflows

### Start a new research project
```bash
bash install.sh
python3 skill/scripts/scaffold.py ~/research-topic "Topic Name" --template research
python3 skill/scripts/deep_research.py ~/research-topic "key research question"
python3 skill/scripts/lint_wiki.py ~/research-topic
python3 skill/scripts/graph_insights.py ~/research-topic
```

### Add a codebase to a software wiki
```bash
python3 skill/scripts/scaffold.py ~/project-wiki "Project Name" --template codebase
python3 skill/scripts/ingest.py ~/project-wiki raw/articles/architecture.md
python3 skill/scripts/ingest.py ~/project-wiki raw/articles/api-docs.md
python3 skill/scripts/link_suggest.py ~/project-wiki --apply
python3 skill/scripts/lint_wiki.py ~/project-wiki
```

### Weekly health check (cron)
```bash
python3 skill/scripts/lint_wiki.py ~/my-wiki
node graph-engine/dist/index.js --wiki ~/my-wiki --action build
node graph-engine/dist/index.js --wiki ~/my-wiki --action insights
python3 skill/scripts/audit_review.py ~/my-wiki --open
python3 skill/scripts/backup.py ~/my-wiki --auto
```

### Full pipeline: source → analyzed wiki
```bash
# 1. One-command setup
git clone https://github.com/JeanBaissari/llm-wiki-monorepo.git
cd llm-wiki-monorepo
bash install.sh

# 2. Create wiki
python3 skill/scripts/scaffold.py ~/quant-wiki "Quant Research" --template algorithmic-trading

# 3. Add sources to raw/ (or use browser extension)
cp ~/research/*.md ~/quant-wiki/raw/articles/

# 4. Ingest (with agent loop — no API key)
LLM_WIKI_RESPONSE_FILE=~/stage1.txt python3 skill/scripts/ingest.py ~/quant-wiki ~/quant-wiki/raw/articles/strategy.md
LLM_WIKI_RESPONSE_FILE=~/stage2.txt python3 skill/scripts/ingest.py ~/quant-wiki ~/quant-wiki/raw/articles/strategy.md

# 5. Auto-link
python3 skill/scripts/link_suggest.py ~/quant-wiki --apply

# 6. Quality check
python3 skill/scripts/lint_wiki.py ~/quant-wiki

# 7. Graph analysis
node graph-engine/dist/index.js --wiki ~/quant-wiki --action build
node graph-engine/dist/index.js --wiki ~/quant-wiki --action insights

# 8. Backup
python3 skill/scripts/backup.py ~/quant-wiki --auto
```
