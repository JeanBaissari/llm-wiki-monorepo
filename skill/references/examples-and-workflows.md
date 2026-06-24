# LLM Wiki — Examples & Workflows

Comprehensive reference covering everything from basic CLI usage to advanced agent-driven pipelines. Updated for current state (v0.1.1).

---

## 1. Repository Architecture — End State Vision

Once all phases are complete, the codebase will look like this:

```
llm-wiki-monorepo/
│
├── src/llm_wiki/          ← CANONICAL Python package (pip install)
│   ├── __init__.py
│   ├── cli.py             ← Unified CLI dispatcher
│   ├── scaffold.py
│   ├── ingest.py
│   ├── lint_wiki.py       ← 16 passes (15 wiki + 1 template validation)
│   ├── discover.py        ← Single source of truth for paths
│   ├── graph_insights.py
│   ├── link_suggest.py
│   ├── backup.py
│   ├── benchmark.py
│   ├── deep_research.py
│   ├── audit_review.py
│   ├── migrate_log.py
│   └── templates/         ← 19 templates shipped in wheel
│
├── skill/scripts/         ← DEPRECATED — thin wrappers with warning
│
├── tests/                 ← unittest suite (all operational scripts)
│   ├── test_scaffold.py
│   ├── test_discover.py
│   ├── test_lint.py
│   ├── test_backup.py
│   ├── test_ingest.py
│   ├── test_link_suggest.py
│   ├── test_graph_insights.py
│   └── test_cli.py
│
├── graph-engine/          ← TypeScript — wikilink + code graph
│   └── src/
│       ├── build.ts       ← Produces graph-data.json + code-graph.json
│       ├── insights.ts    ← Cross-graph surprising connections
│       ├── relevance.ts
│       └── louvain.ts
│
├── graph-bridge/          ← NEW npm package (@baissari/llm-wiki-graph-bridge)
│   └── src/
│       ├── ast-parser.ts  ← Wraps @sentropic/graphify AST extraction
│       ├── merger.ts      ← Merges wikilink + code graphs
│       └── types.ts
│
├── mcp-server/            ← TypeScript — 8 tools, multi-wiki
├── web-viewer/            ← TypeScript — search + graph panel + code overlay
├── extension/             ← Chrome — web clipper + auto-ingest
├── audit-shared/          ← TypeScript — audit schema
├── plugins/obsidian-audit/
│
├── docs/
│   ├── adr/               ← Architecture Decision Records
│   ├── examples/          ← Walkthrough galleries
│   └── api/               ← Python package API reference
│
├── CLAUDE.md → AGENTS.md  ← Symlink for agent compatibility
├── CONTRIBUTING.md
├── CHANGELOG.md
├── VERSIONING.md
│
├── pyproject.toml          ← PyPI: baissarienterprises-llm-wiki
├── package.json            ← npm workspace root
└── .github/workflows/
    ├── ci.yml              ← On push/PR: syntax, build, test, integration
    ├── release.yml         ← On tag: build, sign, publish
    └── nightly.yml         ← Scheduled: publish to TestPyPI
```

---

## 2. Current State (v0.1.1) Quick Reference

### Install

```bash
pip install baissarienterprises-llm-wiki

# Verify
llm-wiki --version          # → 0.1.1
llm-wiki --help             # → 11 available commands
```

### All Commands

| Command | Purpose |
|---------|---------|
| `llm-wiki scaffold <root> <title>` | Create a new wiki from 19 templates |
| `llm-wiki lint <root>` | 15-pass health check |
| `llm-wiki ingest <root> <source>` | Two-stage agent loop ingest |
| `llm-wiki discover <root>` | Auto-detect wiki structure |
| `llm-wiki insights <root>` | Graph analysis (surprising connections, gaps) |
| `llm-wiki link-suggest <root>` | Missing wikilink suggestions |
| `llm-wiki backup <root>` | Snapshot, restore, verify, prune |
| `llm-wiki deep-research <root> <topic>` | Web search → fetch → ingest → synthesize |
| `llm-wiki audit <root>` | List open/resolved reviews |
| `llm-wiki benchmark <csv>` | Performance benchmarks (10–5000 pages) |
| `llm-wiki migrate-log <root>` | Convert v1 log.md → v2 log/ |

---

## 3. Examples by Use Case

### 3.1 Individual Researcher

```bash
# Initialize
llm-wiki scaffold ~/research "Attention Mechanisms" --template research
llm-wiki discover ~/research
# → Method: wiki/ confidence=1.0

# Add sources
mkdir -p ~/research/raw/papers
cp ~/Downloads/attention-is-all-you-need.pdf ~/research/raw/papers/
# Extract text → save as .md in raw/

# Two-stage ingest (agent loop)
LLM_WIKI_RESPONSE_FILE=/tmp/stage1.txt \
  llm-wiki ingest ~/research ~/research/raw/papers/attention-is-all-you-need.md
# → Prints Stage 1 prompt (analysis)
# → You generate analysis, save to /tmp/stage1.txt
# → Re-run with same command → analysis cached (SHA256)

LLM_WIKI_RESPONSE_FILE=/tmp/stage2.txt \
  llm-wiki ingest ~/research ~/research/raw/papers/attention-is-all-you-need.md
# → Prints Stage 2 prompt (page generation)
# → You generate FILE/REVIEW blocks, save to /tmp/stage2.txt
# → Re-run → pages written to wiki/

# Connect the knowledge
llm-wiki link-suggest ~/research --apply

# Check quality
llm-wiki lint ~/research
# → ✅ Wiki is healthy — no issues found

# Analyze connections
llm-wiki insights ~/research --format json
# → Surprising connections between transformer architecture
#   and positional encoding cross community boundaries
# → Knowledge gaps: no dedicated "attention mechanism" page

# Generate a research synthesis
llm-wiki deep-research ~/research "attention mechanisms survey 2024"

# Protect your work
llm-wiki backup ~/research --auto
# → Snapshot created → pruned to 10 → integrity verified
```

### 3.2 Quant Trading Team

```bash
# 1. Scaffold strategy wiki
llm-wiki scaffold ~/quant-lab "Baissari VBT Lab" --template algorithmic-trading

# 2. Ingest the flagship strategy source
# (Using the agent loop approach)
llm-wiki ingest ~/quant-lab src/strategies/xau_swinger/strategy.py
# Stage 1: agent analyzes → produces entity/concept/claim extraction
# Stage 2: agent produces pages for:
#   - XAU Swinger Strategy (concept)
#   - Signal Adapter (entity)
#   - Filter Chain (concept)
#   - Money Management (concept)

# 3. Ingest the parameter config (481-line YAML)
llm-wiki ingest ~/quant-lab configs/strategies/xau_swinger.yaml
# Stage 2 produces:
#   - XAU Swinger Configuration (reference page with all 313 params)
#   - Self-adjusting Baseline (concept)
#   - Regime Filter (entity)

# 4. Ingest risk system
llm-wiki ingest ~/quant-lab src/risk/drawdown.py
# Stage 2 produces:
#   - DDZone Tracker (entity)
#   - GREEN/YELLOW/ORANGE/RED zones (concept)
#   - Drawdown Methodology (synthesis)

# 5. Connect everything
llm-wiki link-suggest ~/quant-lab --apply --min-confidence 0.5
# → Suggests: "XAU Swinger Strategy" mentions "DDZone Tracker" → adds [[DDZone Tracker]]
# → Suggests: "Signal Adapter" is also referenced in config → adds [[XAU Swinger Configuration]]

# 6. Quality gate
llm-wiki lint ~/quant-lab

# 7. Graph analysis (TypeScript engine)
node graph-engine/dist/index.js --wiki ~/quant-lab --action build
node graph-engine/dist/index.js --wiki ~/quant-lab --action insights
# → 3 communities detected: Strategies, Risk, Configuration
# → 2 surprising cross-community connections found
# → 1 knowledge gap: no page linking "Filter Chain" to market data

# 8. Backup the now-valuable knowledge base
llm-wiki backup ~/quant-lab --auto

# 9. Start MCP server for agent access
node mcp-server/dist/index.js --wiki ~/quant-lab

# 10. Open web viewer for team browsing
# (separate terminal)
cd web-viewer && npm start -- --wiki ~/quant-lab --port 4175
# → http://localhost:4175 — search, browse, graph insights
```

### 3.3 Software Engineering Team

```bash
# Onboard a new codebase
llm-wiki scaffold ~/api-docs "Payment API" --template codebase

# Document the architecture by ingesting source files
llm-wiki ingest ~/api-docs src/routes/payments.py
llm-wiki ingest ~/api-docs src/models/transaction.py
llm-wiki ingest ~/api-docs src/services/webhook.py

# Auto-link between architecture, modules, and APIs
llm-wiki link-suggest ~/api-docs --apply

# Before any major refactor, snapshot the current knowledge
llm-wiki backup ~/api-docs --snapshot

# After refactor, detect stale pages
llm-wiki lint ~/api-docs
# → "Payment Router: source file has changed since ingest" (Pass 15)
```

### 3.4 AI Agent Orchestration (OpenCode/Claude Code)

Prompt to Claude Code or OpenCode:

```
Load the llm-wiki Hermes skill and analyze my project at ~/projects/baissari-vbt-lab.
Create a complete knowledge base: discover, scaffold, ingest all core strategy
files, auto-link everything, run quality checks, and produce a graph insights
report. Then start an MCP server so I can query the wiki from this agent session.
```

The agent executes autonomously:

```bash
# Step 1: Discover
llm-wiki discover ~/projects/baissari-vbt-lab --json
# → Detects existing wiki/ directory, pre-existing AGENTS.md

# Step 2: Scaffold with template (adds missing directories)
llm-wiki scaffold ~/projects/baissari-vbt-lab \
  "Baissari VBT Lab" --template algorithmic-trading --force

# Step 3: Discover again (verify new structure)
llm-wiki discover ~/projects/baissari-vbt-lab --json
# → Method: wiki/ confidence=1.0, page types: strategies/, backtests/, risk/

# Step 4: Batch ingest core sources (agent generates both stages)
for f in src/strategies/base.py src/strategies/xau_swinger/strategy.py \
         src/backtest/engine.py src/risk/drawdown.py configs/strategies/xau_swinger.yaml; do
  echo "=== Ingesting $f ==="
  LLM_WIKI_RESPONSE_FILE=/tmp/s1.txt llm-wiki ingest ~/projects/baissari-vbt-lab $f
  LLM_WIKI_RESPONSE_FILE=/tmp/s2.txt llm-wiki ingest ~/projects/baissari-vbt-lab $f
done

# Step 5: Auto-link
llm-wiki link-suggest ~/projects/baissari-vbt-lab --apply

# Step 6: Quality gate
llm-wiki lint ~/projects/baissari-vbt-lab

# Step 7: Graph analysis
node graph-engine/dist/index.js --wiki ~/projects/baissari-vbt-lab --action insights

# Step 8: Backup
llm-wiki backup ~/projects/baissari-vbt-lab --auto

# Step 9: Start MCP server
node mcp-server/dist/index.js --wiki ~/projects/baissari-vbt-lab
```

---

## 4. MCP Integration

### 4.1 Claude Desktop

**Configuration:**
```json
{
  "mcpServers": {
    "llm-wiki": {
      "command": "node",
      "args": [
        "/path/to/llm-wiki-monorepo/mcp-server/dist/index.js",
        "--projects", "/path/to/wikis"
      ]
    }
  }
}
```

**Multi-wiki mode:** Serve all wikis from a directory. Each tool call includes a `project` parameter.

**Available tools (8):**

| Tool | Description | Example |
|------|-------------|---------|
| `llm_wiki_status` | Health, page count, open reviews | `{ "project": "quant-lab" }` |
| `llm_wiki_files` | File tree listing | `{ "project": "quant-lab", "scope": "wiki" }` |
| `llm_wiki_read_file` | Read any file (120KB limit) | `{ "project": "quant-lab", "path": "wiki/concepts/xau_swinger.md" }` |
| `llm_wiki_reviews` | List review items | `{ "project": "quant-lab", "status": "open" }` |
| `llm_wiki_search` | BM25 full-text search | `{ "project": "quant-lab", "query": "drawdown protection" }` |
| `llm_wiki_graph` | Build/insights/search | `{ "project": "quant-lab", "action": "insights" }` |
| `llm_wiki_lint` | Run lint checks | `{ "project": "quant-lab" }` |
| `llm_wiki_ingest` | Trigger ingest on a source | `{ "project": "quant-lab", "source": "raw/articles/new-paper.md" }` |

**Example agent prompt with MCP:**

```
User: "What does the wiki know about drawdown protection?"

Claude (via MCP):
  → llm_wiki_search({ project: "quant-lab", query: "drawdown protection" })
  → 3 results: "DDZone Tracker" (score 0.92),
               "Stop-Loss Savior" (score 0.78),
               "Risk Manager" (score 0.65)
  → llm_wiki_read_file({ project: "quant-lab",
                         path: "wiki/entities/ddzone_tracker.md" })
  → Reads the full page
  → Returns: "The DDZone Tracker implements a four-zone system:
               GREEN (<50% drawdown), YELLOW (50-75%), ORANGE (75-90%),
               RED (>90%). Connected to the Halt Manager for automatic
               circuit breaking..."
```

### 4.2 Codex CLI

```bash
# In Codex CLI, configure the MCP server:
codex mcp add llm-wiki -- \
  node /path/to/llm-wiki-monorepo/mcp-server/dist/index.js \
  --wiki /path/to/your-wiki

# Then in conversation:
# User: "What strategies do we have?"
# Codex: (calls llm_wiki_files → llm_wiki_status → reports)
```

### 4.3 OpenCode

In your OpenCode JSON config:

```json
{
  "mcpServers": {
    "llm-wiki": {
      "command": "node",
      "args": ["/path/to/mcp-server/dist/index.js", "--projects", "/path/to/wikis"],
      "env": {}
    }
  }
}
```

---

## 5. Agent Skill Workflows

### 5.1 Hermes Skill Integration

The `skill/` directory is a Hermes-compatible skill. Symlink it:

```bash
ln -sf /path/to/llm-wiki-monorepo/skill ~/.hermes/skills/research/llm-wiki
```

The skill defines 8 operations: `compile`, `ingest`, `ingest-2step`, `query`, `lint`, `audit`, `research`, `insights`.

When the Hermes cron loads this skill, it runs the EOW pipeline automatically:

```
Cron triggers → skill loaded → discover repos → for each repo:
  1. Assess health (page count, graph age, recent log entries)
  2. Build graph (or conditional rebuild if stale)
  3. Run insights (surprising connections + knowledge gaps)
  4. Run lint (15 passes)
  5. Compile health report
  6. Append to log/
```

### 5.2 Autonomous Research Pipeline

Prompt to an AI agent (OpenCode, Claude Code):

```
I'm researching transformer attention mechanisms. Use the llm-wiki tools to:
1. Scaffold a research wiki
2. Deep-research the topic — search the web, fetch papers, ingest them
3. Auto-link all concepts
4. Run graph insights to find surprising connections
5. Generate a synthesis page
6. Backup the wiki
```

The agent expands this into:

```bash
llm-wiki scaffold ~/attention-research "Attention Mechanisms" --template research
llm-wiki deep-research ~/attention-research "transformer attention mechanisms survey"
llm-wiki deep-research ~/attention-research "multi-head attention variants" --urls "\
  https://arxiv.org/abs/1706.03762,\
  https://arxiv.org/abs/1908.03854,\
  https://arxiv.org/abs/2005.14165"
llm-wiki link-suggest ~/attention-research --apply
node graph-engine/dist/index.js --wiki ~/attention-research --action insights
llm-wiki lint ~/attention-research
llm-wiki backup ~/attention-research --auto
```

### 5.3 Weekly Maintenance Workflow

EOW cron pipeline (from `skill/references/eow-cron-pipeline.md`):

```bash
# For each discovered wiki:
node graph-engine/dist/index.js --wiki <repo> --action build
node graph-engine/dist/index.js --wiki <repo> --action insights
llm-wiki lint <repo>
python3 skill/scripts/graph_insights.py <repo> --format json
llm-wiki audit <repo> --open
llm-wiki backup <repo> --auto

# Compile report:
# - Page count + graph health
# - Top surprising connection
# - New knowledge gaps
# - Open review items
# - Backup status
```

---

## 6. The Extreme Scenario — Everything Working

This is what the system looks like when every component is live, every bridge is built, and every agent is connected.

### Infrastructure

```
                  ┌─────────────────────────────┐
                  │   Researcher's Laptop        │
                  │                              │
                  │  ┌─ pip installed Python ──┐ │
                  │  │  llm-wiki CLI (11 cmd) │ │
                  │  │  discover, scaffold,    │ │
                  │  │  ingest, lint, backup,  │ │
                  │  │  insights, link-suggest,│ │
                  │  │  deep-research, audit   │ │
                  │  └────────────────────────┘ │
                  │                              │
                  │  ┌─ npm installed ─────────┐ │
                  │  │  MCP Server (8 tools)   │ │
                  │  │  Graph Engine (merged)  │ │
                  │  │  Web Viewer (search +   │ │
                  │  │    graph + code overlay) │ │
                  │  └────────────────────────┘ │
                  │                              │
                  │  ┌─ Browser ───────────────┐ │
                  │  │  Extension (web clipper │ │
                  │  │  + auto-ingest)         │ │
                  │  │  Web Viewer (tab:       │ │
                  │  │  Pages/Search/Graph)    │ │
                  │  └────────────────────────┘ │
                  │                              │
                  │  ┌─ AI Agents ─────────────┐ │
                  │  │  Claude Desktop (MCP)   │ │
                  │  │  OpenCode (skill)       │ │
                  │  │  Codex CLI (MCP)        │ │
                  │  └────────────────────────┘ │
                  └─────────────────────────────┘
```

### A Day in the Life

```
08:00 — EOW cron runs on all wikis:
        • quant-lab: 47 pages, 312 wikilinks, 3 communities
        • attention-research: 23 pages, 89 wikilinks, 2 communities
        • api-docs: 12 pages, 45 wikilinks, 1 community
        → All healthy. Backups created. Report compiled.

08:30 — Researcher adds a new paper via browser extension:
        • Clicks extension → clips arXiv page
        • Auto-ingest triggers → new concepts detected
        • Link suggestions fire → connects to existing transformer theory

09:00 — Interacts via Claude Desktop:
        "What surprising connections did last week's rebuild find?"
        → MCP returns: "3 cross-community edges detected.
           'Linear Attention' ↔ 'Softmax Attention' crosses
           the Efficiency ↔ Quality community boundary."

10:00 — Agent runs deep research on a new topic:
        → Searches web, fetches 5 papers, ingests them
        → Auto-links to existing knowledge
        → Creates synthesis page comparing approaches

14:00 — Code review with graph overlay:
        → Graph insights show that the new PR's code changes
          affect modules connected to 3 different wiki topics
        → Reviewer sees the full impact before approving

17:00 — EOD backup:
        → All 3 wikis snapshotted, verified, pruned
        → Knowledge compounded for the day
        → Git commit: "docs: daily wiki update"
```

### Key Metrics at Scale

| Metric | Small Wiki | Medium Wiki | Large Wiki |
|--------|-----------|-------------|-----------|
| Pages | 50 | 500 | 5000 |
| Wikilinks | 300 | 5000 | 50000 |
| Lint time | <1s | 2s | 15s |
| Graph build | <1s | 3s | 30s |
| Graph insights | <1s | 5s | 45s |
| Backup size | 2 MB | 20 MB | 200 MB |
| Backup time | <1s | 3s | 20s |

All operations are linear or sub-linear (verified by `llm-wiki benchmark`).

---

## 7. Directory Structure Reference

### Scaffolded Wiki Layout

```
~/my-wiki/
├── CLAUDE.md                  ← Schema (from template)
├── PURPOSE.md                 ← Scope and goals
├── log/                       ← Daily operation log
│   └── 20260623.md
├── audit/                     ← Human feedback inbox
│   ├── 20260623-abcdef-review.md
│   └── resolved/
├── raw/                       ← Immutable source documents
│   ├── articles/
│   ├── papers/
│   ├── notes/
│   └── .cache/                ← SHA256-cached analysis
├── wiki/                      ← LLM-generated knowledge
│   ├── index.md               ← Page index (auto-updated)
│   ├── concepts/              ← Abstract concepts
│   ├── entities/              ← Named entities
│   ├── summaries/             ← Source summaries
│   ├── comparisons/           ← A vs B comparisons
│   ├── graphs/                ← Graph data exports
│   └── synthesis/             ← Deep research syntheses
├── outputs/                   ← Query answers
│   └── queries/
├── graph-data.json            ← Wikilink graph (generated)
└── code-graph.json            ← Code structure graph (generated, when applicable)
```

### Template Directories (19)

```
algorithmic-trading  (strategies/, backtests/, indicators/, risk/, modules/)
architecture         (diagrams/, services/, infrastructure/, decisions/)
business             (meetings/, decisions/, projects/, stakeholders/)
codebase             (architecture/, modules/, apis/, decisions/)
commodities          (metals/, energy/, agriculture/, correlations/)
copywriting          (copy/, frameworks/, personas/, campaigns/)
crypto               (protocols/, tokens/, defi/, regulations/)
cybersecurity        (vulnerabilities/, exploits/, tools/, advisories/)
decompilers          (formats/, opcodes/, tools/, findings/)
design-systems       (tokens/, components/, patterns/, guidelines/)
developer-tools      (tools/, workflows/, benchmarks/, integrations/)
finance              (markets/, instruments/, strategies/, reports/)
machine-learning     (models/, datasets/, experiments/, benchmarks/)
marketing            (channels/, campaigns/, analytics/, competitors/)
medicine             (conditions/, treatments/, studies/, terminology/)
personal-growth      (goals/, habits/, reflections/, journal/)
prompt-engineering   (techniques/, evaluations/, templates/, providers/)
reading              (characters/, themes/, plot-threads/, chapters/)
research             (methodology/, findings/, thesis/)
```
