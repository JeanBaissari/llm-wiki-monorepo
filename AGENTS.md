# AGENTS.md — LLM Wiki Monorepo

> Read this first. It tells you what this repo is, how it's organized, and how to work on it.

## What this repo is

A complete knowledge base operating system. It takes raw source documents and AI agents produce and maintain a persistent, cross-linked Markdown wiki. Knowledge compounds over time.

**One repo. Any agent. Any machine.** `git clone` and you have everything.

## Architecture

```
                    wiki/ directory (markdown files)
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
   Agent Skill          MCP Server           Graph Engine
   (Python + MD)        (TypeScript)         (TypeScript)
   in-conversation      programmatic         relevance model
    workflows            14 tools via stdio    Louvain communities
                                             graph insights
```

The wiki directory is the shared state. Every component reads/writes the same markdown files. No database. No API lock-in. Just files.

## Package Map

| Dir | Language | What it does | When to touch it |
|-----|----------|-------------|-----------------|
| `skill/` | Python + MD | Agent skill: SKILL.md + 13 scripts + 10 references | Agent operations, scripts, docs |
| `mcp-server/` | TypeScript | MCP server: 14 tools via stdio | Programmatic wiki access |
| `graph-engine/` | TypeScript | Knowledge graph: build, relevance, Louvain, insights | Graph analysis, community detection |
| `templates/` | MD + JSON | 20 domain templates for scaffold.py | Adding/modifying project templates |
| `web-viewer/` | TypeScript | Local preview server: mermaid, KaTeX, feedback | UI changes |
| `extension/` | JavaScript | Chrome web clipper | Browser clipping |
| `audit-shared/` | TypeScript | Audit file format library | Audit schema changes |
| `plugins/obsidian-audit/` | TypeScript | Obsidian plugin | Vault integration |
| `rust-backend/` | _(removed)_ | Coming soon: multi-format doc parsing (PDF, DOCX, EPUB) | — |

## Build Commands

```bash
# Quick one-command install
bash install.sh

# Or step-by-step:
# Graph engine
cd graph-engine && npm install && npx tsc

# MCP server
cd mcp-server && npm install && npx tsc

# Web viewer
cd web-viewer && npm install && npm run build

# Audit shared (needed by web-viewer + obsidian plugin)
cd audit-shared && npm install && npm run build

# Obsidian plugin
cd plugins/obsidian-audit && npm install && npm run build
```

**Python scripts need no build** — they're interpreted directly.

## Test Commands

```bash
# Python scripts — syntax check
python3 -c "import py_compile; py_compile.compile('skill/scripts/<script>.py', doraise=True)"

# TypeScript — type check
cd <package> && npx tsc --noEmit

# Graph engine — functional test
node graph-engine/dist/index.js --wiki /path/to/wiki --action build

# MCP server — tool test
timeout 5 node mcp-server/dist/index.js --wiki /path/to/wiki <<< '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

# Full integration test
python3 skill/scripts/scaffold.py /tmp/test-wiki "Test" --template codebase --force
python3 skill/scripts/lint_wiki.py /tmp/test-wiki
node graph-engine/dist/index.js --wiki /tmp/test-wiki --action build
node graph-engine/dist/index.js --wiki /tmp/test-wiki --action insights
python3 skill/scripts/backup.py /tmp/test-wiki --auto
python3 skill/scripts/link_suggest.py /tmp/test-wiki --limit 5
python3 skill/scripts/graph_insights.py /tmp/test-wiki --format json
```

## CLI Reference

> All commands use the `llm-wiki` CLI. Both `llm-wiki <cmd>` and `python3 skill/scripts/<cmd>.py` paths are valid — CLI for users and CI, `skill/scripts/` for Hermes skill integration.

| Command | Purpose | Example |
|---------|---------|---------|
| `llm-wiki scaffold` | Bootstrap a new wiki | `llm-wiki scaffold ~/wikis/my-project "My Project" --template codebase` |
| `llm-wiki ingest` | Two-step CoT source ingestion | `llm-wiki ingest ~/wikis/my-project paper.pdf --llm openai` |
| `llm-wiki lint` | 15 automated wiki checks | `llm-wiki lint ~/wikis/my-project` |
| `llm-wiki discover` | Auto-detect wiki layout | `llm-wiki discover ~/wikis/my-project --json` |
| `llm-wiki insights` | Pure Python graph analysis | `llm-wiki insights ~/wikis/my-project --format json` |
| `llm-wiki backup` | Snapshot, restore, verify | `llm-wiki backup ~/wikis/my-project --auto` |
| `llm-wiki index` | Build FTS5 search index | `llm-wiki index ~/wikis/my-project --rebuild` |
| `llm-wiki link-suggest` | Missing wikilink detection | `llm-wiki link-suggest ~/wikis/my-project --apply` |
| `llm-wiki benchmark` | Synthetic wiki benchmarks | `llm-wiki benchmark /tmp/results.csv` |
| `llm-wiki audit` | List/group audit feedback | `llm-wiki audit ~/wikis/my-project --open` |
| `llm-wiki health` | Subsystem health check | `llm-wiki health ~/wikis/my-project` |
| `llm-wiki deep-research` | Multi-source research pipeline | `llm-wiki deep-research ~/wikis/my-project "transformer architectures"` |

Run `llm-wiki --help` for full command list and flags. Run `llm-wiki <command> --help` for command-specific options.

## Key Files to Know

| File | Why it matters |
|------|---------------|
| `skill/SKILL.md` | The agent skill — defines all 8 operations. Loaded by Hermes/Claude/Codex. |
| `skill/scripts/scaffold.py` | Creates new wikis. `--template` flag picks domain template. |
| `skill/scripts/ingest.py` | Two-step CoT ingest. Stage 1 analysis → Stage 2 generation. |
| `skill/scripts/discover.py` | Auto-discovers wiki structure (pages, sources, logs, audits) — single source of truth for all tools. |
| `skill/scripts/lint_wiki.py` | 15 automated checks with auto-discovered layout. Run this before committing wiki changes. |
| `skill/scripts/graph_insights.py` | Pure Python graph analysis — no graph-engine dependency. |
| `skill/scripts/backup.py` | Snapshot, restore, integrity verification — `--auto` one-command safe state. |
| `skill/scripts/link_suggest.py` | Suggests missing wikilinks from entities — `--apply` auto-adds them. |
| `skill/scripts/benchmark.py` | Performance benchmarks — synthetic wikis at 10/100/500/1000/5000 pages. |
| `mcp-server/src/index.ts` | MCP server entry. 14 tool handlers. Built with @modelcontextprotocol/sdk. |
| `graph-engine/src/index.ts` | Graph CLI. `--action build|insights|search|relevance`. |
| `graph-engine/src/relevance.ts` | 4-signal relevance model — ported from nashsu/llm_wiki. |
| `graph-engine/src/louvain.ts` | Louvain community detection — uses graphology library. |
| `templates/_shared/base-schema.md` | Base page types, frontmatter, naming conventions. All templates extend this. |

## Conventions

### Python scripts
- All use `argparse`
- **v0.2.0+: Managed dependencies** — see [Python Dependency Policy](#python-dependency-policy-v020) below. External packages installed via `pip` from `pyproject.toml`.
- Exit codes: 0 = success/clean, 1 = issues found, 2 = usage error
- Print structured output to stdout, errors/warnings to stderr

### TypeScript packages
- ES2022 modules, strict mode
- Build output in `dist/` (gitignored)
- Dependencies declared in `package.json` per package
- `npm install` from package directory, not root

### Wiki files
- YAML frontmatter on every page: `title`, `type`, `created`, `updated`, `sources`, `tags`
- Optional quality fields: `confidence`, `contested`, `contradictions`
- Wikilinks: `[[Page Name]]` — case-sensitive, exact title match
- Diagrams: mermaid only. No ASCII art.
- Formulas: KaTeX only. `$inline$` or `$$block$$`

### Templates
- `PURPOSE.md` — why this wiki exists
- `SCHEMA.md` — becomes `CLAUDE.md` at scaffold time
- `extra-dirs.json` — JSON array of extra `wiki/` subdirectories
- All templates extend `_shared/base-schema.md`

## Common Tasks

### "Add a new Python script"
1. Create `skill/scripts/<name>.py` with `#!/usr/bin/env python3` shebang
2. Use `argparse` for CLI
3. Add to `INDEX.md` scripts table
4. Add to `QUICKGUIDE.md` with examples
5. If it's a new operation, add to `skill/SKILL.md`

### "Add a new template"
1. Copy an existing template: `cp -r templates/codebase templates/<name>`
2. Edit `PURPOSE.md`, `SCHEMA.md`, `extra-dirs.json`
3. Add to `README.md` template list
4. Add to `INDEX.md` template table
5. Template auto-discovered by `scaffold.py --list-templates`

### "Fix a bug in the MCP server"
1. Edit `mcp-server/src/<file>.ts`
2. `cd mcp-server && npx tsc`
3. Test with: `timeout 5 node dist/index.js --wiki /tmp/test-wiki <<< '...'`
4. Commit with message prefix: "Fix MCP server: ..."

### "Fix a bug in the graph engine"
1. Edit `graph-engine/src/<file>.ts`
2. `cd graph-engine && npx tsc`
3. Test with: `node dist/index.js --wiki /tmp/test-wiki --action <action>`
4. Commit with message prefix: "Fix graph-engine: ..."

### "Run the full test suite"
```bash
# Python syntax
for f in skill/scripts/*.py; do
  python3 -c "import py_compile; py_compile.compile('$f', doraise=True)" && echo "OK $f"
done

# TypeScript type check
cd graph-engine && npx tsc --noEmit && echo "OK graph-engine"
cd ../mcp-server && npx tsc --noEmit && echo "OK mcp-server"

# Integration
python3 skill/scripts/scaffold.py /tmp/test-wiki "Test" --template codebase --force
python3 skill/scripts/lint_wiki.py /tmp/test-wiki
node graph-engine/dist/index.js --wiki /tmp/test-wiki --action build
node graph-engine/dist/index.js --wiki /tmp/test-wiki --action insights
python3 skill/scripts/graph_insights.py /tmp/test-wiki --format json
python3 skill/scripts/backup.py /tmp/test-wiki --auto
python3 skill/scripts/link_suggest.py /tmp/test-wiki --limit 5
rm -rf /tmp/test-wiki
```

## Pitfalls

- **Don't modify files in `raw/`** — sources are immutable. Corrections go in wiki pages.
- **Don't commit `dist/`** — it's in `.gitignore`. Build output is generated.
- **Don't commit `audit-C-report.md` or similar artifacts** — audit reports go in the wiki's audit/ directory, not the repo root.
- **graph-data.json is generated** — don't commit it. It's in `.gitignore`.
- **MCP server needs `__dirname` resolution** — don't use `process.cwd()` for resolving script paths. Use `path.resolve(__dirname, ...)`.
- **Graph engine CLI expects `--wiki` path** — it auto-detects `wiki/` subdirectory. Pass the project root (parent of wiki/) or the wiki/ directory directly.
- **scaffold.py refuses to overwrite** — use `--force` flag. Without it, existing wikis are protected.
- **Two-step ingest may be slow** — Stage 1 analysis is cached by SHA256. Use `--force` to skip cache.
- **discover.py is the single source of truth for paths** — all tools call it at startup. If you rename directories, run `python3 skill/scripts/discover.py <wiki> --show` to verify detection.
- **Flat wikis (no `wiki/` subdirectory) are supported** — discover.py auto-detects pages at root. Confidence is lower (0.14) but all tools work.
- **Custom directory names are supported** — discover.py checks content/, pages/, notes/ for content; sources/, input/ for raw; logs/, journal/ for logs.
- **All tools import discover.py via sys.path.insert** — when adding new scripts, add `from discover import discover_layout` and call it at startup.

## Hermes Skill Installation

The `skill/` directory is symlinked as a Hermes skill:

```bash
ln -sf /path/to/llm-wiki-monorepo/skill ~/.hermes/skills/research/llm-wiki
```

The EOW cron job loads this skill automatically. Changes to `skill/SKILL.md` or `skill/scripts/` propagate immediately — no restart needed.

## External Dependencies

- **graphology** + **graphology-communities-louvain** — graph-engine only. Pure JS, no native deps.
- **@modelcontextprotocol/sdk** — MCP server only. Pure JS.
- **Readability.js** + **Turndown.js** — Browser extension only. Already vendored.
- **Python (v0.2.0+):** openai, anthropic, litellm, instructor, tenacity, tiktoken, python-dotenv, pydantic, portalocker — specified in `pyproject.toml`. See [Python Dependency Policy](#python-dependency-policy-v020).
- No Rust dependencies. (`rust-backend/` removed — coming soon.)

## Python Dependency Policy (v0.2.0+)

**v0.1.x policy (retired):** Python scripts used pure stdlib only. No external packages.

**v0.2.0+ policy (current):** Managed Python dependencies specified in `pyproject.toml`. Pinned with minimum versions, selected on:

1. **Maturity:** ≥5k GitHub stars or official SDK from the provider
2. **Maintenance:** Active releases within the last 3 months
3. **License:** MIT, Apache 2.0, or BSD — no copyleft
4. **Size:** No dependency that adds >100MB to a fresh install
5. **Platform:** Must install via `pip` on Linux, macOS, and Windows

### Core Dependencies

| Package | Min Version | Purpose |
|---------|------------|---------|
| openai | ≥1.55 | OpenAI API client — native streaming, token usage, structured output |
| anthropic | ≥0.39 | Anthropic API client — Claude model access |
| litellm | ≥1.90 | Multi-provider proxy — fallback routing, cost tracking |
| instructor | ≥1.15 | Pydantic-guided structured output — typed LLM responses |
| tenacity | ≥8.0 | Retry decorators — exponential backoff with jitter |
| tiktoken | ≥0.7 | Fast BPE tokenizer — token counting for OpenAI models |
| python-dotenv | ≥1.0 | .env file loading — API key management |
| pydantic | ≥2.0 | Data validation — used by instructor, also for config models |
| portalocker | ≥2.8 | Cross-platform advisory file locking — concurrency control |
