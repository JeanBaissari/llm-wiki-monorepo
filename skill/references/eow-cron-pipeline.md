# EOW Cron Pipeline — Concrete Pattern

This is the exact workflow executed by the weekly wiki/graphify cron job.
Use this as the template for future EOW runs.

## Step 1: Discover repos with wikis

```bash
find ~/projects -maxdepth 3 -type d -name 'wiki' 2>/dev/null
find ~/projects -maxdepth 3 -type d -name '.graphify' 2>/dev/null
```

## Step 2: Assess each repo

For each repo with a wiki/ directory:
- Check if `CLAUDE.md`, `index.md`, and `log/` directory exist
- Count wiki pages: `find wiki/ -name '*.md' | wc -l`
- Check graph freshness: `wiki/graphs/graph-data.json` mtime
- Check recent log entries for context

## Step 3: Graph-engine build (always)

```bash
LLM_WIKI_MONOREPO="$HOME/projects/llm-wiki-monorepo"
cd <repo-wiki-root>
node "$LLM_WIKI_MONOREPO/graph-engine/dist/index.js" --wiki . --action build
```

Outputs graph structure to stdout and optionally to `wiki/graphs/graph-data.json`.

## Step 3.5: Graph-engine insights (always)

```bash
node "$LLM_WIKI_MONOREPO/graph-engine/dist/index.js" --wiki . --action insights
```

Captures surprising connections and knowledge gaps. Include key findings in the health report.

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
- Don't commit `wiki/graphs/graph-data.json` — it's in `.gitignore`.
- Graph-engine can handle 1000+ pages. For very large wikis (>5000 pages), use `timeout 120`.
- The `graph_insights.py` script is a pure Python fallback — use graph-engine for production.
- Always run insights after graph build — the insight analysis depends on fresh graph data.
