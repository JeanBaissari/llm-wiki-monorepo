# v0.3.1 Batch Execution Plan

Status: IN PROGRESS | Branch strategy: worktrees → `v0.3.1/*` → merge to main

---

## Architecture

```
main (v0.3.0)
  ├── worktree: v0.3.1/batch-a  → docs + infrastructure
  ├── worktree: v0.3.1/batch-b  → CI + provenance + operation hardening
  ├── worktree: v0.3.1/batch-c  → TypeScript features (OperationContext, validators)
  ├── worktree: v0.3.1/batch-d  → claims features (confidence, --claims flag)
  └── worktree: v0.3.1/batch-e  → fixtures + tests (MCP transcripts, deep-research)
```

Each batch:
1. Sub-agent executes in its worktree
2. Sub-agent commits changes
3. I verify (tests + acceptance criteria)
4. I merge into main
5. Next batch starts

---

## Batch A — Docs & Infrastructure Completeness

**Worktree:** `v0.3.1/batch-a`
**Scope:** No code changes. Documentation + metadata updates only.
**PRDs:** LWM_001, LWM_004, LWM_009 (docs-only gaps)
**Estimated:** 25 min

### Tasks

#### A1 — Add component tier classification (LWM_001)
- Add "Tier" column to AGENTS.md Package Map table
- Classify each package as: core, adapter, programmatic-access, analysis, optional
- Update README.md Packages table similarly

#### A2 — Propagate product identity (LWM_001)
- Verify "agent-native file-first knowledge compiler" phrase exists in README.md ✅
- Add phrase to docs/architecture/overview.md (PURPOSE.md)
- Add phrase to docs/getting-started/quickstart.md

#### A3 — Add test scripts to packages (LWM_004)
- Add `"test": "vitest run"` to graph-bridge/package.json (or classify as optional)
- Add `"test": "node --test dist/*.test.js"` to audit-shared/package.json (fail closed)
- Update `scripts/zero_test_guard.py` if graph-bridge stays optional

#### A4 — schema_version in generated docs (LWM_009)
- Add `schema_version` field documentation to `schema/generated/base-schema.md`
- Add "GENERATED FROM schema/versions/v0.2.1/ — DO NOT EDIT" marker to templates/_shared/base-schema.md

### Verification
```bash
python3 scripts/docs_truth_check.py --json
python3 scripts/release_manifest.py --json
npm run typecheck --workspaces --if-present
```

---

## Batch B — CI + Provenance + Operation Hardening

**Worktree:** `v0.3.1/batch-b`
**Scope:** CI config, scripts, small code hardening
**PRDs:** LWM_002, LWM_009 (CI gate), LWM_010 (mandatory import)
**Estimated:** 30 min

### Tasks

#### B1 — Integrate provenance scan into CI (LWM_002)
- Add provenance scan job to `.github/workflows/ci.yml`
- Run `python3 scripts/provenance_scan.py` and fail on unresolved markers

#### B2 — Regenerate package-lock.json (LWM_002)
- Run `npm install` to regenerate `package-lock.json` with v0.3.0 version
- Verify version matches `package.json`

#### B3 — Add CI fixture freshness gate (LWM_009)
- Add job to `.github/workflows/ci.yml`: `python3 -m pytest tests/test_fixtures_fresh.py -q`
- Fail CI on stale fixtures

#### B4 — Make OperationContext mandatory (LWM_010)
- In `src/llm_wiki/operation.py`, remove try/except ImportError fallback
- OperationContext import failures should raise ImportError (not silently skip)
- Update all 4 callers (ingest, backup, link-suggest, deep-research) to import unconditionally

#### B5 — Add operation manifest file creation (LWM_010)
- In OperationContext.__exit__, create `.llm-wiki/operations/completed/{operation_id}.json`
- Write operation manifest: id, run_id, command, started, finished, inputs, touched_paths

### Verification
```bash
python3 scripts/provenance_scan.py
python3 -m pytest tests/test_fixtures_fresh.py -q
python3 -m pytest tests/ -q -m "not slow"
```

---

## Batch C — TypeScript Features

**Worktree:** `v0.3.1/batch-c`
**Scope:** New TypeScript code in audit-shared, shared-types
**PRDs:** LWM_010 (TS OperationContext), LWM_009 (TS validator)
**Estimated:** 2h

### Tasks

#### C1 — TypeScript OperationContext (LWM_010)
- Create `audit-shared/src/ops/context.ts`
- Model: OperationContext class with id, run_id, command, start/end timestamps, inputs, touched_paths
- Export types matching LWM_009 operation-manifest schema
- Add to audit-shared/src/index.ts exports

#### C2 — Make TS validator load JSON schemas (LWM_009)
- Update `audit-shared/src/schema_validator.ts` to load schemas from `schema/versions/v0.2.1/`
- Use `jsonschema` or `zod` `fromJSONSchema` or manual loading
- Validate against golden fixtures (same as Python validator)
- Add test verifying Python and TS validators agree on all 10 valid + 8 invalid fixtures

#### C3 — Graph-bridge test infrastructure (LWM_004)
- Add vitest.config.ts to graph-bridge
- Add placeholder test file
- Update graph-bridge/package.json with `"test": "vitest run"`

### Verification
```bash
cd audit-shared && npx tsc --noEmit && npm test
cd graph-bridge && npm install && npx tsc --noEmit && npm test
npm run typecheck --workspaces --if-present
```

---

## Batch D — Claims Features

**Worktree:** `v0.3.1/batch-d`
**Scope:** New Python code in quality/claims/
**PRDs:** LWM_011 (Phases 3-5)
**Estimated:** 1.5h

### Tasks

#### D1 — Page confidence compilation (LWM_011 Phase 3)
- In `ClaimsManager`, add `page_confidence(page_slug: str) -> str` method
- Logic: aggregate claim confidences for a page → "high"/"medium"/"low"/"unknown"
- Add to health report: per-page confidence breakdown
- Add CLI: `llm-wiki claims health --page wiki/concepts/example.md`

#### D2 — Ingest --claims flag (LWM_011 Phase 4)
- Add `--claims` flag to `llm_wiki ingest`
- When set, extend Stage 1 analysis prompt to extract candidate claims
- Parse claim blocks from LLM output (---CLAIM: block type)
- Write candidate claims to sidecar via ClaimsManager

#### D3 — Convenience methods (LWM_011)
- `ClaimsManager.reinforce_claim(claim_id, source)`
- `ClaimsManager.challenge_claim(claim_id, source, evidence)`
- `ClaimsManager.weaken_claim(claim_id, source)`
- `ClaimsManager.supersede_claim(claim_id, replacement_claim_id)`
- `ClaimsManager.resolve_contradiction(contradiction_id, resolution_claim_id)`

#### D4 — Sidecar indexes (LWM_011)
- On ClaimsManager init, build in-memory indexes:
  - `by_page`: claim_id → page_slug
  - `by_source`: claim_id → source_file
  - `by_status`: status → [claim_ids]

### Verification
```bash
python3 -m pytest tests/test_claims.py -q
python3 -m pytest tests/test_ingest.py -q
PYTHONPATH=src python3 -m llm_wiki claims health --help
```

---

## Batch E — Fixtures + Tests

**Worktree:** `v0.3.1/batch-e`
**Scope:** New test fixtures, new test files
**PRDs:** LWM_012 (fixture lanes 3-9)
**Estimated:** 2h

### Tasks

#### E1 — MCP transcript fixtures (LWM_012 lane 3)
- Create `tests/fixtures/mcp_transcripts/`
- Golden JSON requests: tools/list, tools/call (status, files, read_file, search, lint)
- Golden JSON responses: matching expected output
- Test: `tests/test_mcp_transcripts.py` — replay each transcript against a temp wiki, assert responses match

#### E2 — Deep-research deterministic tests (LWM_012)
- Create `tests/test_deep_research.py`
- Mock `call_llm()` and `urlopen()` with fixture responses
- Test: single-source → 1 page output
- Test: multi-source → N pages + index update
- Test: empty source → no crash, empty wiki

#### E3 — Docs example contract tests (LWM_012)
- `tests/test_docs_examples.py`
- Extract every ````bash` code block from README.md, AGENTS.md, quickstart.md, cli.md
- Run each command (or mock as needed)
- Assert exit codes match documented behavior

#### E4 — Fixture regeneration + verify
- Run `python3 skill/scripts/regenerate_fixtures.py`
- Run `python3 skill/scripts/validate_fixtures.py`
- Run `python3 -m pytest tests/test_fixtures_fresh.py -q`
- Remove fixture freshness warnings from conftest.py

### Verification
```bash
python3 -m pytest tests/test_mcp_transcripts.py tests/test_deep_research.py tests/test_docs_examples.py -q
python3 -m pytest tests/test_fixtures_fresh.py -q
```

---

## Execution Order

```
1. Batch A (docs) — dispatches first, no code dependencies
2. Batch B (CI/hardening) — dispatches after A, no dependency on C/D/E
3. Batch C + D + E (features) — dispatch in parallel after B
   All three are independent — different languages, different modules
```

## Merge Strategy

```
main
  ← merge v0.3.1/batch-a
  ← merge v0.3.1/batch-b
  ← merge v0.3.1/batch-c ──┐
  ← merge v0.3.1/batch-d ──┤ (parallel, merge in any order)
  ← merge v0.3.1/batch-e ──┘
  → tag v0.3.1
  → push
```

## Verification Gate (before each merge)

```bash
# Python full suite
python3 -m pytest tests/ -q -m "not slow"

# TypeScript full check
npm run typecheck --workspaces --if-present
npm run build --workspaces --if-present

# Acceptance criteria script
python3 _verify_modularization.py
```
