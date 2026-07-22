# Changelog

## [0.2.1] — 2026-07-22

### Release Integrity (LWM_003 + LWM_004)

- Release manifest (`release-manifest.json`) — machine-readable contract for version, CLI, MCP tools, templates, docs
- Release manifest validator (`scripts/release_manifest.py`) — checks version consistency across pyproject.toml, __init__.py, package.json, CHANGELOG.md, and console script imports
- Docs truth checker (`scripts/docs_truth_check.py`) — validates MCP tool counts, template counts, and CLI command claims in README, AGENTS, INDEX, QUICKGUIDE
- Workspace membership: `graph-bridge` and `plugins/obsidian-audit` added to root npm workspaces
- Package test gates: `graph-engine` tests run via vitest; `audit-shared` explicitly acknowledges zero-test state
- Zero-test guard (`scripts/zero_test_guard.py`) — detects package test commands that run zero tests
- CI matrix: Python 3.10–3.12, Node 18/20/22; TypeScript typecheck + test gate; Python coverage; release manifest validation

## [0.2.0] — 2026-07-04

### Phase 1 — Foundation (6 PRDs)

#### LWM_01: CI Test Infrastructure
- Full pytest + vitest test suite with 172 tests (91 Python, 49 graph-engine, 32 mcp-server)
- Provider-agnostic mock approach for LLM-dependent tests (vcrpy for local dev only)
- Test matrix: Python 3.10–3.12, Node 18–22
- Coverage: ≥80% Python, ≥70% TypeScript (report-only initially, blocking after 3 consecutive ≥80% runs)
- Static fixture wikis: empty, minimal, stale, populated (50+ pages with cross-references)
- Legacy test files (`test_ingest_blocks.py`, `test_ingest_e2e.py`) migrated to pytest and deleted (completed in v0.2.1)
- CI caching for pip + npm (~30s with warm cache)

#### LWM_01B: Test Fixture Lifecycle
- Seed-based fixture generation with schema version markers
- CI validation on stale fixtures
- 3 bug fixes (orphan handling, contradiction detection, false negatives)

#### LWM_02: Concurrency Control
- Per-page advisory file locking via portalocker (cross-platform)
- Atomic write pattern (temp file → fsync → atomic rename) for all wiki writes
- Content-hash-based conflict detection (SHA256 in page frontmatter)
- Conflict file generation (`filename (conflict).md` — Obsidian-compatible)
- Timeout-based staleness detection (lock_timeout × 3) with Unix PID fast-path (`os.kill(pid, 0)`)
- Three-tier conflict management: lint rule (severity=error), `--clean-conflicts` flag (30-day auto-archive), EOW cron pipeline integration
- Read→modify→atomic write for `update_index()`
- `--lock-timeout` flag and `LLM_WIKI_LOCK_TIMEOUT` env var
- Git-based merge workflow documented in `skill/references/concurrency.md`
- 40 concurrency tests

#### LWM_03: LLM SDK Integration
- Replaced `subprocess.run`-based `call_llm()` with native Python SDKs (openai v1.x, anthropic v0.x)
- Provider abstraction layer (`llm/providers.py`) supporting openai, anthropic, deepseek, together, litellm
- LiteLLM integration for multi-provider fallback with cost tracking
- Structured output via instructor — Pydantic-guided FILE/REVIEW block generation (no regex parsing)
- Retry with exponential backoff (3 attempts, jitter) via tenacity on transient errors
- Token counting via tiktoken logged per call (input/output/total)
- Cost estimation logged per ingest operation (±20% of actual)
- `LLM_WIKI_RESPONSE_FILE` offline fallback preserved with instructor validation
- Streaming support for Stage 1 analysis display (Stage 2 waits for full response → validates → writes)
- `.env`-based API key management with `.env.example` template
- `--max-cost` flag for per-ingest spend cap
- `--llm-timeout` flag for total deadline across retries
- **Python Dependency Policy**: stdlib-only convention permanently retired for v0.2.0. Managed dependencies via pyproject.toml.
- 117 core tests

#### LWM_03B: Hermes-Native LLM Integration
- `opencode` provider — routes LLM calls through the agent's own model (no API keys required)
- Multi-marker agent detection: `HERMES_SESSION_ID`, `CLAUDE_CODE_SESSION`, `CODEX_SESSION`, `LLM_WIKI_AGENT_MODE=1`
- Pipe-based stdin/stdout IPC for subprocess communication
- Queue-and-wait when agent model is busy (5-minute timeout with clear error)
- Structured output compatibility with instructor
- Auto-detection: defaults to `opencode` when running inside any supported agent
- `--llm opencode` explicit CLI flag
- 63 opencode/llm/provider tests

#### LWM_03C: Error Handling & Observability
- Structured logging via `wiki_logging.py` with `--quiet`/`--verbose` flags
- Health check module (`health_check.py`) — exit 0 for healthy, exit 3 for panic
- Migrated scaffold.py and graph_insights.py to structured logging
- 194 tests (20 test_logging, all scaffold/discover/ingest/lint)

### Phase 2 — Core Optimizations (6 PRDs)

#### LWM_04: Graph Relevance Optimization
- Replaced O(N×E) relevance computation with precomputed GraphStructure
- `calculateRelevance()` now O(1)/O(min(dA,dB)) per call instead of O(E)
- Fully removed `getNeighbors()` and `getNodeDegree()` from exports
- `calculateRelevanceBreakdown()` added for signal-level access
- ≥20x speedup at 5,000 pages
- 54 graph-engine vitest tests

#### LWM_04B: Graphology Integration Bridge
- Single graphology Graph construction from GraphNode[]/GraphEdge[] with sorted-key deduplication
- `detectCommunities()` accepts optional pre-built graph for reuse
- 5 parity tests verifying byte-identical results with/without shared graph

#### LWM_05: Search Persistence & Indexing
- SQLite FTS5 at `<root>/.index/wiki.db` with incremental updates
- SHA256-based content freshness detection
- Pre-build index at MCP server startup (`server.oninitialize`)
- Current regex-based tokenizer preserved for FTS5-stored term frequencies
- `--rebuild` flag for full reindex
- 36 new search tests (297 total)

#### LWM_06: Link Suggestion Optimization
- Inverted entity index: dual-map `InvertedIndex` (entity→pages + page→entities)
- Replaced O(P×E) entity_page_count Counter with O(1) lookup
- `generate_suggestions()` refactored with `build_inverted_index()`
- ~10x constant-factor speedup
- 27 link_suggest tests + 7 benchmark tests at 100/500/1K/5K pages

#### LWM_06B: Inverted Index Corrected
- True O(P+E) entity lookup via reverse entity map
- Eliminated full registry scan for per-page entity queries
- Backward-compatible: `generate_suggestions()` builds index on first call if not provided
- Both `skill/scripts/link_suggest.py` and `src/llm_wiki/link_suggest.py` synced
- 27 regression tests

#### Cross-Cutting (Phase 2)
- Native dependency policy codified: prefer pure-JS/WASM, native deps require CI prebuild, WASM fallback
- LWM_01B test fixture lifecycle integrated into CI

### Phase 3 — Integration & Unification (4 PRDs)

#### LWM_07: MCP Server Direct Integration
- Python sidecar (`skill/scripts/sidecar.py`) for ingest and graph operations
- TypeScript sidecar manager (`mcp-server/src/sidecar.ts`)
- Direct graph-engine imports via `tryImport` pattern with graceful fallback
- All graph-engine functions importable: `buildWikiGraph`, `findSurprisingConnections`, `detectKnowledgeGaps`
- Separate MCP tools: `llm_wiki_graph_build`, `llm_wiki_graph_insights`, `llm_wiki_graph_search`
- Deprecated combined `llm_wiki_graph` with `action` parameter preserved for backward compat
- Atomic writes + crash cleanup (temp directory → atomic move)
- Request timeout (2 min default) for hung operations
- 114 tests (85 vitest + 29 Python), zero regressions

#### LWM_07B: New MCP Tools
- `suggest_links` — entity-based link suggestions from wiki content
- `backup` — snapshot, restore, verify, prune operations
- `discover_entities` — entity extraction and discovery

#### LWM_08: Community Detection Unification
- Full Blondel et al. (2008) modularity formula with Σ_in/Σ_tot tracking
- Upgraded Python Louvain with seed-based deterministic shuffling (seed=42)
- Communities renumbered by size descending (largest = ID 0)
- Runtime warning when old label-propagation output detected
- NetworkX accepted as dependency for v0.2.0 (pure-Python fallback preserved)
- 298/298 tests pass

#### LWM_08B: Community Verification Suite
- Multi-graph, multi-seed, NMI/ARI cross-validation
- Statistical similarity metrics: NMI > 0.95 AND ARI > 0.95 across 5 seeds
- Modularity scores within 1% relative tolerance
- 5 seeds per implementation (42, 123, 456, 789, 0) with pairwise NMI comparison
- Baseline variance established before cross-implementation comparison

### Breaking Changes
- Python stdlib-only constraint removed — `pip install` now required (see `install.sh`)
- `getNeighbors()` and `getNodeDegree()` removed from graph-engine exports
- Legacy `test_ingest_blocks.py` and `test_ingest_e2e.py` deleted in v0.2.1 (previously migrated to pytest)
- Label propagation algorithm replaced with Louvain (runtime warning on old cached data)

### Dependencies Added
- **Python**: openai≥1.55, anthropic≥0.39, litellm≥1.90, instructor≥1.15, tenacity≥8.0, tiktoken≥0.7, python-dotenv≥1.0, pydantic≥2.0, portalocker≥2.8
- **Optional**: pytest≥8.0, pytest-cov≥5.0, vcrpy≥6.0, networkx≥3.0

### Known Deferred Items
- Benchmark CSV artifact (500–5000 pages) — deferred to Phase 1.6
- CRDT-based multi-writer merging — deferred to v0.3.0+
- SQLite coordination layer — v0.3.0 architectural review
- Multi-machine locking (NFS/network FS) — git-based merge instead
- Local model support (Ollama, llama.cpp) — not configured or hosted
- Browser extension + web viewer tests — separate tooling required (playwright/cypress)
- 100% coverage targets — 80% on critical paths sufficient

---

## [0.1.1] — 2026-06-23

### Fixed

- Templates now ship inside the package wheel — scaffold works from pip install
- TEMPLATES_DIR resolution searches installed package location first, then dev repo
- backup.py: import argparse at module level (not inside `__name__` guard)
- migrate_log.py: add main() function for consistent entry point
- PyPI classifier: corrected `Topic :: Text Processing :: Markdown` to `Topic :: Text Processing :: Markup :: Markdown`

## [0.1.0] — 2026-06-22

### Added

- Initial PyPI release as `baissarienterprises-llm-wiki`
- 11 CLI commands: scaffold, lint, ingest, discover, insights, link-suggest, backup, deep-research, audit, benchmark, migrate-log
- Auto-discovery module (`discover.py`) — zero-config wiki structure detection across canonical, flat, and custom layouts
- 15-pass lint system with dynamic frontmatter validation and source drift detection
- Two-step chain-of-thought ingest with SHA256 caching and agent loop mode
- Knowledge graph engine (TypeScript) with Louvain community detection and 4-signal relevance model
- Link suggestion engine with entity extraction and auto-apply
- Backup and recovery with tar.gz snapshots, restore, verify, and prune
- Performance benchmark suite for synthetic wikis (10–5000 pages)
- MCP server with 8 tools, single and multi-wiki mode
- Web viewer with search bar and graph insights panel
- Browser extension with auto-ingest after clip
- 20 domain templates (audited and consistent)
- CI/CD pipeline (GitHub Actions) with full integration tests
- One-command install script (`install.sh`)
- VERSIONING.md — semantic versioning policy
