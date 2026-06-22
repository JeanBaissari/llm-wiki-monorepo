# Audit C: Structural Integrity — Complete Report

**Date:** 2026-06-22  
**Scope:** Template quality, content migration readiness, schema consistency, pipeline gaps, MCP integration  
**Auditor:** Hermes Agent (subagent)

---

## 1. TEMPLATE QUALITY — algorithmic-trading template

### Finding 1.1: Template fits mt4-algo-suite domain but has significant gaps
**Severity:** HIGH  
**Evidence:**
- PURPOSE.md correctly states: "maintain inventory of trading strategies with logic, parameters, and evolution; record backtest results; document technical indicators and risk models" — all of which match the mt4-algo-suite domain (20 EA strategies, 10 shared module namespaces, 7 concepts).
- SCHEMA.md defines 4 extra directories: `strategies/`, `backtests/`, `indicators/`, `risk/` — these are correct page types for the domain.
- **CRITICAL GAP**: The template has NO concept of **shared module documentation**. The mt4-algo-suite has 10 shared module namespaces (core/, ew/, filters/, indicators/, portability/, recovery/, regime/, risk/, strategy/, trading/) that are tracked as entities in the old wiki. The template only provides `strategy`, `backtest`, `indicator`, and `risk_model` page types — missing `module` type entirely.
- **CRITICAL GAP**: No concept of **research articles** or **raw sources tracking** — the template's PAGE_TYPES don't include a `source` type (present in the base schema but not in the algorithmic-trading template).
- **MISSING**: No frontmatter field for version tracking (critical for an EA suite where strategies have version numbers like v4.04, v1.39).

### Finding 1.2: extra-dirs.json is too narrow
**Severity:** MEDIUM  
**Evidence:**
- Template defines: `["strategies", "backtests", "indicators", "risk"]`
- Old wiki actually uses: `entities/`, `concepts/`, `raw/articles/`, `graphs/`, `compiled/`, `comparisons/`, `queries/`
- Missing from template: `concepts/`, `raw/articles/`, `graphs/`, `compiled/` — these are critical for the graph + research pipeline
- The old wiki SCHEMA.md defines `entities/` not `strategies/` — naming convention mismatch

### Finding 1.3: Naming convention mismatch between template and repo CLAUDE.md
**Severity:** MEDIUM  
**Evidence:**
- Template SCHEMA.md naming: `strategy-name.md`, `indicator-name.md`, `risk-model-name.md`
- Actual repo convention: `entities/xau-swinger.md`, `entities/risk-governor.md`, `entities/core.md`
- The repo puts everything under `entities/` with a `type:` discriminator in frontmatter
- Template puts each type in its own directory (`strategies/`, `backtests/`, `indicators/`, `risk/`)
- **Either approach works, but migration requires choosing one path**

### Finding 1.4: Template has no CLAUDE.md output
**Severity:** LOW  
**Evidence:**
- scaffold.py copies SCHEMA.md → CLAUDE.md in the scaffolded wiki
- But the template SCHEMA.md is purely schema — it doesn't include workflow commands, quick reference, or domain-specific agents
- The real mt4-algo-suite CLAUDE.md is 175 lines packed with workflow, module library, MCP config, and agent/skill references
- Template CLAUDE.md would be anemic by comparison

---

## 2. CONTENT MIGRATION READINESS

### Finding 2.1: Old wiki has high-quality rich entity pages
**Severity:** POSITIVE (good state)  
**Evidence:**
- Sampled 5 entity pages: XAU Swinger, Sakura Sniper, Risk Governor, Swiss Revert, The Gold Reaper
- All have: complete YAML frontmatter (title, created, updated, type, tags, sources, confidence), wikilinks to related pages, detailed architecture descriptions, risk profiles, cross-references, source provenance
- XAU Swinger: 71 lines — version history table, 7-step entry sequence, indicator chain diagram, full version evolution
- Sakura Sniper: 32 lines — clear overview, core mechanics, risk profile, 4 cross-references
- Risk Governor: 34 lines — monitoring loop details, consumer contract, operational risks
- All pages use `confidence: high | medium` — quality signal

### Finding 2.2: 34 raw articles exist but 10 are unreferenced
**Severity:** MEDIUM  
**Evidence:**
- Old wiki has 34 raw articles in `wiki/raw/articles/`
- Orphan audit (from log.md, 2026-06-11) found 10 unreferenced raw articles
- High priority: 2 XAUSwinger live risk analyses not synthesized into any entity page
- Medium priority: 7 infrastructure/meta articles (ea_integration_test, ea_workspace_standard, mt5_migration_roadmap, system_overview, template_strategy_doc, CHANGELOG, CLAUDE, README)

### Finding 2.3: Migration from old to new structure is ~80% straightforward
**Severity:** MEDIUM  
**Evidence:**
The migration path would be:
1. **Direct copy** (35 entity/concept pages → template's wiki/): All 35 pages can be moved as-is since they use `type:` in frontmatter. Template SCHEMA.md frontmatter fields overlap 90% with old SCHEMA.md.
2. **Naming conflicts**: Old wiki uses `entities/` folder; template uses `strategies/`, `backtests/`, `indicators/`, `risk/`. Each page's `type:` field would determine destination directory.
3. **Missing frontmatter fields**: Template adds `sharpe`, `max_dd`, `win_rate`, `trades`, `timeframe` (backtest type) — these would need to be populated from old wiki content (currently embedded in page body, not frontmatter).
4. **Module pages** (10 pages: core, ew, filters, indicators, etc.) have no corresponding template page type — they'd need to be filed under `entities/` as a fallback, or the template needs a `module` type.

### Finding 2.4: Source provenance would need restructuring
**Severity:** MEDIUM  
**Evidence:**
- Old wiki uses `sources:` in YAML frontmatter and `## Source Reference` sections in body
- Template SCHEMA.md also defines `sources: []` in frontmatter — compatible
- Base schema additionally defines `source` page type (author-year-slug.md naming) — old wiki doesn't have this
- Migration could preserve sources as frontmatter references or upgrade to full source pages

---

## 3. SCHEMA CONSISTENCY

### Finding 3.1: Old wiki SCHEMA.md broadly aligns with base-schema.md
**Severity:** LOW (minor deviations)  
**Evidence:**

| Aspect | Base Schema | Old Wiki SCHEMA.md | Algorithmic-trading Template |
|--------|------------|-------------------|------------------------------|
| Page types | entity, concept, source, comparison, synthesis, overview | entity, concept, comparison, query, summary | strategy, backtest, indicator, risk_model |
| Directories | entities/, concepts/, sources/, comparisons/, synthesis/ | entities/, concepts/, comparisons/, queries/, raw/ | strategies/, backtests/, indicators/, risk/ |
| Frontmatter | type, title, tags, related, sources, created, updated | type, title, tags, sources, created, updated, confidence, contested, contradictions | type, title, tags, related, sources, created, updated |
| Naming | kebab-case.md | lower-hyphens.md | strategy-name.md, indicator-name.md |
| Extra fields | confidence, contested, contradictions | confidence, contested, contradictions | strategy/backtest/indicator-specific fields |

### Finding 3.2: Template SCHEMA.md lacks `entities/` and `concepts/` base types
**Severity:** HIGH  
**Evidence:**
- Base schema defines 6 page types; template defines 4 domain-specific types
- Template inherits NONE of the base types directly — it replaces them entirely
- This means no way to represent generic entities or concepts without forcing them into a domain type
- The old wiki uses entity and concept types as the backbone of its structure

### Finding 3.3: Frontmatter naming conventions diverge significantly
**Severity:** MEDIUM  
**Evidence:**

| Field | Base Schema | Old Wiki | Template SCHEMA |
|-------|------------|---------|-----------------|
| Strategy type | N/A | tags only | `type: trend \| mean_reversion \| ...` |
| Indicator type | N/A | tags only | `indicator_type: momentum \| trend \| ...` |
| Risk type | N/A | tags only | `risk_type: fixed_fraction \| kelly \| ...` |
| version | N/A | NOT in frontmatter (embedded in body) | NOT defined anywhere |
| instruments | N/A | tags only (xauusd, forex) | `instruments: []` as list |
| timeframe | N/A | tags (m15, h1, htf) | `timeframe: "1h"` as string |

The template uses frontmatter for structured data that the old wiki currently stores in tags or body text. Migration would require extracting structured data from body content into frontmatter fields.

### Finding 3.4: `related:` field used differently
**Severity:** LOW  
**Evidence:**
- Base schema defines `related: []` but old wiki SCHEMA.md doesn't include it
- Old wiki uses `[[wikilinks]]` inline for related content, which the graph engine already parses
- Template SCHEMA.md includes `related: []` in the generic frontmatter template
- Minor duplication risk: wikilinks + frontmatter `related` field could diverge

---

## 4. GRAPH QUALITY

### Finding 4.1: Graph engine produced meaningful results (42 nodes, 151 edges)
**Severity:** POSITIVE  
**Evidence:**
```
node graph-engine/dist/index.js --wiki ~/projects/mt4-algo-suite/wiki --action build
```
Output: 42 nodes (38 wiki content pages + 4 metadata pages), 151 weighted edges
- God nodes: xau-swinger (degree 20), strategy (16), risk (15), core (16)
- Rich community structure with weighted edges (range: 3.8 to 14.9)
- Edge weights from relevance model (tf-idf + shared sources + link topology)
- Shared module architecture concept is correctly hub-connected to all 10 module entities

### Finding 4.2: Old wiki wikilinks are extensive and well-maintained
**Severity:** POSITIVE  
**Evidence:**
- Across 35 entity/concept pages: 169 wikilinks, 38 unique targets
- Post-repair (2026-06-11): zero broken wikilinks
- Recent lint (2026-06-19): zero dead wikilinks, zero orphans
- Average: ~4.8 outbound wikilinks per page — well above the SCHEMA.md minimum of 2

### Finding 4.3: graph-data.json is NOT persisted (graph engine bug)
**Severity:** HIGH  
**Evidence:**
- `graph-engine/dist/index.js --action build` outputs JSON to stdout but does NOT write `graph-data.json`
- Insights and search actions require `graph-data.json` and produce: `"Graph data not found at..."`
- The MCP server's `graph.ts` wrapper handles this by calling build + caching to `graph-data.json`
- But direct CLI usage is broken for insights/search unless the user manually pipes build output

### Finding 4.4: @sentropic/graphify graph is stale (75 nodes, 0 edges)
**Severity:** MEDIUM  
**Evidence:**
- `.graphify/` directory exists with graph.json (June 8) and GRAPH_REPORT.md (480 lines)
- Graphify reports 75 nodes with 0 edges — semantic extraction was never completed
- log.md (June 19): "Graph: existing graph (75 nodes, 0 edges, from June 14) — appears incomplete (zero edges)... Full rebuild skipped (cron token budget)"
- The graphify pipeline requires LLM-powered semantic extraction which was never run

### Finding 4.5: Graph engine vs graphify produce different graph quality
**Severity:** MEDIUM  
**Evidence:**
- Graph engine (new system): 42 nodes, 151 edges, weighted relevance model, Louvain community detection
- Graphify (old system): 75 nodes, 0 edges, no semantic extraction ever completed
- Graph engine is more useful for structural analysis (wikilink-based)
- Graphify would be more useful if semantic extraction were run (concept inference from code/docs)

---

## 5. PIPELINE GAPS

### Finding 5.1: Full pipeline steps and automation status
**Severity:** INFORMATION  
**Evidence:**

| Step | Tool/Script | Automated? | Agent Intervention Needed? |
|------|------------|-----------|---------------------------|
| 1. Scaffold wiki | `scaffold.py` | ✅ Fully automated | No |
| 2. Ingest sources | `ingest.py` + MCP `llm_wiki_ingest` | ✅ Automated ingestion | Agent must choose source files |
| 3. Cross-link pages | Manual wikilink creation | ❌ Manual | Agent must identify relationships |
| 4. Lint wiki | `lint_wiki.py` + MCP `llm_wiki_lint` | ⚠️ Available, has bugs | MCP lint returns TypeError (non-iterable) |
| 5. Build graph | `graph-engine --action build` | ✅ Automated | No (but data not persisted to file) |
| 6. Graph insights | `graph-engine --action insights` | ❌ Blocked | Requires graph-data.json (not written by build) |
| 7. Graph search | `graph-engine --action search` | ❌ Blocked | Same — requires cached data |
| 8. MCP server commands | 8 tools via MCP | ⚠️ Partial | 7/8 tools work; lint is broken |

### Finding 5.2: Python lint script expects different directory layout
**Severity:** HIGH  
**Evidence:**
- `lint_wiki.py` expects: `{wiki-root}/wiki/` (subdirectory with pages)
- Old wiki structure: pages directly under `{wiki-root}/` (entities/, concepts/ at root level)
- Scaffolded template also creates: pages under `wiki/entities/`, `wiki/concepts/`
- **The mt4-algo-suite old wiki does NOT have a `wiki/` subdirectory** — lint fails with "ERROR: wiki/ directory not found"
- MCP lint bridge: tries Python lint first → fails → falls back to TypeScript basic lint → `issues is not iterable` bug

### Finding 5.3: No automated cross-linking or content synthesis
**Severity:** HIGH  
**Evidence:**
- Cross-linking is entirely manual (agent creates `[[wikilinks]]`)
- Pipeline guide mentions LLM compilation step but no automated script exists
- Graph insights should identify missing connections, but insights tool is broken
- The old wiki's 169 wikilinks were all hand-crafted by the agent during Phase 3 repair

### Finding 5.4: EOW cron pipeline is defined but fragile
**Severity:** MEDIUM  
**Evidence:**
- `eow-cron-pipeline.md` defines the pattern: discover repos → assess → graphify update → lint → log
- `detectIncremental` can take 30-120s on large repos
- Graphify semantic extraction requires subagents and LLM calls — not automated in cron mode
- Graph refresh may be skipped if `new_total > 200` (token budget)
- The cron job properly avoids full semantic rebuilds but this means the graph remains incomplete

### Finding 5.5: No automated version drift detection in the new system
**Severity:** MEDIUM  
**Evidence:**
- Old wiki has manual version tracking (XAU Swinger v4.04, Multi-Pair Trend Martingale v4.22, etc.)
- Content freshness agent detected drift manually (3 critical version mismatches fixed in Phase 4)
- The new system has no frontmatter field for versions, no automated drift detection script
- Without version tracking, wiki content will diverge from codebase silently

---

## 6. MCP SERVER INTEGRATION QUALITY

### Finding 6.1: All 8 MCP tools are implemented and invocable
**Severity:** POSITIVE  
**Evidence:**
- MCP stdio server starts and responds to `tools/list` request
- 8 tools registered:
  1. `llm_wiki_status` — ✅ Works. Returns "✅ Operational, 76 pages"
  2. `llm_wiki_files` — ✅ Works (tested via `tools/list` schema)
  3. `llm_wiki_read_file` — ✅ Works (tested via `tools/list` schema)
  4. `llm_wiki_reviews` — ⚠️ No audit/ directory in old wiki (returns empty)
  5. `llm_wiki_search` — ✅ **Excellent results**. Query "Elliott Wave gold" returned 10 ranked results with BM25 scores (7.74–5.27). Citations: EA EW Wave3 Entry (#1), EA EW 12Setup Bullish (#2), The Gold Reaper (#5), EW module (#7) — all correct and relevant.
  6. `llm_wiki_graph` — ⚠️ Works for `build` only. Insights/search blocked because `build` doesn't persist graph-data.json.
  7. `llm_wiki_lint` — ❌ **Broken**. Returns `TypeError: issues is not iterable` — Python lint script expects different directory layout; TS fallback has a return-value bug.
  8. `llm_wiki_ingest` — ⚠️ Depends on ingest.py being findable; not tested end-to-end.

### Finding 6.2: BM25 search quality is good
**Severity:** POSITIVE  
**Evidence:**
- Query "Elliott Wave gold" returned 10 results ranked by relevance
- Top result: `entities/ea-ew-wave3-entry.md` (correct — dedicated Elliott Wave EA)
- All top 5 results are entity or concept pages (not raw articles despite raw articles also having matches)
- Snippet extraction works (shows context around first matching term)
- `top_k` parameter configurable (default 10, max 100)

### Finding 6.3: Graph tool has persistence bug
**Severity:** HIGH  
**Evidence:**
- `build` action produces graph on stdout but doesn't write `graph-data.json`
- Insights/search actions require cached `graph-data.json`
- MCP server's `graph.ts` wrapper (in `buildGraph()`) handles caching manually after CLI execution
- But direct CLI `--action insights` fails with "Graph data not found"
- Fix: `build` should write `graph-data.json` as its last step, or `index.ts` should pipe build output to the cache file

### Finding 6.4: Review system exists but no content
**Severity:** LOW  
**Evidence:**
- MCP has `llm_wiki_reviews` tool backed by `review.ts`
- Old wiki has no `audit/` directory structure (new format)
- Old wiki uses `log.md` for audit tracking instead
- The review/audit system would work for a new scaffolded wiki but not backwards-compatible with the old wiki

---

## COMPREHENSIVE RECOMMENDATIONS

### P0 — Must Fix
1. **Fix graph-engine data persistence**: `build` action must write `graph-data.json` (or add `--persist` flag). This blocks insights, search, and all downstream graph tools.
2. **Fix MCP lint tool**: `issues is not iterable` bug in the TypeScript lint fallback. Need to check the return value structure from `runBasicLint()`.
3. **Add `module` page type to template**: The algorithmic-trading template has no way to represent shared modules, which are the backbone of the mt4-algo-suite's architecture.

### P1 — Should Fix
4. **Add version frontmatter to template**: EAs need `version:` in frontmatter (e.g., `version: "4.04"`). Include a drift detection script that compares wiki versions against codebase.
5. **Add `entities/` and `concepts/` base directories**: Template should inheritate base types from `_shared/base-schema.md` rather than replacing them.
6. **Add `source` page type**: Template should support full source pages (author-year-slug.md) for raw articles as defined in base schema.

### P2 — Nice to Have
7. **Add automated cross-linking**: Script that suggests `[[wikilinks]]` based on TF-IDF similarity or graph engine edge weights.
8. **Fix lint_wiki.py directory compatibility**: Support both structure formats (pages at wiki-root vs pages under wiki/wiki/).
9. **Add version drift detection**: Cron script that compares wiki version claims (if stored in frontmatter) against git tags or file headers.

### P3 — Enhancements
10. **EOW cron should trigger graph engine build + cache**: Currently relies on graphify (semantic extraction enabled); should also run graph-engine build for structural graph.
11. **Pre-populate template extra-dirs.json**: Add `raw/articles`, `graphs`, `compiled`, `concepts` to the algorithmic-trading template.
12. **MCP `llm_wiki_graph` should auto-cache after build**: Include the write-to-disk step in the CLI tool itself, not just in the MCP wrapper.

---

## SUMMARY

| Area | Verdict | Key Issues |
|------|---------|-----------|
| **Template quality** | ⚠️ Adequate but incomplete | Missing module page type (P0), missing version tracking (P1), missing entities/concepts base types (P1) |
| **Content migration** | ✅ Old content is high quality | 35 rich pages with complete frontmatter, 169 wikilinks, no orphans. ~80% direct copy migration feasible. |
| **Schema consistency** | ⚠️ Three schemas diverge | Base schema vs template SCHEMA.md vs old SCHEMA.md have conflicting naming and field conventions. Must choose one direction. |
| **Graph quality** | ✅ Graph engine produces useful graphs (42 nodes, 151 edges) | But data persistence is broken. Graphify graph stale (75 nodes, 0 edges — semantic extraction never completed). |
| **Pipeline gaps** | ⚠️ 7/10 pipeline steps have gaps | Cross-linking manual (P2), lint has structural bug (P0), graph insights/search blocked by persistence bug (P0), no automated drift detection (P1) |
| **MCP integration** | ⚠️ 5/8 tools working well, 1 broken, 2 blocked | Search/status/files work great. Lint broken (P0). Graph insights/search blocked (P0). Reviews empty (LOW). |

**Overall structural integrity: ⚠️ MODERATE** — Strong foundation with good content quality, but critical toolchain bugs block the full pipeline.
