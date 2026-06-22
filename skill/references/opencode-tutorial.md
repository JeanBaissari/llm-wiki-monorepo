# OpenCode + LLM Wiki — Three-Level Tutorial

This tutorial uses **[baissari-vbt-lab](https://github.com/JeanBaissari/baissari-vbt-lab)** — a production-grade quantitative research lab (VectorBT, XAUSwinger strategy, 731 tests) — as a real-world example. You'll learn how to use the llm-wiki-monorepo tools at three levels of depth.

---

## Level 1: Basic Operations — Individual Tool Use

These are single-command operations you can run against any existing project. No scaffold needed — the tools auto-discover the project's structure.

### 1. Discover What Already Exists

Before doing anything, ask the tools to tell you what they found:

```bash
# Point discover.py at the project root
python3 skill/scripts/discover.py ~/projects/baissari-vbt-lab
```

**Output:**
```
Wiki Layout Discovery: /home/jeanbaissari/.../baissari-vbt-lab
  Method:     wiki/
  Confidence: 0.71

Directories:
  Pages:      .../baissari-vbt-lab/wiki
  Sources:    .../baissari-vbt-lab/docs
  Logs:       (not found)
  Audits:     (not found)
  Outputs:    (not found)

Key Files:
  Index:      .../baissari-vbt-lab/wiki/index.md
  Schema:     (not found)
  Purpose:    (not found)

Page Types:
  - architecture/  (Architecture)
  - changelogs/    (Changelogs)
  - graphs/        (Graphs)
  - quick_guides/  (Quick Guides)

Frontmatter Required:  (none)
Frontmatter Optional:  (none)
Date Format:           %Y-%m-%d
```

It found the existing wiki with 4 page type directories, no CLAUDE.md (the project uses AGENTS.md instead), and no frontmatter conventions yet. Confidence is 0.71 — strong enough to trust the detection.

### 2. Check Wiki Health

```bash
python3 skill/scripts/lint_wiki.py ~/projects/baissari-vbt-lab
```

Lint runs all 15 passes against the auto-discovered `wiki/` directory. It will flag dead wikilinks, orphan pages, missing frontmatter, and pages without inbound links. This is your quality baseline.

### 3. Analyze the Knowledge Graph

```bash
# TypeScript engine (fast, accurate)
node graph-engine/dist/index.js --wiki ~/projects/baissari-vbt-lab --action build
node graph-engine/dist/index.js --wiki ~/projects/baissari-vbt-lab --action insights

# Python fallback (works anywhere, no deps)
python3 skill/scripts/graph_insights.py ~/projects/baissari-vbt-lab --format json
```

The existing wiki already has 13 pages. The graph analysis will reveal:
- **Surprising connections**: pages from different topics that link to each other
- **Knowledge gaps**: isolated pages with no inbound links, sparse topic clusters
- **Bridge nodes**: pages that connect multiple communities

### 4. Backup Before Making Changes

```bash
# One-command safe state
python3 skill/scripts/backup.py ~/projects/baissari-vbt-lab --auto

# Verify the backup is valid
python3 skill/scripts/backup.py ~/projects/baissari-vbt-lab --verify
```

This creates a timestamped tar.gz snapshot, prunes old backups (keeping 10), and verifies wikilink integrity.

### 5. Suggest Missing Links

```bash
# See ranked link suggestions
python3 skill/scripts/link_suggest.py ~/projects/baissari-vbt-lab --limit 15

# Auto-apply the best ones
python3 skill/scripts/link_suggest.py ~/projects/baissari-vbt-lab --apply --min-confidence 0.5
```

The tool extracts entity names from frontmatter and headings, then finds pages that mention each other without linking. For the VBT lab, this might suggest that an architecture page links to a backtesting page, or that a strategy config page links to its implementing class.

---

## Level 2: Medium Workflows — Composing Tools

### Workflow A: One-Command Research Lab Setup

Turn a fresh clone of baissari-vbt-lab into a cross-linked wiki:

```bash
# 1. Install the monorepo tools
cd ~/projects/llm-wiki-monorepo
bash install.sh

# 2. Create an algorithmic-trading wiki from the template
python3 skill/scripts/scaffold.py ~/projects/baissari-vbt-lab \
  "Baissari VBT Lab" \
  --template algorithmic-trading \
  --page-dirs "architecture,strategies,backtests,indicators,risk,optimization" \
  --force

# 3. Run discovery to verify the structure
python3 skill/scripts/discover.py ~/projects/baissari-vbt-lab --show
```

The `--template algorithmic-trading` creates the right directory structure with `strategies/`, `backtests/`, `indicators/`, `risk/` subdirectories.

### Workflow B: Ingest Source Documents into the Wiki

The heart of the system: compile raw source code and configs into living wiki pages.

```bash
# Ingest the XAUSwinger strategy source
# (uses the multi-step agent loop — no API key needed)
LLM_WIKI_RESPONSE_FILE=/tmp/stage1.txt \
  python3 skill/scripts/ingest.py ~/projects/baissari-vbt-lab \
  src/strategies/xau_swinger/strategy.py

# After generating the Stage 1 analysis and saving it to /tmp/stage1.txt,
# generate Stage 2 (FILE/REVIEW blocks) and save to /tmp/stage2.txt,
# then run the second pass:
LLM_WIKI_RESPONSE_FILE=/tmp/stage2.txt \
  python3 skill/scripts/ingest.py ~/projects/baissari-vbt-lab \
  src/strategies/xau_swinger/strategy.py
```

**What happens internally (agent loop):**

```
Pass 1:
  ingest.py prints Stage 1 prompt → you (or OpenCode) generates analysis →
  saves to /tmp/stage1.txt → re-run → Stage 1 reads analysis, caches it
  (SHA256), Stage 2 has nothing yet → exits with warning (expected)

Pass 2:
  Stage 1 hits cache → ingest.py prints Stage 2 prompt →
  you generate FILE/REVIEW blocks → saves to /tmp/stage2.txt →
  re-run → pages written to wiki/strategies/, reviews to audit/
```

Repeat for key source files:

```bash
# Core architecture
LLM_WIKI_RESPONSE_FILE=/tmp/s1.txt python3 skill/scripts/ingest.py \
  ~/projects/baissari-vbt-lab src/backtest/engine.py
LLM_WIKI_RESPONSE_FILE=/tmp/s2.txt python3 skill/scripts/ingest.py \
  ~/projects/baissari-vbt-lab src/backtest/engine.py

# Risk system
LLM_WIKI_RESPONSE_FILE=/tmp/s1.txt python3 skill/scripts/ingest.py \
  ~/projects/baissari-vbt-lab src/risk/drawdown.py
LLM_WIKI_RESPONSE_FILE=/tmp/s2.txt python3 skill/scripts/ingest.py \
  ~/projects/baissari-vbt-lab src/risk/drawdown.py

# Strategy config (481-line parameter reference)
LLM_WIKI_RESPONSE_FILE=/tmp/s1.txt python3 skill/scripts/ingest.py \
  ~/projects/baissari-vbt-lab configs/strategies/xau_swinger.yaml
LLM_WIKI_RESPONSE_FILE=/tmp/s2.txt python3 skill/scripts/ingest.py \
  ~/projects/baissari-vbt-lab configs/strategies/xau_swinger.yaml
```

### Workflow C: Auto-Link + Quality Check

After ingesting multiple sources, connect the pages and verify quality:

```bash
# 1. Auto-link: find entities across pages, insert [[wikilinks]]
python3 skill/scripts/link_suggest.py ~/projects/baissari-vbt-lab --apply

# 2. Full quality audit
python3 skill/scripts/lint_wiki.py ~/projects/baissari-vbt-lab

# 3. Graph analysis to see the emerging structure
node graph-engine/dist/index.js --wiki ~/projects/baissari-vbt-lab --action build
node graph-engine/dist/index.js --wiki ~/projects/baissari-vbt-lab --action insights

# 4. Snapshot the now-valuable knowledge base
python3 skill/scripts/backup.py ~/projects/baissari-vbt-lab --auto
```

### Workflow D: Create a Research Synthesis

After ingesting the XAUSwinger strategy, its config file, and the drawdown risk module, the wiki might have separate pages for each. Use the graph insights to discover connections:

```bash
python3 skill/scripts/graph_insights.py ~/projects/baissari-vbt-lab \
  --format markdown --connections 10 --gaps 10
```

**Typical findings:**
- **Surprising connection**: "XAU Swinger Strategy" ↔ "DDZone Tracker" cross community boundary (strategy ↔ risk)
- **Knowledge gap**: "Spread Model" page has no inbound links — nobody connected it to the strategies that use it
- **Bridge node**: "Data Loader" connects to 4 different communities (backtest, strategies, indicators, validation)

### Workflow E: Compare Backtest Runs via Graph

After ingesting the persistence module and backtest results:

```bash
python3 skill/scripts/link_suggest.py ~/projects/baissari-vbt-lab --apply

# The index should now show entries like:
#   - [[backtests/xau_swinger/runs/20260617_011758]]
#   - [[optimization/trial_9834]]
#   - [[strategies/xau_swinger/strategy]]

node graph-engine/dist/index.js --wiki ~/projects/baissari-vbt-lab --action build
node graph-engine/dist/index.js --wiki ~/projects/baissari-vbt-lab --action search \
  --query "xau swinger drawdown"
```

---

## Level 3: High-Level — OpenCode-Driven Agent Workflows

This is where the system becomes a force multiplier. An OpenCode agent (or Claude Code, Codex, etc.) orchestrates the entire pipeline autonomously — you set the objective, the agent executes.

### Scenario 1: "Understand a New Codebase"

**Prompt to OpenCode:**

```
Load the skill at ~/.hermes/skills/research/llm-wiki.
Then explore ~/projects/baissari-vbt-lab, compile a knowledge base,
and give me a 5-minute briefing on how this project works.
```

**What the agent does autonomously:**

```
1. Discover the project structure (discover.py)
2. Scaffold or adapt the wiki (scaffold.py --template algorithmic-trading)
3. Ingest core source files, one by one:
   - src/strategies/base.py (the strategy contract)
   - src/backtest/engine.py (the backtest engine)
   - src/strategies/xau_swinger/strategy.py (the flagship strategy)
   - src/risk/drawdown.py (the risk system)
   - configs/strategies/xau_swinger.yaml (the parameter reference)
4. Auto-link the resulting pages (link_suggest.py --apply)
5. Run lint to catch quality issues (lint_wiki.py)
6. Run graph insights to find surprising connections
7. Present a structured briefing with:
   - Architecture overview (from compiled wiki pages)
   - Key entities and their relationships
   - Surprising connections found by graph analysis
   - Knowledge gaps (what's not well documented)
```

### Scenario 2: "Deep-Dive into One Component"

**Prompt to OpenCode:**

```
In ~/projects/baissari-vbt-lab, the drawdown tracking system is critical.
Deep-research it: analyze the source code, compare it to academic literature
on drawdown measurement, and create a synthesis page with benchmarks.
```

**What the agent does:**

```
1. Read src/risk/drawdown.py, src/risk/ddzone.py, src/risk/manager.py
2. Ingest the source files into wiki pages
3. Run deep_research.py "drawdown measurement methods hedge fund industry"
4. The agent fetches sources, analyzes them, and creates a synthesis page
5. Auto-link the synthesis page to existing strategy and risk pages
6. Run lint to verify quality
7. Report: what was found, what's unique about this implementation,
   what academic sources were used, and any contradictions between
   the implementation and the literature
```

### Scenario 3: "Weekly Maintenance Cron"

**Prompt to OpenCode (scheduled via cron):**

```
Run the EOW pipeline on ~/projects/baissari-vbt-lab.
Report any regressions, staleness, or surprising graph changes.
```

**What the agent does (defined in eow-cron-pipeline.md):**

```
1. Discover repo structure
2. Run lint (15 passes) — flag new issues
3. Run graph build + insights — compare to last week
4. Run backup --auto — safe state
5. Compile health report:
   - Page count, structural health
   - New issues since last week
   - Most interesting new connection
   - Knowledge gaps that emerged
   - Recommended next actions
```

### Scenario 4: "Port an MQL4 Strategy — Document Everything"

**Prompt to OpenCode:**

```
I'm porting an MQL4 scalping strategy to ~/projects/baissari-vbt-lab.
Document the entire process: the original MT4 logic, the Python translation
decisions, the backtest results, and the optimization journey.
Create a living research narrative that I can share with my team.
```

**What the agent does:**

```
1. Create a research wiki scaffold
2. Ingest the original MQL4 source code into a "source" page
3. Ingest the Python translation into a "strategy" page
4. Create comparison pages for key translation decisions (e.g.,
   "MQL4 iCustom → Python indicator adapter", "MT4 TPSL → OrderManager")
5. After each backtest run, append results to the wiki
6. After each optimization phase, update the optimization page
7. Maintain a chronological narrative in the log
8. Run graph insights to show how this strategy connects to others
9. Final output: a complete, cross-linked research narrative that
   can be exported as a PDF report or shared as a live wiki
```

### Scenario 5: "Risk System Audit and Refactor"

**Prompt to OpenCode:**

```
Audit the risk module in ~/projects/baissari-vbt-lab. I need to
understand every risk control, how they interact, and whether
there are gaps. Create actionable documentation.
```

**What the agent does:**

```
1. Discover all risk-related source files (src/risk/, src/trading/)
2. Ingest each one into the wiki:
   - drawdown.py (DDZone, GREEN/YELLOW/ORANGE/RED)
   - halt_manager.py (circuit breaker logic)
   - sizing.py (position sizing algorithms)
   - sl_savior.py (stop-loss protection)
   - ecmf.py (equity curve management)
   - manager.py (risk coordinator)
   - order_management.py (pending orders, recovery)
3. Auto-link all risk pages to each other and to strategies
4. Run graph insights — find communities within the risk module
5. Identify gaps: which risk controls exist in the MT4 original
   that haven't been ported to Python yet?
6. Generate an audit report:
   - Risk control inventory (7 components found)
   - Interaction map (how they chain: DDZone → HaltManager → Sizing)
   - Coverage gaps (missing: volatility-based position sizing,
     correlation-based pair risk)
   - Recommended next actions (with priority)
7. Create REVIEW items for each gap (in audit/ directory)
```

---

## Key Insights From This Tutorial

| Level | Time Investment | Value |
|-------|----------------|-------|
| **1. Basic** | 2 minutes per command | Instant quality feedback, safety net |
| **2. Medium** | 10-30 minutes per workflow | Cross-linked knowledge, auto-discovered connections |
| **3. High** | Agent does it all | Living knowledge base that grows with the codebase |

The baissari-vbt-lab example demonstrates a pattern that works for any codebase:
- **Source files become wiki pages** via ingest
- **Configs become reference pages** (the 481-line XAU Swinger config is now a browsable, linkable document)
- **Backtest runs become data pages** linked to their strategy
- **Risk components become a connected graph** revealing interaction patterns
- **The log becomes a research narrative** — every experiment, every insight, every decision

The system compounds: the more you use it, the more connections it finds, the more valuable the wiki becomes.
