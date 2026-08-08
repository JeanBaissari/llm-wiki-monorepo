# CLI Reference — llm-wiki-monorepo

Full command reference for all `llm-wiki` CLI operations. For getting started, see [`docs/getting-started/quickstart.md`](../getting-started/quickstart.md). For MCP server and tool details, see [`docs/reference/mcp-tools.md`](mcp-tools.md).

## Two Paths to Run Commands

All Python operations have **two invocation paths** — both supported, neither deprecated:

| Path | Usage | Example |
|------|-------|---------|
| **`llm-wiki` CLI** | Pip-installed usage. Cleaner syntax, built-in aliases. | `llm-wiki scaffold ~/my-wiki "Title"` |
| **`python3 skill/scripts/`** | Hermes skill integration. Works without pip install. | `python3 skill/scripts/scaffold.py ~/my-wiki "Title"` |

> **Tip:** `llm-wiki` has short aliases — `sc` for scaffold, `in` for ingest, `ls` for lint, `bk` for backup, `dr` for deep-research, `lsug` for link-suggest.

---

## 1. Ingest Sources

```bash
# llm-wiki CLI (pip-installed usage)
llm-wiki ingest ~/my-wiki raw/articles/my-article.md
llm-wiki ingest ~/my-wiki raw/articles/my-article.md --force
llm-wiki ingest ~/my-wiki raw/articles/my-article.md --batch raw/articles/

# Alternative: direct script invocation (Hermes skill integration)
python3 skill/scripts/ingest.py ~/my-wiki raw/articles/my-article.md
python3 skill/scripts/ingest.py ~/my-wiki raw/articles/my-article.md --force
python3 skill/scripts/ingest.py ~/my-wiki raw/articles/my-article.md --batch raw/articles/
```

**Agent loop mode** (no API key needed):
```bash
# Pass 1: prints Stage 1 prompt → you respond with analysis → cached
LLM_WIKI_RESPONSE_FILE=~/stage1-response.txt llm-wiki ingest ~/my-wiki source.md

# Pass 2: uses cached analysis → prints Stage 2 prompt → you respond with pages
LLM_WIKI_RESPONSE_FILE=~/stage2-response.txt llm-wiki ingest ~/my-wiki source.md
```

**How two-step ingest works:**
1. Stage 1 (Analysis): LLM extracts entities, concepts, claims, relationships, contradictions
2. Stage 2 (Generation): LLM produces FILE blocks (wiki pages) + REVIEW blocks (issues to fix)
3. Result: pages created/updated, review items generated, index + log updated

---

## 2. Lint the Wiki

```bash
# llm-wiki CLI (pip-installed usage)
llm-wiki lint ~/my-wiki
llm-wiki lint ~/my-wiki --json

# Alternative: direct script invocation (Hermes skill integration)
python3 skill/scripts/lint_wiki.py ~/my-wiki
python3 skill/scripts/lint_wiki.py ~/my-wiki --json
```

**15 automated checks:** dead wikilinks, orphan pages, missing index entries, unlinked concepts, log/ shape, audit/ shape, audit targets, frontmatter validation, stale pages (>90 days), confidence signals, contradiction signals, page size (>200 lines), log rotation, SHA256 source drift, stale wiki pages from source drift.

---

## 3. Graph Insights

### Python engine (via CLI)

```bash
# llm-wiki CLI (pip-installed usage)
llm-wiki insights ~/my-wiki
llm-wiki insights ~/my-wiki --connections 10 --gaps 10
llm-wiki insights ~/my-wiki --format json

# Alternative: direct script invocation (Hermes skill integration)
python3 skill/scripts/graph_insights.py ~/my-wiki
python3 skill/scripts/graph_insights.py ~/my-wiki --connections 10 --gaps 10
python3 skill/scripts/graph_insights.py ~/my-wiki --format json
```

### TypeScript engine (production — no CLI equivalent)

```bash
# Build graph
node graph-engine/dist/index.js --wiki ~/my-wiki --action build

# Get insights (requires build first)
node graph-engine/dist/index.js --wiki ~/my-wiki --action insights

# Search graph
node graph-engine/dist/index.js --wiki ~/my-wiki --action search --query "strategy"

# Get related nodes
node graph-engine/dist/index.js --wiki ~/my-wiki --action relevance --node "entities/xau-swinger"
```

> The TypeScript graph engine is a separate Node.js package — there's no `llm-wiki` CLI wrapper for it.

---

## 4. Link Suggestions

```bash
# llm-wiki CLI (pip-installed usage)
llm-wiki link-suggest ~/my-wiki
llm-wiki link-suggest ~/my-wiki --apply
llm-wiki link-suggest ~/my-wiki --limit 10 --min-confidence 0.5
llm-wiki link-suggest ~/my-wiki --format json

# Alternative: direct script invocation (Hermes skill integration)
python3 skill/scripts/link_suggest.py ~/my-wiki
python3 skill/scripts/link_suggest.py ~/my-wiki --apply
python3 skill/scripts/link_suggest.py ~/my-wiki --limit 10 --min-confidence 0.5
python3 skill/scripts/link_suggest.py ~/my-wiki --format json
```

Entity extraction from frontmatter, headings, and bold terms. 4-signal scoring: frequency, position, type affinity, commonality penalty.

---

## 5. Deep Research

```bash
# llm-wiki CLI (pip-installed usage)
llm-wiki deep-research ~/my-wiki "transformer attention mechanisms"
llm-wiki deep-research ~/my-wiki "topic" --urls "https://arxiv.org/abs/1706.03762,https://example.com/article"
llm-wiki deep-research ~/my-wiki "topic" --depth 3 --sources 10

# Alternative: direct script invocation (Hermes skill integration)
python3 skill/scripts/deep_research.py ~/my-wiki "transformer attention mechanisms"
python3 skill/scripts/deep_research.py ~/my-wiki "topic" --urls "https://arxiv.org/abs/1706.03762,https://example.com/article"
python3 skill/scripts/deep_research.py ~/my-wiki "topic" --depth 3 --sources 10
```

---

## 6. Backup & Recovery

```bash
# llm-wiki CLI (pip-installed usage)
llm-wiki backup ~/my-wiki --snapshot
llm-wiki backup ~/my-wiki --list
llm-wiki backup ~/my-wiki --restore 20260622-143000
llm-wiki backup ~/my-wiki --verify
llm-wiki backup ~/my-wiki --prune 5
llm-wiki backup ~/my-wiki --auto

# Alternative: direct script invocation (Hermes skill integration)
python3 skill/scripts/backup.py ~/my-wiki --snapshot
python3 skill/scripts/backup.py ~/my-wiki --list
python3 skill/scripts/backup.py ~/my-wiki --restore 20260622-143000
python3 skill/scripts/backup.py ~/my-wiki --verify
python3 skill/scripts/backup.py ~/my-wiki --prune 5
python3 skill/scripts/backup.py ~/my-wiki --auto
```

**Operations:**
- `--snapshot` — Create a timestamped tar.gz snapshot
- `--list` — List all available backups
- `--restore <TIMESTAMP>` — Restore from a specific backup
- `--verify` — Check wiki integrity (wikilinks, frontmatter, required files)
- `--prune N` — Keep only the N most recent backups
- `--auto` — One-command safe state: snapshot + prune to 10 + verify

---

## 7. Audit Reviews

```bash
# llm-wiki CLI (pip-installed usage)
llm-wiki audit ~/my-wiki --open
llm-wiki audit ~/my-wiki --resolved
llm-wiki audit ~/my-wiki --all

# Alternative: direct script invocation (Hermes skill integration)
python3 skill/scripts/audit_review.py ~/my-wiki --open
python3 skill/scripts/audit_review.py ~/my-wiki --resolved
python3 skill/scripts/audit_review.py ~/my-wiki --all
```

---

## 8. Performance Benchmarks

```bash
# llm-wiki CLI (pip-installed usage)
llm-wiki benchmark /tmp/benchmark-results.csv

# Alternative: direct script invocation (Hermes skill integration)
python3 skill/scripts/benchmark.py /tmp/benchmark-results.csv
```

Outputs CSV with timing for: lint, graph build, graph insights, Python insights. Includes scaling factor analysis across 10/100/500/1000/5000 page wikis.

---

## 9. Wiki Structure Discovery

```bash
# llm-wiki CLI (pip-installed usage)
llm-wiki discover ~/my-wiki
llm-wiki discover ~/my-wiki --json
llm-wiki discover ~/my-wiki --show

# Alternative: direct script invocation (Hermes skill integration)
python3 skill/scripts/discover.py ~/my-wiki
python3 skill/scripts/discover.py ~/my-wiki --json
python3 skill/scripts/discover.py ~/my-wiki --show
```

Auto-detects wiki layout: content pages, source documents, log/audit directories, page type taxonomy, frontmatter conventions. Used internally by all other tools.

---

## 10. Migrate Old Wikis

```bash
# llm-wiki CLI (pip-installed usage)
llm-wiki migrate-log ~/my-old-wiki

# Alternative: direct script invocation (Hermes skill integration)
python3 skill/scripts/migrate_log.py ~/my-old-wiki
```

Converts v1 `log.md` → v2 `log/` directory structure.

---

## 11. Hermes Agent Install

```bash
# Symlink skill into Hermes (also offered by install.sh)
ln -sf $(pwd)/skill ~/.hermes/skills/research/llm-wiki

# Verify
ls ~/.hermes/skills/research/llm-wiki/SKILL.md
```

No `llm-wiki` CLI equivalent — this configures the Hermes skill integration.

---

## Common Workflows

### Start a new research project
```bash
bash install.sh
llm-wiki scaffold ~/research-topic "Topic Name" --template research
llm-wiki deep-research ~/research-topic "key research question"
llm-wiki lint ~/research-topic
llm-wiki insights ~/research-topic
```

### Add a codebase to a software wiki
```bash
llm-wiki scaffold ~/project-wiki "Project Name" --template codebase
llm-wiki ingest ~/project-wiki raw/articles/architecture.md
llm-wiki ingest ~/project-wiki raw/articles/api-docs.md
llm-wiki link-suggest ~/project-wiki --apply
llm-wiki lint ~/project-wiki
```

### Weekly health check (cron)
```bash
llm-wiki lint ~/my-wiki
node graph-engine/dist/index.js --wiki ~/my-wiki --action build
node graph-engine/dist/index.js --wiki ~/my-wiki --action insights
llm-wiki audit ~/my-wiki --open
llm-wiki backup ~/my-wiki --auto
```

### Full pipeline: source → analyzed wiki
```bash
# 1. One-command setup
git clone https://github.com/JeanBaissari/llm-wiki-monorepo.git
cd llm-wiki-monorepo
bash install.sh

# 2. Create wiki
llm-wiki scaffold ~/quant-wiki "Quant Research" --template algorithmic-trading

# 3. Add sources to raw/ (or use browser extension)
cp ~/research/*.md ~/quant-wiki/raw/articles/

# 4. Ingest (with agent loop — no API key)
LLM_WIKI_RESPONSE_FILE=~/stage1.txt llm-wiki ingest ~/quant-wiki ~/quant-wiki/raw/articles/strategy.md
LLM_WIKI_RESPONSE_FILE=~/stage2.txt llm-wiki ingest ~/quant-wiki ~/quant-wiki/raw/articles/strategy.md

# 5. Auto-link
llm-wiki link-suggest ~/quant-wiki --apply

# 6. Quality check
llm-wiki lint ~/quant-wiki

# 7. Graph analysis
node graph-engine/dist/index.js --wiki ~/quant-wiki --action build
node graph-engine/dist/index.js --wiki ~/quant-wiki --action insights

# 8. Backup
llm-wiki backup ~/quant-wiki --auto
```

## 14. Tuning Constants (`llm-wiki tuning`)

One canonical config surface for every precision-steering constant (LWM_031 /
ADR-0028): relevance weights + type-affinity matrix, insights thresholds +
signal scores, community resolution/seed, RRF k / sim floor, BM25 k1/b, claim
penalties. Precedence: `--set` > `LLM_WIKI_TUNE__*` env > `<wiki>/tuning.toml` >
code defaults (unchanged). See [docs/reference/tuning.md](tuning.md).

```bash
# Show the resolved profile (defaults + active overrides):
llm-wiki tuning ~/my-wiki

# Emit the graph-engine JSON profile (stdout or file):
llm-wiki tuning ~/my-wiki --json
llm-wiki tuning ~/my-wiki --emit /tmp/tuning.json

# One-off sweep (highest precedence, never persisted):
llm-wiki tuning ~/my-wiki --set relevance.directLink=5 --set community.resolution=1.3 --json
```

`--set section.key=value` is also accepted on `search`, `insights` and
`claims redteam` (e.g. `llm-wiki search ~/my-wiki "q" --set retrieval.simFloor=0.5`,
`llm-wiki insights ~/my-wiki --set insights.sparseCohesionThreshold=0.3`,
`llm-wiki claims redteam ~/my-wiki --set claims.failBelow=60`), and the
graph-engine CLI accepts `--tuning-json <path>` on its build/insights/relevance
actions.

```bash
# Feed the resolved profile to the TypeScript graph-engine (no TS re-derivation):
llm-wiki tuning ~/my-wiki --emit /tmp/tuning.json
node graph-engine/dist/index.js --wiki ~/my-wiki --action build --tuning-json /tmp/tuning.json
node graph-engine/dist/index.js --wiki ~/my-wiki --action insights --tuning-json /tmp/tuning.json
```
