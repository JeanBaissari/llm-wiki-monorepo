# v0.3.0 Modularization — Acceptance Criteria

## 0. Contract Freeze (Batch 0)

| ID | Criterion | Verified |
|----|-----------|----------|
| AC-00.1 | All 15 CLI commands produce help output (`--help` exits 0) | YES |
| AC-00.2 | CLI aliases resolve to correct targets | YES |
| AC-00.3 | `llm-wiki --version` outputs `0.2.1` | YES |
| AC-00.4 | Frontmatter parser golden tests pass for canonical inputs | YES |
| AC-00.5 | Core module import boundary test documents expected constraints | YES |
| AC-00.6 | `release-manifest.json` lists 15 unified CLI commands | YES |
| AC-00.7 | `test_drift.py` references no deleted files | YES |

## 1. Core Extraction (Batch 1)

| ID | Criterion | Verified |
|----|-----------|----------|
| AC-01.1 | `src/llm_wiki/core/` directory exists with __init__.py | YES |
| AC-01.2 | `core/frontmatter.py`, `core/hashing.py`, `core/atomic.py`, `core/locking.py`, `core/logging.py`, `core/layout.py`, `core/wikilinks.py` exist | YES |
| AC-01.3 | All old flat modules deleted (frontmatter.py, content_hash.py, atomic_write.py, lock_wiki.py, wiki_logging.py, discover.py) | YES |
| AC-01.4 | Core modules import ONLY from stdlib and each other — no domain/CLI imports | YES |
| AC-01.5 | All 203 tests pass after core extraction | YES |
| AC-01.6 | CLI discover command dispatches from `llm_wiki.core.layout` | YES |

## 2. Quality Packages (Batch 2)

| ID | Criterion | Verified |
|----|-----------|----------|
| AC-02.1 | `src/llm_wiki/quality/claims/` with models.py, storage.py, cli.py | YES |
| AC-02.2 | `src/llm_wiki/quality/lint/` with service.py, cli.py | YES |
| AC-02.3 | `src/llm_wiki/quality/audit/` with writer.py, review.py | YES |
| AC-02.4 | Old files deleted: claims.py, lint_wiki.py, audit_writer.py, audit_review.py | YES |
| AC-02.5 | 165 contract+claims+lint+schema tests pass | YES |
| AC-02.6 | `llm-wiki lint --help`, `llm-wiki audit --help`, `llm-wiki claims health --help` produce valid output | YES |

## 3. Ingest + Providers (Batch 3)

| ID | Criterion | Verified |
|----|-----------|----------|
| AC-03.1 | `src/llm_wiki/ingest/` with pipeline.py, blocks.py, writer.py, cache.py | YES |
| AC-03.2 | `src/llm_wiki/providers/registry.py` contains `call_llm()` and `detect_default_provider()` | YES |
| AC-03.3 | Old `ingest.py` and `llm.py` deleted | YES |
| AC-03.4 | `llm-wiki ingest --help` produces valid output | YES |
| AC-03.5 | `from llm_wiki.providers.registry import call_llm` works | YES |

## 4. Graph + Search + Ops + Wiki + Research (Batch 4)

| ID | Criterion | Verified |
|----|-----------|----------|
| AC-04.1 | `graph/` with louvain.py, insights.py, suggest.py | YES |
| AC-04.2 | `search/index.py` from old `index_wiki.py` | YES |
| AC-04.3 | `ops/` with health.py, serve.py, benchmark.py, migrate.py | YES |
| AC-04.4 | `wiki/` with scaffold.py, backup.py | YES |
| AC-04.5 | `research/deep_research.py` from old `deep_research.py` | YES |
| AC-04.6 | All 11 old flat modules deleted | YES |
| AC-04.7 | All skill/scripts wrappers updated to new import paths | YES |
| AC-04.8 | CLI commands for insights, link-suggest, index, health, serve, scaffold, backup, deep-research produce valid help | YES |

## 5. MCP Server (Batch 5)

| ID | Criterion | Verified |
|----|-----------|----------|
| AC-05.1 | `mcp-server/src/tools/` with 11 handler files | YES |
| AC-05.2 | `mcp-server/src/adapters/` with sidecar.ts, fts5.ts, graph-engine.ts | YES |
| AC-05.3 | `mcp-server/src/registry.ts` with all 14 TOOL_DEFINITIONS | YES |
| AC-05.4 | `mcp-server/src/main.ts` replaces old `index.ts` | YES |
| AC-05.5 | `package.json` entry point updated to `dist/main.js` | YES |
| AC-05.6 | TypeScript typecheck passes (`npx tsc --noEmit`) | YES |
| AC-05.7 | Build succeeds (`npm run build`) | YES |
| AC-05.8 | MCP test E2E smoke test passes (tools/list) | YES |
| AC-05.9 | All 14 tool names preserved byte-for-byte | YES |

## 6. No Regressions

| ID | Criterion | Verified |
|----|-----------|----------| 
| AC-06.1 | Test pass count on branch ≥ test pass count on main | YES (453 vs 445) |
| AC-06.2 | Test fail count on branch ≤ test fail count on main | YES (25 vs 33) |
| AC-06.3 | All new test failures are pre-existing (exist on main) | YES |
| AC-06.4 | No new import errors in any module | YES |
| AC-06.5 | Sidecar JSON-RPC handlers produce valid responses | YES |
| AC-06.6 | CI workflows reference correct entry points | YES |
| AC-06.7 | `release-manifest.json` paths match `pyproject.toml` console_scripts | YES |
| AC-06.8 | `docs_truth_check.py` exits 0 with no drift | TBD |

## 7. Documentation

| ID | Criterion | Verified |
|----|-----------|----------|
| AC-07.1 | ADR 0013 documents all tradeoffs and decisions | YES |
| AC-07.2 | Each package has an __init__.py documenting its purpose (via docstring) | PARTIAL |
| AC-07.3 | Acceptance criteria are verifiable and executable | YES |
| AC-07.4 | Remaining gaps documented in ADR 0013 | YES |
