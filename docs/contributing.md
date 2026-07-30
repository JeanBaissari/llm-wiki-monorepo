# Contributing to LLM Wiki

> Thanks for wanting to help. This guide tells you how.

## Release Blocker: GPL Provenance Review

> **🚨 BLOCKER — Public release is blocked until resolved.**

This project includes code ported from [nashsu/llm_wiki](https://github.com/nashsu/llm_wiki) which is licensed under **GPL-3.0**. Specifically:
- `graph-engine/src/relevance.ts` — 4-signal relevance model (comments state "Ported from nashsu/llm_wiki")
- `graph-engine/src/insights.ts` — Surprising connections and knowledge gap detection (comments state "Port of nashsu's graph-insights.ts")

These files are classified as **P — Ported code** in `docs/legal/provenance.md` and their disposition is `clean_room_replace`. **Before any public release**, these components must be:
1. Replaced with clean-room implementations based only on public algorithm descriptions, OR
2. Isolated with explicit GPL-3.0 licensing and packaging boundaries, OR
3. Removed or deferred from the release.

The provenance scan (`python3 skill/scripts/provenance_scan.py`) must pass with zero unresolved items before any package publication or release tagging.

See [docs/legal/provenance.md](./docs/legal/provenance.md) for the full provenance ledger.

## Project Structure

```
src/llm_wiki/         ← Python package — CLI, LLM providers, concurrency, search
skill/scripts/        ← Python scripts — scaffold, ingest, lint, insights, backup
skill/SKILL.md        ← Agent skill definition — loaded by Hermes/Claude/Codex
templates/            ← 20 domain templates (PURPOSE.md + SCHEMA.md + extra-dirs.json)
tests/                ← pytest suite — 16 test files + conftest.py fixtures
mcp-server/           ← TypeScript — MCP server (stdio, 10 tools)
graph-engine/         ← TypeScript — knowledge graph (relevance, Louvain, insights)
web-viewer/           ← TypeScript — local preview server
extension/            ← JavaScript — Chrome web clipper
```

## How to Add a Python Script

**For scripts that live in `skill/scripts/`** (Hermes skill integration):

1. Create `skill/scripts/<name>.py` with `#!/usr/bin/env python3` shebang
2. Use `argparse` for CLI — follow the pattern in existing scripts
3. Import `discover` for wiki layout detection at startup:
   ```python
   from discover import discover_layout
   layout = discover_layout(wiki_root)
   ```
4. Exit codes: `0` = success/clean, `1` = issues found, `2` = usage error
5. Print structured output to stdout, errors and warnings to stderr
6. Add to `docs/reference/file-map.md` scripts table
7. Add to `docs/reference/cli.md` with examples
8. If it's a new operation, add it to `skill/SKILL.md`

**For scripts that live in `src/llm_wiki/`** (Python package):

1. Create `src/llm_wiki/<name>.py`
2. Use `argparse` with a `main()` entry point
3. Add a console script entry to `pyproject.toml` under `[project.scripts]`:
   ```toml
   llm-wiki-<command> = "llm_wiki.<name>:main"
   ```
4. Import from existing modules rather than copying logic — `discover.py`, `atomic_write.py`, and `wiki_logging.py` are shared foundations

**Quality check before opening a PR:**
```bash
python3 -c "import py_compile; py_compile.compile('skill/scripts/<name>.py', doraise=True)"
```

## How to Add a Template

1. Copy an existing template:
   ```bash
   cp -r templates/codebase templates/<name>
   ```
2. Edit three files inside:
   - `PURPOSE.md` — why this wiki type exists, what it's for
   - `SCHEMA.md` — page types, conventions, frontmatter, cross-referencing rules
   - `extra-dirs.json` — JSON array of extra `wiki/` subdirectories
3. Add the template to `README.md` under the "Templates" section
4. Add it to `docs/reference/file-map.md` template table
5. Test that scaffold discovers it:
   ```bash
   python3 skill/scripts/scaffold.py --list-templates | grep <name>
   ```
6. Scaffold a test wiki to verify the output:
   ```bash
   python3 skill/scripts/scaffold.py /tmp/test-<name> "Test" --template <name> --force
   ```

## How to Add a Test

Tests live in `tests/` and use pytest. Every test file maps to a module:

| Test file | Covers |
|-----------|--------|
| `test_scaffold.py` | Wiki creation, template discovery |
| `test_discover.py` | Layout detection, path resolution |
| `test_ingest.py` | Two-step ingest, file generation, review blocks |
| `test_lint.py` | 15-pass lint checks |
| `test_index.py` | FTS5 search indexing |
| `test_concurrency.py` | WikiLock, atomic writes, conflict detection |
| `test_link_suggest.py` | Entity extraction, link suggestions |
| `test_louvain.py` | Louvain community detection |
| `test_integration.py` | End-to-end pipeline |
| `test_opencode.py` | OpenCode provider integration |

### Adding a new test

1. Create `tests/test_<name>.py`
2. Use fixtures from `conftest.py` where possible:
   - `tmp_wiki` — fresh scaffolded wiki in a temp directory
   - `populated_wiki` / `minimal_wiki` / `empty_wiki` — pre-built fixture wikis
   - `mock_llm_success` / `mock_llm_failure` — controlled LLM responses
3. If you need new fixture data, add it to `tests/fixtures/wikis/`
4. Run the new test in isolation first:
   ```bash
   python3 -m pytest tests/test_<name>.py -v
   ```

### Test conventions

- Use `tmp_path` or fixture wikis — never touch real files
- Mock external calls (LLM APIs, network) — tests must run offline
- Assert on file content, not stdout strings
- Keep test data small — fixtures are git-tracked

## How to Run the Test Suite

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all Python tests
python3 -m pytest tests/ -v

# Run a specific test file
python3 -m pytest tests/test_lint.py -v

# Run with coverage
python3 -m pytest tests/ -v --cov=src/llm_wiki --cov=skill/scripts

# TypeScript type checks
cd graph-engine && npx tsc --noEmit
cd mcp-server && npx tsc --noEmit

# Python syntax check (all scripts)
for f in skill/scripts/*.py; do
  python3 -c "import py_compile; py_compile.compile('$f', doraise=True)" && echo "OK $f"
done
```

## Code Style Guide

Follow existing patterns. When in doubt, open a nearby file and match it.

### Python (src/llm_wiki/ and skill/scripts/)

- **argparse** for CLI — no click, no typer
- **Type hints** on function signatures — use `Path`, `list[str]`, `dict[str, Any]`
- **Docstrings** on public functions — one-line summary, then details
- **Imports** — stdlib first, then third-party, then project:
  ```python
  import os
  import sys
  from pathlib import Path

  from openai import OpenAI

  from discover import discover_layout
  ```
- **Error handling** — use `sys.exit()` with exit codes, not bare exceptions
- **Output** — structured to stdout (print), errors to stderr (`sys.stderr.write()`)
- **No f-strings in logging/debug output** — older Python 3.10 compatibility

### TypeScript (mcp-server/, graph-engine/, web-viewer/)

- ES2022 modules, strict mode
- Build output goes to `dist/` (gitignored)
- `npm install` from the package directory, not repo root
- Path resolution: use `path.resolve(__dirname, ...)` — not `process.cwd()`

### Markdown (wiki files, templates, docs)

- Every wiki page: YAML frontmatter with `title`, `type`, `created`, `updated`, `sources`, `tags`
- Wikilinks: `[[Page Name]]` — case-sensitive, exact title match
- Diagrams: mermaid only. No ASCII art.
- Formulas: KaTeX only. `$inline$` or `$$block$$`

## PR Process

1. **Fork** the repo
2. **Create a branch** from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```
3. **Make your changes.** Keep commits focused — one concern per commit.
4. **Run the test suite** locally (see above). All tests must pass.
5. **Push and open a PR** against `main`
6. **Review:** at least one maintainer reviews. CI must pass. Address feedback.
7. **Merge:** squash-merge preferred. Branch is deleted after merge.

PRs that change behavior should include or update tests. PRs that add scripts should update documentation (docs/reference/file-map.md, docs/reference/cli.md).

## Commit Message Format

This project uses [Conventional Commits](https://www.conventionalcommits.org/).

```
<type>: <short description>

<optional body>
```

**Types:**

| Prefix | Use for |
|--------|---------|
| `feat:` | New feature or script |
| `fix:` | Bug fix |
| `docs:` | Documentation changes (README, AGENTS.md, skill refs) |
| `chore:` | Build, CI, install scripts, dependency bumps |
| `refactor:` | Code changes that don't fix bugs or add features |
| `test:` | Adding or updating tests |
| `perf:` | Performance improvements |

**Examples:**
```
feat: Add template validation pass to lint_wiki.py
fix: Handle empty frontmatter in ingest FILE block parsing
docs: Add agent-native provider section to QUICKGUIDE
chore: Update pytest dependency to >=8.0
```

When a change touches a specific package, prefix the scope:
```
fix(mcp-server): Resolve __dirname in single-wiki mode
feat(graph-engine): Add --action export-graph
test(ingest): Add malformed FILE block handling
```

## Getting Help

- **AGENTS.md** — architecture, conventions, build commands, pitfalls
- **docs/reference/cli.md** — every command with real examples
- **docs/reference/file-map.md** — complete file tree with descriptions
- **Issues** — [GitHub Issues](https://github.com/JeanBaissari/llm-wiki-monorepo/issues)

Open an issue before starting on something large. It saves everyone time.
