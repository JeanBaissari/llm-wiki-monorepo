# MCP Tools — llm-wiki-monorepo

MCP server, web viewer, and browser extension reference. For CLI commands, see [`docs/reference/cli.md`](cli.md). For getting started, see [`docs/getting-started/quickstart.md`](../getting-started/quickstart.md).

---

## MCP Server

```bash
# Single-wiki mode
node mcp-server/dist/main.js --wiki ~/my-wiki

# Multi-wiki mode (serve all wikis in a directory)
node mcp-server/dist/main.js --projects ~/wikis

# Via env var
LLM_WIKI_PATH=~/my-wiki node mcp-server/dist/main.js
```

No `llm-wiki` CLI equivalent — the MCP server is a TypeScript package accessed via stdio.

**15 MCP Tools** (source of truth: `mcp-server/src/registry.ts`):

| Tool | Side effect | Purpose |
|------|-------------|---------|
| `llm_wiki_status` | read-only | Wiki health, page count, last ingest, open reviews |
| `llm_wiki_files` | read-only | File tree listing (wiki/sources/all) |
| `llm_wiki_read_file` | read-only | Read any project-relative file (120KB limit, allow-listed dirs) |
| `llm_wiki_reviews` | read-only | List review items (open/resolved/all) |
| `llm_wiki_search` | read-only | Search wiki pages — hybrid by default (BM25 + semantic KNN via RRF, LWM_032/ADR-0020); `mode="keyword"` forces lexical-only |
| `llm_wiki_ask` | read-only | Grounded "ask this wiki" QA — hybrid retrieval over pages + community summaries, deterministic `no_llm` passages mode (LWM_033) |
| `llm_wiki_graph` | write | Graph operations (build/insights/search) — backward-compatible wrapper |
| `llm_wiki_graph_build` | write | Build the knowledge graph from wiki markdown (direct graph-engine import) |
| `llm_wiki_graph_insights` | read-only | Graph insights — surprising connections and knowledge gaps |
| `llm_wiki_graph_search` | read-only | Search graph nodes matching a query |
| `llm_wiki_lint` | external | Run automated lint checks via Python sidecar |
| `llm_wiki_ingest` | write | Trigger two-step ingest on a source |
| `llm_wiki_suggest_links` | read-only | Suggest missing wikilinks with confidence scores (threshold/limit/pages params) |
| `llm_wiki_backup` | write | Timestamped tar.gz snapshot with integrity verification |
| `llm_wiki_discover_entities` | read-only | List the entity registry (names, paths, types, aliases; optional type filter) |

**Multi-wiki mode:** Add `"project": "project-name"` to tool call arguments.

**Claude Desktop config:**
```json
{
  "mcpServers": {
    "llm-wiki": {
      "command": "node",
      "args": ["/path/to/llm-wiki-monorepo/mcp-server/dist/main.js", "--projects", "/path/to/wikis"]
    }
  }
}
```

---

## Web Viewer

```bash
cd web-viewer
npm install
npm run build
npm start -- --wiki ~/my-wiki --port 4175
# Open http://127.0.0.1:4175
```

No `llm-wiki` CLI equivalent — the web viewer is a standalone TypeScript app.

**Features:** Search bar (TF-based ranking), graph insights panel (metrics, surprising connections, knowledge gaps), KaTeX math, mermaid diagrams, wikilink resolution, audit feedback.

---

## Browser Extension

1. Open Chrome → `chrome://extensions`
2. Enable "Developer mode"
3. Click "Load unpacked" → select `extension/` directory
4. Click the extension icon on any webpage → clips to markdown with frontmatter
5. Check "Auto-ingest after clip" to automatically trigger the ingest pipeline

No `llm-wiki` CLI equivalent — the extension is a standalone Chrome extension.
