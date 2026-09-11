# @baissari/llm-wiki-shared-types

Canonical TypeScript types shared across the monorepo. `graph-engine` and
`mcp-server` both import this package, so building it **first** is required for
a clean build of either consumer.

## Contents

- **Graph types** — `GraphNode`, `GraphEdge` (with optional `relType`,
  `directed`, `validFrom`/`validTo`, `observedAt`), `CommunityInfo`,
  `SurprisingConnection`, `KnowledgeGap`, `GraphData`, `GraphAction`.
- **MCP types** — `WikiProject`, `FileNode`, `SearchResult`, `ReviewItem`,
  `LintIssue`, `HealthStatus`.

```ts
import type { GraphNode, GraphEdge, GraphData } from "@baissari/llm-wiki-shared-types";
```

The graph types mirror what `graph-engine` writes to `<wiki-root>/graph-data.json`.

## Build

```bash
cd packages/shared-types
npm install
npm run build      # tsc → dist/ (index.js + index.d.ts)
```

Build order for consumers: `packages/shared-types` → `graph-engine` →
`mcp-server`. `bash install.sh` from the repo root builds everything in order.

## Test

```bash
npm test          # vitest run
npm run typecheck # tsc --noEmit
```

## Docs

- [Root README](../../README.md) — project overview
- [docs/README.md](../../docs/README.md) — documentation index
- [docs/reference/file-map.md](../../docs/reference/file-map.md) — file inventory
- [graph-engine](../../graph-engine) and [mcp-server](../../mcp-server) — consumers
- [AGENTS.md](../../AGENTS.md) — repository conventions
