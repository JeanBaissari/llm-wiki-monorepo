# Quick Start — llm-wiki-monorepo

> Ready to go from zero to a live wiki? This guide covers installation and your first wiki in minutes. For the full CLI command reference, see [`docs/reference/cli.md`](../reference/cli.md). For MCP server and tool details, see [`docs/reference/mcp-tools.md`](../reference/mcp-tools.md).

## Two Paths to Run Commands

All Python operations have **two invocation paths** — both supported, neither deprecated:

| Path | Usage | Example |
|------|-------|---------|
| **`llm-wiki` CLI** | Pip-installed usage. Cleaner syntax, built-in aliases. | `llm-wiki scaffold ~/my-wiki "Title"` |
| **`python3 skill/scripts/`** | Hermes skill integration. Works without pip install. | `python3 skill/scripts/scaffold.py ~/my-wiki "Title"` |

Each section below shows `llm-wiki` first, then the direct script invocation as the alternative.

> **Tip:** `llm-wiki` has short aliases — `sc` for scaffold, `in` for ingest, `ls` for lint, `bk` for backup, `dr` for deep-research, `lsug` for link-suggest.

---

## 1. One-Command Install

```bash
bash install.sh
```

Detects Python/Node versions, installs npm dependencies, builds all TypeScript packages, verifies all Python scripts, and optionally creates Hermes symlinks and PATH wrappers.

No `llm-wiki` equivalent — this sets up the monorepo itself.

---

## 2. Scaffold a Wiki

```bash
# llm-wiki CLI (pip-installed usage)
llm-wiki scaffold ~/my-wiki "My Research Topic"
llm-wiki scaffold ~/my-codebase-wiki "My Project" --template codebase
llm-wiki scaffold ~/strat-wiki "Strategy Lab" --template algorithmic-trading
llm-wiki scaffold --list-templates
llm-wiki scaffold ~/my-wiki "New Topic" --template codebase --force

# Alternative: direct script invocation (Hermes skill integration)
python3 skill/scripts/scaffold.py ~/my-wiki "My Research Topic"
python3 skill/scripts/scaffold.py ~/my-codebase-wiki "My Project" --template codebase
python3 skill/scripts/scaffold.py ~/strat-wiki "Strategy Lab" --template algorithmic-trading
python3 skill/scripts/scaffold.py --list-templates
python3 skill/scripts/scaffold.py ~/my-wiki "New Topic" --template codebase --force
```

**What it creates:**
```
<wiki-root>/
├── PURPOSE.md      ← Why this wiki exists
├── CLAUDE.md       ← Schema: conventions, page types, naming rules
├── log/            ← Per-day operation log
├── audit/          ← Human feedback inbox
├── raw/            ← Immutable source documents
├── wiki/           ← LLM-generated knowledge pages
└── outputs/        ← Query answers, charts
```

**20 domain templates available:** research, codebase, finance, algorithmic-trading, algorithmic-trading-mql4, cybersecurity, machine-learning, prompt-engineering, copywriting, marketing, design-systems, architecture, crypto, commodities, decompilers, medicine, developer-tools, personal-growth, reading, business.
