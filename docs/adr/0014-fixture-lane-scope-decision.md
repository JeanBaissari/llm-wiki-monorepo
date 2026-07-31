# ADR 0014: Fixture Lane Scope — Core vs Optional Classification

- **Status:** accepted
- **Date:** 2026-07-31
- **Context:** LWM_012 specifies 9 fixture certification lanes. Lanes 1-3 (core wiki, graph topology, MCP transcripts) are complete. Lanes 4-8 required decisions about which to implement vs reclassify based on component tier.

## Decision

| Lane | Component | Tier | Decision | Rationale |
|------|-----------|:---:|----------|-----------|
| 4 — Web routes | web-viewer | optional | **Implemented** | Route handlers contain real security logic (path traversal rejection, bad payload 400s). Tests import route modules directly without full Express server — valuable for catching regressions. |
| 5 — Audit entries | audit-shared | core | **Implemented** | Fixtures existed but were schema-stale. Regenerated against current zod `AuditEntrySchema` + wired into vitest. Most tractable lane — fixtures were 90% present, just needed regeneration. |
| 6 — Browser clipper | extension | optional | **Reclassified** | Zero existing test infrastructure in `extension/`. No package.json, no vitest, no test runner. Browser-dependent libs (Readability/Turndown) require jsdom + Chrome API mocks. Standalone verification: load `extension/` in Chrome, clip a test page, verify Markdown output. |
| 7 — Obsidian vaults | plugins/obsidian-audit | optional | **Reclassified** | Zero tests in plugin. Requires Obsidian `App`/`Vault` mocks and `"obsidian"` module stubbing (only resolves inside Obsidian runtime). Standalone verification: install plugin in Obsidian, run `audit-add-feedback` command, verify file written to `audit/`. |
| 8 — Deep research | src/llm_wiki | core | **Implemented** | Core-tier feature. Most tractable — pure Python with injectable subprocess boundary. Fixture wiki + 6 deterministic tests created. |

## Consequences

**Easier:** Release certification focuses on core-tier components. Optional components have documented standalone verification paths — no CI integration needed.

**Remaining:** Lanes 6+7 fixtures may be added later if the components are promoted to first-class. The ADR documents why they're deferred and how to verify them manually.

## Manual Verification Commands

```bash
# Lane 6 — Browser clipper
# 1. Load extension/ as unpacked Chrome extension
# 2. Navigate to any article page
# 3. Click extension icon → "Clip Page"
# 4. Verify Markdown saved with frontmatter (source_url, ingested, source_type)

# Lane 7 — Obsidian plugin
# 1. Copy plugins/obsidian-audit/main.js to vault/.obsidian/plugins/obsidian-audit/
# 2. Open Obsidian vault, enable plugin
# 3. Select text in any note → Mod+'
# 4. Verify audit entry written to vault/audit/
```
