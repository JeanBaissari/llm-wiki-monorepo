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
- Check if `SCHEMA.md`, `index.md`, `log.md` exist
- Count wiki pages: `find wiki/ -name '*.md' | wc -l`
- Check if `.graphify/graph.json` exists and its mtime
- Check recent log entries for context

## Step 3: Graphify update (conditional)

Only if `.graphify/` exists AND the graph is >3 days old:

```bash
export NODE_PATH=$(npm root -g)
cd <repo>
node -e "
const { detectIncremental } = require('@sentropic/graphify');
const result = detectIncremental('.');
console.log('new_total:', result.new_total || 0);
"
```

**Decision threshold:**
- `new_total == 0`: Nothing changed. Skip.
- `new_total <= 200`: Run AST-only merge + re-cluster (code-only or small change).
- `new_total > 200`: Skip rebuild. Log staleness. Don't spawn subagents for semantic extraction — token cost is prohibitive for cron.

**Never run full semantic extraction in cron mode** — requires subagents, LLM calls, and a user to approve.

## Step 4: Wiki lint (always)

```bash
python3 ~/.hermes/skills/research/llm-wiki/scripts/wiki-lint.py <wiki_path>
```

The script checks: orphan pages, broken wikilinks, index completeness, frontmatter, stale content, contradictions, quality signals, source drift, page size, tag audit.

## Step 5: Append to log.md

For each repo, append an entry like:
```
## [YYYY-MM-DD] EOW | Graph refresh + lint
- Graph: <status — existing, stale, N files changed, action taken>
- Lint: <N pages checked, N issues, breakdown by category>
- STATUS: <one-line health assessment>
```

## Step 6: Compile health report

One paragraph per repo. Cover:
- Page count + structural health
- Graph freshness (age, node/edge count, files changed)
- Most interesting finding (surprising connection, worst regression, contradiction surfaced)
- Recommended next action

## Pitfalls

- `detectIncremental` can take 30-120s on large repos (1,600+ files). Use `timeout 120`.
- `NODE_PATH` must be set for `require('@sentropic/graphify')` to resolve.
- The lint script exits with code 1 when issues are found — that's normal, not an error.
- Don't copy stale graph artifacts to `wiki/graphs/` — it's misleading. Just note the age.
- The `baissari-vbt-lab` wiki has no `SCHEMA.md` — the lint script flags this as a structural issue.
