# Knowledge Graph Construction Strategies

The wiki graph is built from the wiki itself: `[[wikilinks]]`, entity mentions,
and community structure. It is deterministic, offline, and requires no external
model, service, or code analysis. This reference covers construction at scale.

## Canonical builder: graph-engine

```bash
node graph-engine/dist/index.js --wiki <wiki-root> --action build      # → graph-data.json
node graph-engine/dist/index.js --wiki <wiki-root> --action insights   # surprises + gaps
node graph-engine/dist/index.js --wiki <wiki-root> --action relevance --node <id>
```

- Nodes are wiki pages; edges are resolved `[[wikilinks]]` (plus opted-in
  derived layers only when `--include-derived` is explicitly requested).
- Communities come from Louvain (default) or Leiden (`[leiden]` extra).
- The pure-Python fallback is `skill/scripts/graph_insights.py <wiki>` when
  Node/graph-engine is unavailable — same conceptual outputs.

## Scale guidance

| Wiki size | Approach |
|---|---|
| < 50 pages | Wikilinks + the viewer's built-in graph are sufficient; skip rebuilds |
| 50–1,000 pages | `graph-engine --action build` on every content-changing run; insights weekly |
| > 1,000 pages | Incremental rebuilds only when `raw/` or `wiki/` changed; cap with `timeout 120` |
| > 5,000 pages | Prefer the pure-Python `graph_insights.py` fallback or a nightly build; avoid per-request rebuilds |

## Keeping it fast and bounded

- Rebuild conditionally: hash the wiki file list and compare with the previous
  build fingerprint; skip when unchanged.
- Never run derived-edge generation inside a bounded cron window — it is an
  explicit, opt-in analysis (`llm-wiki derive-edges`).
- The graph is derived state: don't commit `graph-data.json` (it is gitignored).

## What the graph gives you

- **God nodes** — highest-degree pages (hub topics).
- **Surprising connections** — cross-community, cross-type edges.
- **Knowledge gaps** — isolated nodes, sparse communities, bridge nodes.
- **Communities** — Louvain/Leiden partitions with optional LLM summaries
  (`llm-wiki summarize-communities`, opt-in, drafted locally only when the
  agent provides a provider).
