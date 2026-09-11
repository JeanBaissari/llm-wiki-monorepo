# web-viewer

Local web preview for an LLM Wiki. It renders wiki pages with **mermaid**
(client-side) and **KaTeX** (server-side), adds search and a knowledge-graph
panel, and lets you file audit feedback by selecting text.

## Features

- Pages tab — rendered markdown, mermaid diagrams, math, wikilinks.
- Search tab — keyword search over wiki pages with ranked snippets.
- Graph tab — graph insights plus an interactive graph overlay, including the
  optional derived-edge layer (`.index/derived-edges.json`).
- Open-audits sidebar — list, create, and resolve audit feedback from the
  browser. Files are written in the same schema as the Obsidian plugin.

## Build

```bash
cd web-viewer
npm install
npm run build      # bundles the client (build-client.mjs)
```

`npm start` runs the build automatically via a `prestart` script.

## Usage

```bash
npm start -- --wiki /path/to/wiki-root [--port 4175] [--host 127.0.0.1] [--author me]
```

- `-w, --wiki` (required) — wiki root produced by `scaffold.py`.
- `-p, --port` — default `4175`.
- `--host` — default `127.0.0.1` (loopback only).
- `--author` — name written into feedback files (default `$USER`).

**Security:** there is no authentication. Binding to a non-loopback host with
`--host` prints a warning and exposes the wiki for reading *and* writing to
anyone who can reach it — only do so on a trusted network or behind an
authenticating proxy. See
[docs/operations/security-and-boundaries.md](../docs/operations/security-and-boundaries.md).

## Test

```bash
npm test          # vitest run
npm run typecheck # tsc --noEmit
```

## Docs

- [Root README](../README.md) — project overview
- [docs/README.md](../docs/README.md) — documentation index
- [docs/operations/security-and-boundaries.md](../docs/operations/security-and-boundaries.md) — trust boundary
- [skill/references/audit-guide.md](../skill/references/audit-guide.md) — audit file format
- [AGENTS.md](../AGENTS.md) — repository conventions
