# EOW Cron Pipeline — Concrete Pattern

This is the exact workflow executed by the weekly wiki maintenance cron job.
Use this as the template for future EOW runs.

## Step 1: Discover repos with wikis

```bash
find ~/projects -maxdepth 3 -type d -name 'wiki' 2>/dev/null
```

## Step 2: Assess each repo

For each repo with a wiki/ directory:
- Check if `CLAUDE.md`, `index.md`, and `log/` directory exist
- Count wiki pages: `find wiki/ -name '*.md' | wc -l`
- Check graph freshness: `<wiki-root>/graph-data.json` mtime
- Check recent log entries for context

## Step 3: Graph-engine build (conditional)

Rebuild only when `raw/` or `wiki/` changed since the last build (for example, keep a hash of the wiki file list alongside `graph-data.json` and compare). If nothing changed, skip to Step 3.5 and reuse the existing graph.

```bash
LLM_WIKI_MONOREPO="$HOME/projects/llm-wiki-monorepo"
cd <wiki-root>
node "$LLM_WIKI_MONOREPO/graph-engine/dist/index.js" --wiki . --action build
```

The engine writes `<wiki-root>/graph-data.json` and prints the graph structure to stdout. `graph-data.json` is derived state — gitignored, never committed.

## Step 3.5: Graph-engine insights (after a build, or against the existing graph)

```bash
node "$LLM_WIKI_MONOREPO/graph-engine/dist/index.js" --wiki . --action insights
```

Reads `graph-data.json`, so it requires at least one prior build. Captures surprising connections and knowledge gaps. Include key findings in the health report.

## Step 4: Wiki lint (always)

```bash
python3 "$LLM_WIKI_MONOREPO/skill/scripts/lint_wiki.py" <wiki-root>
```

The script checks: orphan pages, broken wikilinks, index completeness, frontmatter, stale content, contradictions, quality signals, source drift, page size, tag audit.

## Step 5: Graph insights analysis (pure Python fallback)

```bash
python3 "$LLM_WIKI_MONOREPO/skill/scripts/graph_insights.py" <wiki-root> --format markdown
```

Provides community detection, surprising cross-community connections, and knowledge gaps (isolated nodes, sparse communities, bridge nodes). Use when graph-engine is not available.

## Step 6: Append to log/

For each repo, append an entry to `log/YYYYMMDD.md`:
```
## [HH:MM] EOW | Graph build + lint + insights
- Graph: <N nodes, M edges, C communities, cohesion score>
- Lint: <N pages checked, N issues, breakdown by category>
- Insights: <X surprising connections, Y knowledge gaps>
- STATUS: <one-line health assessment>
```

## Step 7: Compile health report

One paragraph per repo. Cover:
- Page count + structural health
- Graph freshness (node/edge count, communities, cohesion)
- Most interesting finding (top surprising connection, worst regression, contradiction surfaced)
- Knowledge gaps (isolated nodes, sparse communities)
- Recommended next action

## Pitfalls

- The lint script exits with code 1 when issues are found — that's normal, not an error.
- Don't commit `<wiki-root>/graph-data.json` — it's in `.gitignore`.
- Cap long builds with `timeout 120` (recommended at >1,000 pages). For very large wikis (>5,000 pages), prefer the pure-Python `graph_insights.py` fallback or a nightly build instead of per-request rebuilds — same guidance as `graph-construction-strategies.md`.
- The `graph_insights.py` script is a pure Python fallback — use graph-engine for production.
- Run insights after a fresh build — the insight analysis reads `graph-data.json`, so it depends on that file existing.
- No external model or network call is involved: the graph is wikilink/entity-derived.
