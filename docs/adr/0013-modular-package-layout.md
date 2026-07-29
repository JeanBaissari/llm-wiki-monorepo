# ADR 0013: Modular Package Layout by Domain

- **Status:** accepted
- **Date:** 2026-07-29
- **Branches:** deployed on `v0.3.0/modularization`
- **Deciders:** JeanBaissari (@JeanBaissari)

## Context

`src/llm_wiki/` held 28 flat Python modules with no organizational hierarchy. Related concerns lived side-by-side with unrelated ones — `louvain.py` sat next to `claims.py` next to `deep_research.py`. Each 300-700 line module mixed CLI parsing, business logic, storage I/O, and output formatting into a single file. The TypeScript MCP server had a single `index.ts` (1,287 lines) with 14 tool handlers defined inline. Documentation was split between root-level `.md` files and `skill/references/` with no taxonomy.

This made it difficult to:
- Determine where new code should live
- Reason about import dependencies
- Test individual concerns in isolation
- Navigate the codebase by capability

## Decision

Reorganize the Python package and MCP server around **domain/category/function** — a three-level hierarchy where every module answers: what domain owns this, what category within that domain, and what specific function.

### Python package layout

```text
src/llm_wiki/
  core/           # infrastructure primitives — no domain imports
  quality/        # wiki quality: claims, lint, audit
  ingest/         # source ingestion pipeline
  providers/      # LLM provider adapters (openai, anthropic, opencode)
  graph/          # knowledge graph: louvain, insights, suggestions
  search/         # FTS5 search index
  ops/            # operations: health, serve, benchmark, migration
  wiki/           # wiki lifecycle: scaffold, backup
  research/       # deep research pipeline
```

### MCP server layout

```text
mcp-server/src/
  main.ts         # CLI entry (thin)
  registry.ts     # all 14 tool definitions + dispatch map
  tools/          # one file per tool handler
  adapters/       # sidecar bridge, FTS5, graph-engine
  projects/       # project scanning and discovery
  security/       # path-safety (allowlists, traversal checks)
```

### Root documentation layout (target)

```text
docs/
  getting-started/
  reference/       # CLI, templates, schema, MCP tools
  architecture/    # overview + ADRs
  agent-guides/
  release/
```

### Rationale

| Decision | Why |
|----------|-----|
| `core/` for infrastructure | These are shared primitives: frontmatter parser, hashing, atomic writes, locking, logging, wikilinks, layout discovery. Every domain depends on them. They must NOT depend on any domain package to avoid circular imports and allow independent testing. |
| `quality/` for claims + lint + audit | All three are quality-checking subsystems operating on wiki content. Grouping them together makes it obvious that new quality tools should live here. |
| `ingest/` separate from `providers/` | Ingest is the pipeline (chunk, analyze, generate, write). Providers are LLM adapters. They change for different reasons — a new provider shouldn't touch the pipeline, and a pipeline change shouldn't touch providers. |
| `graph/` not in core | Graph algorithms (louvain, insights, suggestions) are optional features that depend on optional Python packages (networkx). They don't belong in mandatory infrastructure. |
| `ops/` for non-wiki operations | Health checks, serve, benchmark, migration — these are operational concerns about the tool itself, not about wiki content. |
| `wiki/` for lifecycle | Scaffold and backup manage the wiki's existence. They're distinct from quality (which checks content) and ops (which checks the tool). |
| Tool handlers split into `tools/` | Each MCP tool handler is independently testable, independently importable, and has a clear single responsibility. Adding a new tool means adding one file + one registry entry — not touching 1,287 lines of index.ts. |
| `suggest_links` → `graph/suggest.py` | Link suggestions are graph-based operations. They build entity registries from wikilink graphs. |
| `link_suggest.py` → renamed from `link_suggest` to `suggest` within graph/ | Module name should match directory context. External CLI keeps `link-suggest` as command name. |

### Tradeoffs considered

| Alternative | Why rejected |
|-------------|-------------|
| Keep everything flat | No discovery boundary. New contributors can't intuit where code lives. |
| `core/` as the only subpackage, rest flat | Overloads core. Everything becomes "infrastructure" — no clear domain separation. |
| `services/` namespace (service-oriented) | Python community prefers function modules over Java-style service classes. Current code is function-based, not class-based. |
| `apps/` + `packages/` top-level workspaces | Too much breakage for this iteration. Internal modularization first; workspace relocation deferred to a follow-up. |
| Keep old module files as `*_wrapper.py` facades | User explicitly requested ruthless moves. CLI entry points (`pyproject.toml` console_scripts, `cli.py` COMMANDS dict) were updated directly to new paths. |
| Move `schema_validator.py` to `contracts/` | Deferred. Schema validation is used by core infrastructure (`audit_writer`) but conceptually belongs to contracts. Will be resolved in a follow-up. |

### Migration rules applied

1. **CLI commands preserve names** — `llm-wiki lint`, `llm-wiki ingest`, etc. unchanged.
2. **Import paths updated ruthlessly** — every `from llm_wiki.X import Y` updated to `from llm_wiki.domain.category import Y`.
3. **Function signatures unchanged** — no behavior modified during the move.
4. **Skills scripts remain thin wrappers** — `skill/scripts/lint_wiki.py` now imports `from llm_wiki.quality.lint import main`.
5. **MCP tool schemas byte-identical** — 14 tool names, inputSchemas, and response formats preserved.
6. **Constraint-based verification** — added contract tests (`test_cli_snapshots.py`, `test_frontmatter_golden.py`, `test_core_boundaries.py`) before moving a single file, then ran them after each batch.

## Consequences

**Easier:**
- Adding a new command means: create `domain/category/new_module.py` → add entry in `cli.py` → create thin wrapper in `skill/scripts/`.
- Tool isolation: a bug in `ops/benchmark.py` can't break `quality/lint/service.py`.
- Dependency clarity: `grep "from llm_wiki.core" src/llm_wiki/quality/` shows exactly what quality depends on.

**Harder:**
- Cross-cutting changes may touch multiple packages (e.g., adding a new core primitive requires updating imports in 4-6 domains).
- Import paths are longer. `from llm_wiki.quality.claims.models import Claim` vs old `from llm_wiki.claims import Claim`.
- CI paths need explicit verification for each domain (addressed by `test_core_boundaries.py`).

**Remaining Gaps (post-v0.3):**
- `contracts/` package for `schema_validator.py` and version management
- `mcp-server/src/adapters/graph-engine.ts` has a fragile `resolveGraphEngine()` fallback path
- `shared-types/` TypeScript package for graph node/edge contracts duplicating across packages
- Root documentation taxonomy (docs/getting-started/, docs/reference/, docs/architecture/)
- `release-manifest.json` updated to reflect new console_scripts paths
