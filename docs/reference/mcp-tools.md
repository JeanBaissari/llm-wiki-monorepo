# MCP Tools — llm-wiki-monorepo

MCP server, web viewer, and browser extension reference. For CLI commands, see [`docs/reference/cli.md`](cli.md). For getting started, see [`docs/getting-started/quickstart.md`](../getting-started/quickstart.md).

---

## MCP Server

```bash
# Single-wiki mode
node mcp-server/dist/index.js --wiki ~/my-wiki

# Multi-wiki mode (serve all wikis in a directory)
node mcp-server/dist/index.js --projects ~/wikis

# Via env var
LLM_WIKI_PATH=~/my-wiki node mcp-server/dist/index.js
```

No `llm-wiki` CLI equivalent — the MCP server is a TypeScript package accessed via stdio.

**10 MCP Tools:**
- `llm_wiki_status` — Health, page count, last ingest, open reviews
- `llm_wiki_files` — File tree listing (wiki/sources/all)
- `llm_wiki_read_file` — Read any file (120KB limit)
- `llm_wiki_reviews` — List review items (open/resolved/all)
- `llm_wiki_search` — SQLite FTS5 full-text search
- `llm_wiki_graph` — Graph operations (build/insights/search)
- `llm_wiki_lint` — Run automated lint checks
- `llm_wiki_ingest` — Trigger two-step ingest on a source
- `llm_wiki_audit_save` — Save audit feedback responses
- `llm_wiki_links_suggest` — Suggest missing wikilinks

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
