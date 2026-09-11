# graph-engine

Knowledge graph engine for LLM Wiki. It builds a deterministic, offline graph
from the wiki's `[[wikilinks]]` — no external model, service, or network call —
then answers insight, search, and relevance queries over it.

- **Build** — nodes are wiki pages, edges are resolved wikilinks; communities via
  Louvain (`graphology-communities-louvain`), plus a 4-signal relevance model.
- **Insights** — surprising connections (cross-community, cross-type) and
  knowledge gaps (isolated nodes, sparse communities, bridge nodes).
- **Search** — ranked node search.
- **Relevance** — related nodes around a given node id.

## Build

```bash
# From the repo root (installs all workspaces):
npm install

# shared-types is imported by this package — build it first:
cd packages/shared-types && npm run build
cd ../../graph-engine && npm run build
```

The package's build script uses the root TypeScript install
(`node ../node_modules/typescript/bin/tsc`), so run `npm install` from the repo
root first. `bash install.sh` does everything. `npm run typecheck` is available.

## Usage

```bash
node graph-engine/dist/index.js --wiki <wiki-root> --action build
node graph-engine/dist/index.js --wiki <wiki-root> --action insights
node graph-engine/dist/index.js --wiki <wiki-root> --action search  --query "risk"
node graph-engine/dist/index.js --wiki <wiki-root> --action relevance --node <node-id>
```

- `--wiki` accepts the wiki root (parent of `wiki/`) or the pages directory
  directly. If `<path>/wiki/` exists, the graph is built from it, but
  `graph-data.json` is always written to the `--wiki` path.
- `build` writes **`<wiki-root>/graph-data.json`** (derived state — gitignored,
  do not commit) and prints the graph to stdout.
- `insights`, `search`, and `relevance` read `graph-data.json`; run `build`
  first.
- `--tuning-json <path>` consumes the resolved profile emitted by
  `llm-wiki tuning <wiki-root> --emit <path>`; without it, built-in defaults
  apply. See [docs/reference/tuning.md](../docs/reference/tuning.md).
- Large wikis: incremental rebuilds only, and cap runs with `timeout 120`
  (recommended at >1,000 pages). At >5,000 pages prefer the pure-Python
  fallback (`skill/scripts/graph_insights.py`) or a nightly build.

## Test

```bash
npm test          # vitest run
npm run typecheck # tsc --noEmit
```

## Docs

- [Root README](../README.md) — project overview
- [docs/README.md](../docs/README.md) — documentation index
- [docs/reference/tuning.md](../docs/reference/tuning.md) — tuning constants and `--tuning-json`
- [skill/references/graph-construction-strategies.md](../skill/references/graph-construction-strategies.md) — graph construction at scale
- [AGENTS.md](../AGENTS.md) — repository conventions
