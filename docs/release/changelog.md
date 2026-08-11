# Changelog

## [0.6.0] — 2026-08-11

### Epistemic & Surface

The v0.6.0 minor closes the USAGE.md §7/§8 UX + epistemic backlog. Everything is
additive and opt-in — defaults stay byte-identical, the base install stays
lexical-only, `graph-data.json` shape is unchanged, and every new capability is
eval-gated. 25 CLI commands / 15 MCP tools.

- **One-command setup** (LWM_035): `llm-wiki setup <root> [--title]` scaffolds or
  validates a wiki and registers the MCP server with the detected client(s) —
  claude (`claude mcp add` or `.mcp.json`), codex (`~/.codex/config.toml`),
  opencode (`opencode.json`), hermes (skill symlink). Idempotent, reversible
  (`--uninstall`), `--dry-run` writes nothing, never clobbers unrelated config
  keys, never writes secrets, and finishes with a health + `tools/list` smoke
  test. The Hermes skill symlink from `install.sh` is unified here.
- **Demo wiki** (LWM_036): `llm-wiki demo <dest>` materializes a committed,
  deterministic, lint-clean "Redis Internals" playground (8 pages) from the
  installed package or repo, regenerates the FTS index, and prints next steps.
  Ships in the wheel (package-data); base install never requires node.
- **Ask this wiki** (LWM_033): `llm-wiki ask <root> "<question>"` — grounded QA
  over pages + community-summary nodes (located by `type:` frontmatter, never
  directory). Hybrid retrieval (LWM_032) + summary-aware rerank, exactly one
  structured LLM call via the agent-native `$0.00` provider default, `--no-llm`
  deterministic offline passages mode, and a faithfulness contract (answer
  entities ⊆ cited pages). Committed ask gold set + citation precision@k gate
  (fail-on-drop) following the standing curation procedure. MCP: `llm_wiki_ask`.
- **Contradictions + evidence confidence** (LWM_034): `llm-wiki contradictions
  <root> detect|list|apply|unapply` — typed claim extraction (entity-grounded),
  a suggest-only contradiction detector (unit-normalized numeric values, polarity,
  exclusive categories), and a deterministic evidence-grounded confidence scorer
  (source count/recency/cross-page agreement/citation support → high/medium/low +
  `evidence_score`), author-overridable via a `confidence_source: evidence|author`
  marker. `detect` writes nothing; `apply`/`unapply` are reversible. Reuses the
  `.llm-wiki/claims/` sidecar (ClaimsManager) — no parallel storage. Contradiction
  + confidence gold sets with fail-on-drop gates.
- **Recommended-extras profile** (LWM_037): `pip install -e ".[recommended]"` =
  `semantic` + `leiden` + `entity-resolution` (deliberately not `ner`/`eval`).
  GLiNER `[ner]` gains a torch-free local path — a documented ONNX model-cache
  convention (`~/.cache/llm-wiki/models/`, `LLM_WIKI_GLINER_MODEL` env) with a
  measured disk budget; base install never imports the stack.
- **Web-viewer derived-edge overlay + Sigma.js + exports** (LWM_038): the derived
  layer (`.index/derived-edges.json`) renders as an off-by-default toggleable
  dashed overlay (byte-identical when off), a Sigma.js WebGL view for large
  graphs, and JSON Canvas 1.0 + JSON-LD exports (layer-labeled, schema-valid).
  Web-viewer-only diff — no backend graph output change.
- **Search gold-set standing procedure** (LWM_039 §A): `scripts/curate_gold_set.py`
  (split hygiene + manifest freeze + byte-stable baseline regen) + a
  `gate_search_goldset_fresh` release-certify gate + a committed `growth_meta.json`
  grow-or-justify record. The ask gold set follows the same loop.
- **Cross-platform hardening** (LWM_039 §X): a 22-test `test_cross_platform_edge.py`
  suite + CI lane covering the recent macOS/Windows fixes, which also exposed and
  fixed real bugs: CRLF frontmatter parsing (`core/frontmatter.py`,
  `search/index.py`), Windows backslash wikilink keys (`core/wikilinks.py`), and
  strict-decode lint reads (`quality/lint/service.py`).
- **Serve friction + boundary docs** (LWM_039 §B–D): `llm-wiki serve` prints the
  exact build command + `--build` flag when `mcp-server/dist` is missing;
  `docs/operations/security-and-boundaries.md` states the files-first trust
  boundary; README gains a "Five ways to run this" landing section.

## [0.5.0] — 2026-08-07

### Graph Precision

The precision-focused minor after the Semantic Core. Everything is additive and
either opt-in or behind an optional extra — the base install stays lexical-only
and byte-identical, and the **one** elected default change (hybrid search) is
gated on an eval proving no keyword-recall regression. `graph-data.json` shape is
unchanged.

- **Entity resolution** (LWM_025): `llm-wiki entities resolve/list/unmerge` — a
  lightweight normalize → block → two-signal-merge pipeline that collapses
  variant surface forms ("GPT-4"/"GPT 4"/"gpt-4") to one canonical id. A merge
  needs two independent signals (string **and** embedding) to agree; embedding
  similarity alone can never merge. Reversible by construction: an append-only,
  git-diffable `.llm-wiki/entities/aliases.jsonl` is the source of truth, with a
  regenerable `.index/wiki.db` cache. `link-suggest --resolve-entities` routes
  alias mentions to the canonical page (`[[Canonical|surface]]`, surface
  preserved), unblocking the v0.4.0 suggest-only semantic `--apply`.
- **GLiNER extractor** (LWM_026): a pluggable `EntityExtractor` interface;
  `RegexExtractor` default is byte-identical, `GLiNERExtractor` is an optional
  `[ner]` backend (Apache-2.0, CPU/ONNX/INT8) with a deferred model load and an
  always-safe import/fallback.
- **Leiden community detection** (LWM_027): `graph/leiden.py` — an optional
  `[leiden]` sidecar engine (graspologic, MIT — not GPL leidenalg) with the
  identical `detect_communities` contract and an internal-connectivity guarantee.
  Louvain stays the default until the NMI/modularity gate proves Leiden ≥ Louvain.
- **Typed/directed/bitemporal edges** (LWM_028): `GraphEdge` gains optional
  `relType`/`directed`/`validFrom`/`validTo`/`observedAt`. The `build.ts` dedup
  key is guarded so the undirected default stays byte-identical; directed opt-in
  makes `A→B ≠ B→A`. File-format change done once.
- **Derived edges** (LWM_029): `llm-wiki derive-edges` builds a **quarantined**
  sibling layer (`.index/derived-edges.json`) of `similar_to` (cosine-KNN over
  the v0.4.0 vectors) + `co_occurs_with` (shared sources/entities) edges,
  excluded by default from every analytics consumer and `graph-data.json`.
  Opt-in inclusion is **fail-closed** on a modularity gate vs the wikilink
  baseline.
- **Community summaries** (LWM_030): opt-in `llm-wiki summarize-communities` —
  one structured LLM call per community (agent-native `$0.00` default) written as
  first-class `type: community-summary` pages with `[[member]]` links.
  Cost-bounded (`--dry-run`, SHA-keyed idempotency, `--max-communities`) and
  faithfulness-filtered (`key_entities ⊆ member entities`).
- **Tuning config** (LWM_031): a canonical `TuningConfig` (`core/config.py`)
  owning ~17 precision constants; defaults equal today's literals byte-for-byte;
  resolution is `CLI > env > file > code-default` and fails closed on unknown
  keys / out-of-range values. `search --set section.key=value`.
- **Hybrid search is now the default** (LWM_032): `llm-wiki search` and the MCP
  `llm_wiki_search` tool default to hybrid, gated by a committed search gold set
  + fail-closed eval gate (recall parity + precision no-regress on a held-out
  GATE split). `--keyword` / `mode="keyword"` escape hatch retained; both degrade
  to keyword byte-identically without the `[semantic]` extra.

New optional extras: `[entity-resolution]` (splink), `[ner]` (gliner,
onnxruntime), `[leiden]` (graspologic, networkx). Base install unchanged.

### QA Remediation (2026-08-07, pre-tag)

Post-build 6-reviewer QA + master-auditor pass (23 findings AD-1…AD-23)
remediated before the tag, per the spec-driven plan in
`~/.claude/plans/glowing-bouncing-swing.md`:

- **Evidence & gates now committed**: ER-F1 gate (`er_goldset.json` +
  `er_baseline.json`, F1 0.917 on the gate split, fail-on-drop),
  search-eval baseline + `split_manifest.json` SHA256 freeze +
  reproducibility test, Leiden NMI/modularity verification over all
  `fixtures/graphs/*.json`, derived-edge + community-summary gate metrics in
  `eval_baseline.json`, defaults-snapshot golden for the tuning config.
- **ADRs 0016–0028 authored** (index + decision register) — every `# See
  ADR-00xx` citation in code now resolves.
- **Correctness fixes**: GLiNER load/inference failures now fall back to the
  regex extractor; ambiguous/single-signal entity near-misses emit
  `entity-merge` audit review rows; the alias DB readers assert the
  `alias_meta` guard and auto-rebuild from the JSONL; semantic `--apply`
  routes aliases by normalized page title; the two-signal must-not-merge
  guarantee is now tested non-vacuously (same-block pair, `resolve.py`
  union path exercised).
- **Derived-edge gate completed**: NMI ≥ 1−tol AND modularity ≥ baseline
  (was modularity-only); `--include-derived` wired fail-closed into
  insights/summarize consumers; on-disk edge fields unified to camelCase.
- **Community summaries**: global reference built from real member entities
  (faithfulness leak closed), SHA-keyed filenames with orphan cleanup,
  `--levels` hierarchy (Leiden levels seam + deterministic agglomeration
  fallback), `summary_faithfulness` metric.
- **Leiden**: per-connected-component execution (no node loss), exposed
  `hierarchical_levels` for the summary hierarchy, `[leiden]` CI lane,
  networkx probed in availability check.
- **LWM_031 fully threaded**: all 22 constants + the 5×5 type-affinity
  matrix + insights signal scores are effective via `--set`/env/`tuning.toml`;
  `to_graph_engine_json()` is live; graph-engine consumes the same resolved
  tuning (TS parity test); new `llm-wiki tuning` command.
- **Release gate fixed**: `release_certify.py` gains a search-eval step and
  a pytest timeout large enough for the grown suite; the CI `certify` job's
  `needs: [ci]` (non-existent job) is fixed; the `semantic` CI job now
  installs `[semantic]` and re-certifies the search gate with the real
  embedder; MCP `handleSearch` hybrid-default path covered by tests.
- **Docs SoT**: `cli.md` (4 new commands + flags), `mcp-tools.md` 10→14
  tools (phantom tools removed), `templates/_shared/base-schema.md`
  (`community-summary` type), `file-map.md`, `README.md`, `tuning.md`,
  `docs/operations/`, `GOLD_SET.md`; all 8 v0.5.0 PRD Evidence Matrices
  flipped to `delivered` (6 rows deferred with reasons).

### Post-release hardening (2026-08-09, untagged main merge)

- **serve entry-point fix** — `llm-wiki serve` now resolves the MCP server
  entry point from `mcp-server/package.json` `main` (fallback `dist/main.js`)
  instead of the stale `dist/index.js`, which the `main.ts` build no longer
  emits — "MCP server not built" on clean checkouts is fixed (G-2).
- **ADR-0013 dedup** — the superseded `0013-acceptance-criteria.md` is deleted;
  its unique acceptance-checklist content is merged into
  `0013-modular-package-layout.md`; ADR index + decision register collapsed to a
  single `0013` row (G-3).
- **Session-transcript gitignore** — pattern generalized from `2026-08-07-*.txt`
  to `20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]-*.txt` so future dated exports are
  covered (G-5).
- **Deferred Evidence-Matrix rows closed** — the 2 deferred LWM_025 rows
  (frozen-format corpus + FTS5-untouched) and remaining deferred rows remain
  documented with reasons; no new deferrals (see H-3).
- **Splink backend backlogged** — the splink-backed blocking/comparison feeding
  the two-signal gate is planned for v0.6.0 per `PRD/v0.5.1/backlog.md`; the
  pure-Python fallback is the active shipped path (G-1).

## [0.4.0] — 2026-08-06

### Semantic Core

The first feature-expansion minor after the v0.3.x stabilization line. Adds a
**semantic layer** to a system that was previously lexical/structural only.
Everything is additive and behind the optional `[semantic]` extra — the base
install stays lexical-only and byte-identical to v0.3.4, and every existing
default (keyword search, `graph-data.json` shape, the 14 MCP tools, ingest
frontmatter) is unchanged.

- **Pluggable embeddings** (LWM_013/015): a dimension-agnostic `Embedder`
  interface with **model2vec / potion-retrieval-32M** (numpy-only, no torch) as
  the default; `is_semantic_available()` probe + graceful lexical fallback.
- **In-file vector store** (LWM_014/017/018): a `page_vectors` float32-blob table
  + optional `sqlite-vec` `vec0` table in the existing `.index/wiki.db`, with an
  `embed_meta` guard. KNN uses a pure-numpy fallback when the extension can't
  load (macOS/Windows-safe), and the `vec0` fast path is an exact prefilter +
  numpy rerank so both backends return identical top-k.
- **`llm-wiki embed`** (LWM_016): SHA256-fresh batch embedding into the store.
- **Hybrid search** (LWM_019/020): `llm-wiki search [--hybrid]` — Reciprocal Rank
  Fusion of FTS5/BM25 + vector KNN, opt-in, with a gibberish floor and
  keyword-only fallback. (Promotion to default deferred to v0.5.0 post-eval.)
- **Semantic link suggestion** (LWM_021): `llm-wiki link-suggest --semantic
  --page <stem>` — fuses embedding + Personalized PageRank + lexical signals;
  suggest-only, never auto-applying a link on static-embedding similarity alone.
- **Evaluation harness** (LWM_022): `llm-wiki eval` + a committed gold-set
  baseline (precision@5=0.75) with a disjoint tune/gate split, wired as a CI
  eval-regression gate.
- **Graph-engine consolidation** (LWM_024): deleted the divergent Python
  label-propagation path — `llm-wiki insights` now uses the canonical Louvain,
  matching the TypeScript engine; seeded the graph-engine rng so community IDs in
  `graph-data.json` are deterministic.
- **CI gates** (LWM_023): eval-regression gate, a cross-OS (ubuntu+macOS)
  `semantic` job exercising the native/numpy KNN paths, a base-install-purity
  gate, and benchmark governance (env-dependent latency benchmark marked `slow`).

### New CLI commands

- `llm-wiki search`, `llm-wiki embed`, `llm-wiki eval`.

### New optional extras

- `[semantic]` (model2vec, numpy, sqlite-vec) and `[eval]` (deepeval).

### Deferred to follow-ups

- MCP hybrid-search surface (optional `mode` param), Windows CI matrix, and a
  couple of snapshot corpora remain for a subsequent patch.

## [0.3.4] — 2026-07-31

### Fixture Lanes Certification (LWM_012)

- **Lane 5 — Audit entries** regenerated against current zod `AuditEntrySchema`. Wired into `audit-shared` vitest (6 tests pass). Added optional fields to schema (`target_kind`, `target_reason`, optional anchors).
- **Lane 8 — Deep research** fixture wiki created in `tests/fixtures/deep_research_sources/`. Expanded `test_deep_research_mock.py` from 2 smoke tests to 9 deterministic tests (no-URLs, with-URLs, invalid root, fixture structure).
- **Lane 4 — Web routes** first-ever `web-viewer` test infra: vitest + supertest with 6 route case tests (page, search, graph, audit, path traversal rejection).
- **Lanes 6+7 — Reclassified**: browser clipper and Obsidian plugin marked optional. ADR 0014 documents decision with manual verification commands.

### Version + Docs

- Version bumped 0.3.0 → 0.3.4 across pyproject.toml, `__init__.py`, package.json, release-manifest.json
- Frontmatter test xfail removed (key case preservation is correct behavior, not a bug)
- Fully documented changelog for all v0.3.x releases

## [0.3.3] — 2026-07-31

### GPL Provenance Resolution (LWM_002)

- `graph-engine/src/relevance.ts`: Added configurable `RelevanceOptions` (weights, typeAffinityMatrix). `buildSourceIndex()` for performance. `GraphNode.sources` type safety. Degree-0 edge case guard. 16 unit tests.
- `graph-engine/src/insights.ts`: Added configurable `InsightsOptions` (8 thresholds). Extensible `SurpriseSignalFn[]` registry — 4 signal functions extracted. Single-pass edge iteration optimization. `structuralTypes` merge. 12 unit tests.
- All GPL provenance markers removed from source files. Documentation updated: `CONTRIBUTING.md` blocker resolved, `README.md` reflects substantial rewrite, `AGENTS.md` updated.
- Provenance scan: 50→38 markers, 21→17 GPL references (remaining are docs-only or false positives).

## [0.3.2] — 2026-07-30

### Infrastructure + Feature Completions

- **`llm-wiki ops list` CLI** — browse operation manifests (`.llm-wiki/operations/completed/`)
- **`llm-wiki claims redteam` report** — health scoring + action recommendations
- **Markdown log → operation ID linking** — daily log entries include `[op: <id>]`
- **Wheel smoke test in CI** — release workflow installs built wheel + verifies version
- **Cross-language schema CI** — Python + TS validators tested against shared fixtures
- **README tier column** — all packages classified (core/adapter/access/analysis/optional)

## [0.3.1] — 2026-07-30

### PRD Completion — 5 Batches

- **Batch A**: Component tier classification in AGENTS.md. Product identity propagated. schema_version in generated docs. Templates marked as generated.
- **Batch B**: Provenance scan in CI. Fixture freshness CI gate. `package-lock.json` regenerated. OperationContext mandatory. Operation manifest files (`.llm-wiki/operations/completed/`).
- **Batch C**: TypeScript `OperationContext` in `audit-shared/src/ops/context.ts`. TS schema validator loads JSON schemas. `graph-bridge` test infra.
- **Batch D**: Page confidence compilation from claims. Ingest `--claims` flag. Convenience methods (reinforce, challenge, weaken, supersede, resolve). Lazy index loading.
- **Batch E**: MCP transcript fixtures (`tools_list.json`). Deep-research mock tests. Docs contract tests. Fixtures regenerated.

## [0.3.0] — 2026-07-29

### Modular Package Layout (ADR 0013)

- **Python:** 28 flat modules reorganized into 10 domain packages: `core/`, `quality/{claims,lint,audit}/`, `ingest/`, `providers/`, `graph/`, `search/`, `ops/`, `wiki/`, `research/`, `contracts/`
- **TypeScript:** MCP server split from 1,287-line `index.ts` into 20 focused files under `tools/`, `adapters/`, `projects/`, `security/`
- **Shared types:** extracted canonical `GraphNode`/`GraphEdge` types into new `packages/shared-types/` workspace package
- **Core primitives:** centralized frontmatter parsing, wikilink extraction, hashing, atomic writes, locking, and logging into `core/`
- **All CLI commands unchanged** — `llm-wiki lint`, `llm-wiki ingest`, etc. work identically
- **All 14 MCP tool names and schemas preserved** byte-for-byte
- **+51 tests added** (490 total); 7 pre-existing failures eliminated; 472 pass

### Docs Taxonomy

- Root documentation reorganized into `docs/`: `architecture/`, `getting-started/`, `reference/`, `legal/`, `release/`
- `README.md` and `AGENTS.md` kept at root (PyPI packaging + agent tool convention)
- `CONTRIBUTING.md` → symlink to `docs/contributing.md`
- `LICENSE` file created (MIT)

### Remaining Gaps Closed

- OpenCode test imports fixed (2 failures → 0)
- graph-engine resolve path reordered
- MCP integration tests match sidecar response schema (9 failures → 0)
- Link suggest `inverted` parameter added
- Release manifest console_scripts updated to modular paths
- Doc drift: MCP tool counts, template counts, version manifest consistency

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
- docs/release/versioning.md — semantic versioning policy
