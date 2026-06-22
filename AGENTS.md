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
   workflows            8 tools via stdio    Louvain communities
                                             graph insights
```

The wiki directory is the shared state. Every component reads/writes the same markdown files. No database. No API lock-in. Just files.

## Package Map

| Dir | Language | What it does | When to touch it |
|-----|----------|-------------|-----------------|
| `skill/` | Python + MD | Agent skill: SKILL.md + 12 scripts + 11 references | Agent operations, scripts, docs |
| `mcp-server/` | TypeScript | MCP server: 8 tools via stdio | Programmatic wiki access |
| `graph-engine/` | TypeScript | Knowledge graph: build, relevance, Louvain, insights | Graph analysis, community detection |
| `templates/` | MD + JSON | 19 domain templates for scaffold.py | Adding/modifying project templates |
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
| `mcp-server/src/index.ts` | MCP server entry. 8 tool handlers. Built with @modelcontextprotocol/sdk. |
| `graph-engine/src/index.ts` | Graph CLI. `--action build|insights|search|relevance`. |
| `graph-engine/src/relevance.ts` | 4-signal relevance model — ported from nashsu/llm_wiki. |
| `graph-engine/src/louvain.ts` | Louvain community detection — uses graphology library. |
| `templates/_shared/base-schema.md` | Base page types, frontmatter, naming conventions. All templates extend this. |

## Conventions

### Python scripts
- All use `argparse` (except older scripts being migrated)
- Pure stdlib — no external Python dependencies
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
- **The patch tool may fail on this repo** — use `sed` or `python3` for inline edits when the patch tool gives escape-drift errors.
- **MCP server needs `__dirname` resolution** — don't use `process.cwd()` for resolving script paths. Use `path.resolve(__dirname, ...)`.
- **Graph engine CLI expects `--wiki` path** — it auto-detects `wiki/` subdirectory. Pass the project root (parent of wiki/) or the wiki/ directory directly.
- **scaffold.py refuses to overwrite** — use `--force` flag. Without it, existing wikis are protected.
- **Two-step ingest may be slow** — Stage 1 analysis is cached by SHA256. Use `--force` to skip cache.
- **discover.py is the single source of truth for paths** — all tools call it at startup. If you rename directories, run `python3 skill/scripts/discover.py <wiki> --show` to verify detection.
- **Flat wikis (no `wiki/` subdirectory) are supported** — discover.py auto-detects pages at root. Confidence is lower (0.14) but all tools work.
- **Custom directory names are supported** — discover.py checks content/, pages/, notes/ for content; sources/, input/ for raw; logs/, journal/ for logs.**
- **All tools import discover.py via sys.path.insert** — when adding new scripts, add `from discover import discover_layout` and call it at startup.

## Hermes Skill Installation

The `skill/` directory is symlinked as a Hermes skill:

```bash
ln -sf /path/to/llm-wiki-monorepo/skill ~/.hermes/skills/research/llm-wiki
```

The EOW cron job (`9629c8c17a7a`) loads this skill automatically. Changes to `skill/SKILL.md` or `skill/scripts/` propagate immediately — no restart needed.

## External Dependencies

- **graphology** + **graphology-communities-louvain** — graph-engine only. Pure JS, no native deps.
- **@modelcontextprotocol/sdk** — MCP server only. Pure JS.
- **Readability.js** + **Turndown.js** — Browser extension only. Already vendored.
- No Python dependencies beyond stdlib.
- No Rust dependencies. (`rust-backend/` removed — coming soon.)
