# ADR 001: `discover.py` as Single Source of Truth for Wiki Structure

- **Status:** accepted
- **Date:** 2026-07-04
- **Context:** Every tool in the ecosystem — scaffold, lint, ingest, backup, link_suggest, graph_insights, deep_research — needs to locate the wiki's pages directory, raw sources, logs, audits, and frontmatter conventions. Earlier versions had each script hardcoding its own directory heuristics (`wiki/`, `raw/`, `log/`), causing subtle breakage when layouts diverged. A wiki at the root level (flat) versus one nested under `wiki/` would silently fail in different tools.
- **Decision:** All tools import `discover.discover_layout()` via `sys.path.insert` at startup. This single function scans the project root, tests ordered candidates for pages, sources, logs, audits, and outputs, and returns a `WikiLayout` dataclass with seven confidence signals. Tools never guess paths — they always call discover and trust its result.
- **Consequences:** Easier: adding a new tool means importing discover and getting instant path resolution. Removing: the import mechanism (`sys.path.insert`) is fragile when scripts are run outside the expected directory. The same logic is duplicated across `skill/scripts/discover.py` and `src/llm_wiki/discover.py` — they must be kept in sync, or one must become a thin wrapper.
