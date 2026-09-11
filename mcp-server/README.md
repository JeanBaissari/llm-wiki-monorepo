# mcp-server

Standalone [Model Context Protocol](https://modelcontextprotocol.io) server for
LLM Wiki. It exposes **15 tools** over stdio so any MCP client (Claude, Codex,
opencode, Cursor) can read, search, lint, ingest into, and back up a wiki.

## What it does

Tools (all prefixed `llm_wiki_`):

| Tool | Side effect | Purpose |
|------|-------------|---------|
| `llm_wiki_status` | read-only | Health, page count, last ingest, open reviews |
| `llm_wiki_files` | read-only | File tree of `wiki/`, `raw/`, or all |
| `llm_wiki_read_file` | read-only | Read a project-relative file (truncated at 120KB) |
| `llm_wiki_reviews` | read-only | List audits/reviews by status |
| `llm_wiki_search` | read-only | Hybrid search (BM25 + semantic KNN via RRF; `mode: "keyword"` forces lexical) |
| `llm_wiki_ask` | read-only | Grounded citation retrieval (deterministic Python sidecar path) |
| `llm_wiki_graph` | write | Backward-compatible graph wrapper (`build`/`insights`/`search`) |
| `llm_wiki_graph_build` | write | Build the wikilink knowledge graph |
| `llm_wiki_graph_insights` | read-only | Surprising connections + knowledge gaps |
| `llm_wiki_graph_search` | read-only | Search graph nodes |
| `llm_wiki_lint` | external | Run the Python lint suite |
| `llm_wiki_ingest` | write | Ingest a source file (Python sidecar) |
| `llm_wiki_suggest_links` | read-only | Missing-wikilink suggestions |
| `llm_wiki_backup` | write | Timestamped snapshot with integrity verification |
| `llm_wiki_discover_entities` | read-only | Entity registry, optionally filtered by `entity_type` |

Most Python-backed tools — ingest, lint, ask, search, suggest-links, entities,
backup, and status — run through a long-lived **Python sidecar**
(`skill/scripts/sidecar.py`), auto-started at server launch. The graph tools
import `graph-engine` directly — no subprocess.

## Build

```bash
# From the repo root (installs all workspaces):
npm install

# Build dependencies first, then this package:
cd packages/shared-types && npm run build
cd ../../graph-engine && npm run build
cd ../mcp-server && npm run build
```

`bash install.sh` from the repo root does the same in order. From the repo root
you can also run `npm run build` (all workspaces) or
`npm run build --workspace mcp-server`. `npm run typecheck` and `npm run dev`
(tsx, no build) are available.

## Usage

```bash
# Single wiki
node mcp-server/dist/main.js --wiki /path/to/wiki-root

# Multi-wiki mode — every subdirectory of the path is scanned for wikis;
# tool calls then accept a `project` parameter.
node mcp-server/dist/main.js --projects /path/to/wikis
```

`--wiki` and `--projects` are mutually exclusive. With neither, the server
falls back to the `LLM_WIKI_PATH` environment variable. `python3` must be on
`PATH` for the sidecar.

Client registration (Claude, Codex, opencode, `llm-wiki setup`) and the full
parameter reference: [docs/reference/mcp-tools.md](../docs/reference/mcp-tools.md).
Hermes/agent wiring: [skill/SKILL.md](../skill/SKILL.md).

## Test

```bash
npm test          # vitest run
npm run typecheck # tsc --noEmit
```

## Docs

- [Root README](../README.md) — project overview and architecture
- [docs/README.md](../docs/README.md) — documentation index
- [docs/reference/mcp-tools.md](../docs/reference/mcp-tools.md) — tool parameters
- [AGENTS.md](../AGENTS.md) — repository conventions
