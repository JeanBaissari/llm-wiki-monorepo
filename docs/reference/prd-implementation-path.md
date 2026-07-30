# v0.3.0 PRD Implementation Path — Refined for Modular Architecture

Last updated: 2026-07-30 | Aligned with: v0.3.0 modular package layout (ADR 0013)

---

## Overview

This document takes the 12 PRDs originally written for v0.2.1 stabilization and refines them for the v0.3.0 modular architecture. Every path reference, import example, and module location is updated. Each PRD includes:
- **Status** — what's implemented vs pending
- **v0.3.0 paths** — where code lives now  
- **Technical example** — practical usage in the new structure
- **Remaining work** — what still needs to be done

---

## How to Read This

- ✅ = Fully implemented
- ⚡ = Partially implemented
- ❌ = Not implemented
- 🔮 = Deferred (non-blocking)

---

## PRD 1: LWM_001 — Project Vision, Scope, and Boundaries

**Status:** ⚡ Partially implemented
**Priority:** MEDIUM | **Blocks:** LWM_002–LWM_006

### What it specified
- Define the product as "agent-native, file-first knowledge compiler"
- Classify all components into tiers (core, adapter, programmatic access, analysis, optional)
- Freeze v0.2.1 as a stabilization release — no feature expansion

### v0.3.0 status
| Requirement | Status |
|---|:---:|
| Product identity phrase in all 4 docs | ⚡ In README.md, AGENTS.md; PURPOSE.md and quickstart partial |
| Component tier classification | ❌ Not yet in docs tables |
| "Stabilization release" framing | ✅ CHANGELOG.md has v0.2.1 → v0.3.0 entries |
| No desktop parity claims | ✅ None present |
| Documented `llm-wiki <command>` inventory | ✅ All 15 commands in CLI + quickstart |

### Updated paths (v0.3.0 modular)
| v0.2.1 reference | v0.3.0 location |
|---|---|
| `src/llm_wiki` (flat, all modules) | `src/llm_wiki/{core,quality,ingest,graph,search,ops,wiki,research,contracts,providers}/` |
| `README.md` component list | `README.md` architecture diagram updated |
| `AGENTS.md` Package Map | Still at root; needs tier column |

### Technical example — new module layout imports
```python
# OLD (v0.2.1 flat)
from llm_wiki.ingest import main
from llm_wiki.health_check import check_wiki_health
from llm_wiki.lint_wiki import lint

# NEW (v0.3.0 modular)
from llm_wiki.ingest.pipeline import main
from llm_wiki.ops.health import check_wiki_health
from llm_wiki.quality.lint.service import lint
```

### Remaining work
1. Add component tier column to AGENTS.md Package Map table (core/adapter/access/analysis/optional)
2. Complete product identity phrase propagation to `docs/architecture/overview.md` and `docs/getting-started/quickstart.md`

---

## PRD 2: LWM_002 — License, Provenance, and Open Source Policy

**Status:** ⚡ Partially implemented
**Priority:** HIGH | **Blocks:** v0.3.0 public release

### What it specified
- Create provenance inventory for all files with upstream markers
- Resolve GPL provenance on `graph-engine/src/relevance.ts` and `insights.ts`
- Create THIRD_PARTY.md, NOTICE.md, LICENSE
- Add provenance scan to CI

### v0.3.0 status
| Requirement | Status |
|---|:---:|
| LICENSE file (MIT) | ✅ Created at repo root |
| THIRD_PARTY.md (provenance ledger) | ✅ At `docs/legal/provenance.md` |
| NOTICE.md (attribution) | ✅ At `docs/legal/notices.md` |
| Provenance scan script | ✅ `scripts/provenance_scan.py` exists |
| Provenance in CI | ❌ Not yet integrated |
| GPL resolution on relevance.ts + insights.ts | ⚡ Classified `P` (Ported) with `clean_room_replace` — pending actual rewrite |
| package-lock.json version | ⚡ Present but may be stale |

### Technical example — provenance scan
```bash
# Run provenance scan against the repo
python3 scripts/provenance_scan.py

# With explicit root
python3 scripts/provenance_scan.py --root /path/to/repo

# Expected output: passes when all markers resolved, fails on unknowns
exit 0  # clean
exit 1  # unresolved provenance markers found
```

### Remaining work
1. Integrate `provenance_scan.py` into CI (`.github/workflows/ci.yml`)
2. Actually rewrite `graph-engine/src/relevance.ts` and `insights.ts` (clean-room replacement)
3. Regenerate `package-lock.json` to match `package.json` v0.3.0
4. Move `docs/legal/notices.md` content into PyPI wheel via `[tool.setuptools.package-data]`

---

## PRD 3: LWM_003 — Version, Release Manifest, and Docs Truth

**Status:** ⚡ Partially implemented
**Priority:** HIGH

### What it specified
- Create `release-manifest.json` at repo root
- Create `scripts/release_manifest.py` validator
- Create `scripts/docs_truth_check.py`
- Fix MCP tool count / template count / CLI command drift in docs
- CI fails closed on manifest drift

### v0.3.0 status
| Requirement | Status |
|---|:---:|
| release-manifest.json | ✅ Exists, console_scripts updated to modular paths |
| release validator | ✅ `scripts/release_manifest.py` works |
| docs truth checker | ✅ `scripts/docs_truth_check.py` exists |
| MCP tool count (14) in all docs | ✅ All 4 docs say 14 (verified) |
| Template count (20) in docs | ✅ Not hardcoded; `--list-templates` used instead |
| All 15 CLI commands in manifest | ✅ Updated |
| CI runs validator on PR | ✅ In `ci.yml` |
| console_scripts importable | ✅ All resolve to modular paths |

### Updated paths (v0.3.0 modular)
```json
// release-manifest.json — updated console_scripts
"llm-wiki-scaffold = llm_wiki.wiki.scaffold:main",
"llm-wiki-ingest = llm_wiki.ingest.pipeline:main",
"llm-wiki-lint = llm_wiki.quality.lint:main",
"llm-wiki-insights = llm_wiki.graph.insights:main",
"llm-wiki-link-suggest = llm_wiki.graph.suggest:main",
"llm-wiki-backup = llm_wiki.wiki.backup:main",
"llm-wiki-benchmark = llm_wiki.ops.benchmark:main",
"llm-wiki-deep-research = llm_wiki.research.deep_research:main",
"llm-wiki-audit = llm_wiki.quality.audit:main",
"llm-wiki-discover = llm_wiki.core.layout:main",
"llm-wiki-index = llm_wiki.search.index:main",
"llm-wiki-health = llm_wiki.ops.health:main",
"llm-wiki-serve = llm_wiki.ops.serve:main"
```

### Technical example — validate release manifest
```bash
# Check that all docs and manifests are consistent
python3 scripts/release_manifest.py --json
# Exit 0 = clean, Exit 1 = drift detected

python3 scripts/docs_truth_check.py --json
# Compares MCP tool counts, template lists, CLI commands across all docs
```

### Remaining work
1. Add MCP tool metadata generation from registry → docs (eliminate manual drift)

---

## PRD 4: LWM_004 — Workspace, CI, and Package Test Gates

**Status:** ⚡ Partially implemented
**Priority:** HIGH

### What it specified
- All first-class TS packages in root npm workspaces
- Every package has typecheck/build/test scripts
- Zero-test guard prevents false-green test passes
- CI matrix covers all packages

### v0.3.0 status
| Requirement | Status |
|---|:---:|
| All packages in workspaces | ✅ Including new `packages/shared-types` |
| typecheck scripts | ✅ All packages have them |
| build scripts | ✅ All packages have them |
| test scripts | ⚡ graph-bridge has none; audit-shared has placeholder |
| zero-test guard | ✅ `scripts/zero_test_guard.py` exists |
| CI matrix (Python 3.10-3.12, Node 18-22) | ✅ In `ci.yml` |
| vitest deps installed | ✅ Installed in mcp-server + graph-engine |

### Updated workspaces (v0.3.0)
```json
// package.json — workspaces
"workspaces": [
    "mcp-server",
    "graph-engine",
    "graph-bridge",
    "packages/shared-types",
    "web-viewer",
    "audit-shared",
    "plugins/obsidian-audit"
]
```

### Technical example — run full workspace test
```bash
# Install all workspace deps
npm install

# Typecheck everything
npm run typecheck --workspaces --if-present

# Build everything
npm run build --workspaces --if-present

# Test everything
npm run test --workspaces --if-present

# Python tests
python3 -m pytest tests/ -q -m "not slow"
```

### Remaining work
1. Add test script to `graph-bridge` or classify as optional in manifest
2. Make `audit-shared` test script fail closed (not `echo '# tests 0'`)
3. Add `typecheck` to `web-viewer` and `plugins/obsidian-audit`

---

## PRD 5: LWM_005 — Python Core and Skill Wrapper Unification

**Status:** ✅ Implemented (and refactored beyond spec)
**Priority:** LOW (complete)

### What it specified (original v0.2.1)
- Make `src/llm_wiki` canonical; convert `skill/scripts/*.py` to thin wrappers
- Add `health_check.py`, `wiki_logging.py`, `index` and `health` to CLI
- Fix `__main__.py` exit code; add drift tests

### v0.3.0 status — fully implemented AND modularized
| Requirement | Status |
|---|:---:|
| `src/llm_wiki` is canonical | ✅ |
| All 13 skill/scripts are thin wrappers | ✅ |
| `index`, `health`, `serve`, `claims` in CLI | ✅ 15 commands |
| Unknown commands exit non-zero | ✅ |
| Drift tests prevent divergence | ✅ `tests/test_drift.py` |

### Updated paths (v0.3.0 modular)
Old → new:
```
src/llm_wiki/scaffold.py      → src/llm_wiki/wiki/scaffold.py
src/llm_wiki/ingest.py        → src/llm_wiki/ingest/pipeline.py
src/llm_wiki/lint_wiki.py     → src/llm_wiki/quality/lint/service.py
src/llm_wiki/discover.py      → src/llm_wiki/core/layout.py
src/llm_wiki/graph_insights.py → src/llm_wiki/graph/insights.py
src/llm_wiki/backup.py        → src/llm_wiki/wiki/backup.py
src/llm_wiki/index_wiki.py    → src/llm_wiki/search/index.py
src/llm_wiki/link_suggest.py  → src/llm_wiki/graph/suggest.py
src/llm_wiki/benchmark.py     → src/llm_wiki/ops/benchmark.py
src/llm_wiki/audit_review.py  → src/llm_wiki/quality/audit/review.py
src/llm_wiki/deep_research.py → src/llm_wiki/research/deep_research.py
src/llm_wiki/migrate_log.py   → src/llm_wiki/ops/migrate.py
src/llm_wiki/health_check.py  → src/llm_wiki/ops/health.py
```

### Technical example — thin wrapper pattern
```python
# skill/scripts/scaffold.py
"""Thin wrapper — delegates to llm_wiki.wiki.scaffold."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm_wiki.wiki.scaffold import main

if __name__ == "__main__":
    raise SystemExit(main())
```

### Remaining work
- None. This PRD is complete.

---

## PRD 6: LWM_006 — Local Concurrency Locks and Atomic Writes

**Status:** ✅ Implemented
**Priority:** LOW (complete)

### What it specified
- Fix `write_wiki` lock-across-read-hash-write
- Fix `backup --verify` empty-file detection
- Protect index/log/cache writes with atomic/locking
- Multi-process concurrency tests

### v0.3.0 status — fully implemented
| Requirement | Status |
|---|:---:|
| `write_wiki` locks across full operation | ✅ |
| `test_lock_timeout_failure` returns `locked` | ✅ |
| Hash conflicts detected as conflicts | ✅ |
| `backup --verify` catches empty files | ✅ |
| Index/log/cache writes protected | ✅ |
| 50 concurrency tests pass | ✅ |

### Updated paths (v0.3.0 modular)
```
src/llm_wiki/lock_wiki.py    → src/llm_wiki/core/locking.py
src/llm_wiki/atomic_write.py → src/llm_wiki/core/atomic.py
src/llm_wiki/content_hash.py → src/llm_wiki/core/hashing.py
src/llm_wiki/ingest.py (write_wiki) → src/llm_wiki/ingest/writer.py
```

### Technical example — concurrency-safe wiki write
```python
from llm_wiki.core.locking import WikiLock
from llm_wiki.core.atomic import atomic_write
from llm_wiki.core.hashing import compute_hash, inject_hash

def write_wiki(root, rpath, content, force=False):
    lock = WikiLock(target_path)
    try:
        lock.__enter__()
        current = read_file(target_path)
        if current and not force:
            if compute_hash(current) != compute_hash(content):
                # Conflict detected — save to conflict file
                atomic_write(conflict_path, content)
                return ("conflict", True)
        final = inject_hash(content)
        ok = atomic_write(target_path, final)
        return ("created" if not current else "updated", ok)
    finally:
        lock.__exit__(None, None, None)
```

### Remaining work
- None. This PRD is complete.

---

## PRD 7: LWM_007 — MCP Tool Registry, Stdio E2E, Path Safety

**Status:** ✅ Implemented (and modularized beyond spec)
**Priority:** LOW (complete)

### What it specified
- Canonical TOOL_DEFINITIONS registry
- Project-scoped path policy (safeJoin, allow-list, symlink safety)
- Side-effect metadata on all 14 tools
- Stdio E2E tests
- TypeScript typecheck repair

### v0.3.0 status — fully implemented AND modularized
| Requirement | Status |
|---|:---:|
| 14 tool schemas in registry | ✅ `mcp-server/src/registry.ts` |
| safeJoin path safety | ✅ `mcp-server/src/security/path-safety.ts` |
| Side-effect metadata | ✅ all 14 tools annotated |
| Stdio E2E tests | ✅ `test_stdio_e2e.test.ts` |
| TypeScript typecheck | ✅ passes |

### Updated paths (v0.3.0 MCP modular)
```
mcp-server/src/index.ts         → DELETED (split into 20 files)
mcp-server/src/registry.ts      → all TOOL_DEFINITIONS + dispatch
mcp-server/src/tools/*.ts       → per-tool handlers (status, files, search, graph, lint, ingest, etc.)
mcp-server/src/adapters/        → sidecar.ts, fts5.ts, graph-engine.ts
mcp-server/src/projects/        → config.ts, discover.ts
mcp-server/src/security/        → path-safety.ts
mcp-server/src/main.ts          → CLI entry (thin)
```

### Technical example — adding a new MCP tool
```typescript
// mcp-server/src/tools/example.ts
import { PythonSidecar } from "../adapters/sidecar.js";

export async function handleExample(
    wikiRoot: string,
    args: Record<string, unknown>,
    sidecar?: PythonSidecar
): Promise<{ content: { type: string; text: string }[]; isError?: boolean }> {
    return {
        content: [{ type: "text", text: "Example tool response" }]
    };
}
```

```typescript
// mcp-server/src/registry.ts — add to TOOL_DEFINITIONS
{
    name: "llm_wiki_example",
    description: "Example tool description.",
    inputSchema: { /* ... */ },
    handler: handleExample,           // reference to the handler function
    sideEffect: "read_only",           // metadata classification
}
```

### Remaining work
- None. This PRD is complete.

---

## PRD 8: LWM_008 — Graph Engine Louvain, Relevance API, Typecheck

**Status:** ✅ Implemented
**Priority:** LOW (complete)

### What it specified
- Integrate Louvain into `buildWikiGraph()`
- Repair stale `buildGraphStructure` API
- Import-safe CLI guard
- TypeScript typecheck repair
- Non-zero tests

### v0.3.0 status — fully implemented
| Requirement | Status |
|---|:---:|
| Louvain integrated into build | ✅ |
| `buildGraphStructure` restored | ✅ |
| Import-safe (CLI guarded) | ✅ |
| TypeScript typecheck passes | ✅ |
| Tests run non-zero | ✅ |

### Technical example — building a graph with Louvain communities
```typescript
// graph-engine/src/build.ts
import { detectCommunities } from "./louvain.js";

export function buildWikiGraph(wikiRoot: string): GraphData {
    const nodes = /* parse wiki pages */;
    const edges = /* extract wikilinks */;

    // Louvain community detection with seed for reproducibility
    const { assignments, communities } = detectCommunities(nodes, edges, {
        seed: 42,
        resolution: 1.0,
    });

    nodes.forEach(n => {
        n.community = assignments.get(n.id) ?? -1;
    });

    return { nodes, edges, communities };
}
```

### Remaining work
- None. This PRD is complete.

---

## PRD 9: LWM_009 — Machine-Readable Schema and Migrations

**Status:** ⚡ Partially implemented
**Priority:** MEDIUM | **Blocks v0.3.0 release:** YES

### What it specified (4 phases)
1. JSON schemas for page, audit, operation-event, operation-manifest, template, claim-sidecar
2. Frontmatter parser consolidation (one Python, one TypeScript)
3. Audit schema completeness (anchor validation fixtures)
4. Migration registry + CI gates

### v0.3.0 status
| Requirement | Status |
|---|:---:|
| 6 JSON schemas | ✅ `schema/versions/v0.2.1/*.json` |
| 10 valid + 8 invalid fixtures | ✅ `schema/fixtures/` |
| Python validator | ✅ `src/llm_wiki/contracts/schema_validator.py` |
| TypeScript validator | ⚡ Uses hardcoded rules, not JSON schema loading |
| Frontmatter parser consolidation | ✅ `src/llm_wiki/core/frontmatter.py` (canonical) |
| Migration registry | ✅ `schema/versions/migrations.json` |
| Migration code | ✅ Stub at `src/llm_wiki/ops/migrate.py` |
| Generated base-schema.md | ✅ `schema/generated/base-schema.md` |
| `schema_version` in generated docs | ❌ Not documented |
| template base-schema marked as derived | ❌ Not marked |
| CI for fixture freshness | ❌ Not in CI |

### Updated paths (v0.3.0 modular)
```
src/llm_wiki/schema_validator.py → src/llm_wiki/contracts/schema_validator.py
src/llm_wiki/frontmatter.py      → src/llm_wiki/core/frontmatter.py
src/llm_wiki/migrate.py          → src/llm_wiki/ops/migrate.py
```

### Technical example — validating a page against schema
```python
from llm_wiki.contracts import validate_page, validate_audit

# Validate page frontmatter
page = {
    "title": "My Page",
    "type": "concept",
    "created": "2026-01-01",
    "updated": "2026-06-01",
    "sources": ["raw/article.md"],
    "tags": ["example"]
}
errors = validate_page(page)
# [] = valid, ["missing field..."] = invalid

# Validate audit entry
audit = {
    "id": "20260101-120000-abc1",
    "target": "wiki/concepts/example.md",
    "target_lines": [10, 15],
    "anchor_before": "...",
    "anchor_text": "...",
    "anchor_after": "...",
    "severity": "suggest",
    "author": "agent",
    "source": "manual",
    "created": "2026-01-01",
    "status": "open"
}
errors = validate_audit(audit)
# [] = valid
```

### Remaining work
1. Add `schema_version` documentation to `schema/generated/base-schema.md`
2. Mark `templates/_shared/base-schema.md` as generated from schema
3. Update TypeScript validator to load JSON schemas (not hardcoded rules)
4. Add CI job for fixture freshness check
5. Add `jsonschema` to pyproject.toml optional-dependencies

---

## PRD 10: LWM_010 — OperationContext, Audit Writer, Event Log

**Status:** ⚡ Partially implemented
**Priority:** MEDIUM

### What it specified (5 phases)
1. OperationContext core (Python + TypeScript)
2. Ingest + Markdown log integration with operation IDs
3. One schema-complete atomic audit writer
4. Cover backup, link-suggest, deep research with OperationContext
5. Reader and diagnostics CLI

### v0.3.0 status
| Requirement | Status |
|---|:---:|
| Python OperationContext | ✅ `src/llm_wiki/operation.py` |
| OperationContext wired into ingest | ✅ |
| OperationContext wired into backup | ✅ |
| OperationContext wired into link-suggest | ✅ |
| OperationContext wired into deep-research | ✅ |
| Atomic audit writer (Python) | ✅ `src/llm_wiki/quality/audit/writer.py` |
| TypeScript OperationContext | ❌ Not created |
| Operation manifest files | ❌ `.llm-wiki/operations/` not created |
| Markdown log → operation ID linking | ❌ Not implemented |
| Reader/diagnostics CLI | ❌ Not implemented |
| OperationContext mandatory | ⚡ Still uses try/except fallback |

### Updated paths (v0.3.0 modular)
```
src/llm_wiki/operation.py    → src/llm_wiki/operation.py (still top-level)
src/llm_wiki/audit_writer.py → src/llm_wiki/quality/audit/writer.py
```

### Technical example — wrapping an operation
```python
from llm_wiki.operation import OperationContext

def main():
    with OperationContext("ingest", wiki_root="/path/to/wiki") as ctx:
        ctx.input("source_path", "/path/to/source.md")
        ctx.input("provider", "openai")

        # ... do the work ...

        ctx.touch("wiki/concepts/new_page.md", action="create")
        ctx.touch("wiki/index.md", action="update")

# After the context exits, an operation manifest is written to:
# .llm-wiki/operations/completed/{operation_id}.json
```

### Remaining work
1. Make OperationContext import mandatory (remove try/except)
2. Create TypeScript OperationContext (`audit-shared/src/ops/context.ts`)
3. Add operation manifest file creation
4. Link Markdown daily logs to operation IDs
5. Add `llm-wiki ops list` reader CLI

---

## PRD 11: LWM_011 — Claim/Event Confidence and Contradiction Model

**Status:** ⚡ Partially implemented
**Priority:** LOW (non-blocking)

### What it specified (5 phases)
1. Schema + fixtures for claims, epistemic events, contradictions
2. Sidecar writer + reader with JSONL storage
3. Page confidence compilation from claim state
4. Ingest candidate claims behind `--claims` flag
5. `claims health`, `claims diff`, `claims redteam` CLI commands

### v0.3.0 status
| Requirement | Status |
|---|:---:|
| Claim, EpistemicEvent, Contradiction models | ✅ `src/llm_wiki/quality/claims/models.py` |
| ClaimsManager with JSONL storage | ✅ `src/llm_wiki/quality/claims/storage.py` |
| `claims health` CLI | ✅ `src/llm_wiki/quality/claims/cli.py` |
| `claims diff` CLI | ✅ `src/llm_wiki/quality/claims/cli.py` |
| Sidecar-free wikis still work | ✅ Graceful fallback |
| Page confidence from claims | ❌ Not implemented |
| Ingest `--claims` flag | ❌ Not implemented |
| `claims redteam` report | ❌ Not implemented |
| Convenience methods (reinforce/challenge) | ❌ Not implemented |

### Updated paths (v0.3.0 modular)
```
src/llm_wiki/claims.py → src/llm_wiki/quality/claims/{models,storage,cli}.py
```

### Technical example — tracking claims
```python
from llm_wiki.quality.claims import Claim, ClaimsManager, has_sidecar

wiki = "/path/to/wiki"

# Create a claim
mgr = ClaimsManager(wiki)
claim = Claim(
    claim_id="claim_transformer_intro",
    statement="Transformer architecture introduced in Vaswani et al. 2017",
    confidence="high",
    status="active",
    sources=["raw/attention_paper.md"],
    pages=["wiki/concepts/transformers.md"],
    claim_type="fact"
)
mgr.create_claim(claim)

# Check health
if has_sidecar(wiki):
    report = mgr.health_report()
    print(f"Active claims: {report['active_claims']}")
    print(f"Open contradictions: {report['open_contradictions']}")
    print(f"Stale claims: {report['stale_claims']}")
```

### Technical example — CLI usage
```bash
# Health report
llm-wiki claims health ~/my-wiki

# Compare two wiki states
llm-wiki claims diff ~/my-wiki /tmp/snapshot
```

### Remaining work
1. Implement page confidence compilation from claim state
2. Add `--claims` flag to ingest pipeline for candidate claim extraction
3. Add `claims redteam` report
4. Add convenience methods: `reinforce_claim()`, `challenge_claim()`, `weaken_claim()`
5. Add sidecar indexes (`by-page.json`, `by-source.json`)

---

## PRD 12: LWM_012 — Release E2E Eval and Fixture Certification

**Status:** ⚡ Partially implemented
**Priority:** HIGH | **Blocks v0.3.0 release:** YES

### What it specified
- Release certification harness (`scripts/release_certify.py`)
- CI matrix with 16 test gates
- 9 fixture certification lanes
- Wheel build/install smoke test
- MCP stdio E2E, graph CLI E2E, deep-research deterministic tests
- `pytest.mark.slow` governance

### v0.3.0 status
| Requirement | Status |
|---|:---:|
| release_certify.py | ✅ Exists |
| CI matrix (3 jobs) | ✅ release-manifest, TypeScript, Python |
| Wheel build/install smoke | ✅ Builds clean, install tested |
| MCP stdio E2E | ✅ Tests exist |
| Graph CLI E2E | ✅ `graph-engine --action build` works |
| pytest.mark.slow registered | ✅ In `pyproject.toml [tool.pytest.ini_options]` |
| Python coverage reporting | ✅ In CI |
| Fixture certification (9 lanes) | ❌ Most lanes empty |
| MCP transcript fixtures | ❌ Directory doesn't exist |
| Deep-research deterministic tests | ❌ Not implemented |
| Docs example contract tests | ❌ Not implemented |

### Technical example — release certification
```bash
# Full release certification
python3 scripts/release_certify.py

# JSON-only output
python3 scripts/release_certify.py --json-only

# Generates: reports/release-certification.json
```

### Technical example — fixture regeneration
```bash
# Regenerate all test fixtures
python3 skill/scripts/regenerate_fixtures.py

# Validate fixtures against schema
python3 skill/scripts/validate_fixtures.py

# Check fixture freshness (CI gate)
python3 -m pytest tests/test_fixtures_fresh.py -q
```

### Remaining work
1. Create MCP transcript fixtures (`tests/fixtures/mcp_transcripts/`)
2. Add offline deep-research tests with mocked sources
3. Expand fixture lanes (web routes, audit entries, clipper pages, Obsidian vaults)
4. Add wheel build/install smoke test to certification
5. Add docs example contract tests

---

## Summary: Implementation Status

| PRD | Domain | Status | Blocking Release? | Remaining Work |
|-----|--------|:---:|:---:|---|
| LWM_001 | Vision & Scope | ⚡ | No | Add tier classification to docs |
| LWM_002 | License & Provenance | ⚡ | **Yes** | Integrate provenance scan into CI |
| LWM_003 | Release Manifest | ✅ | No | Auto-generate MCP docs from registry |
| LWM_004 | CI & Test Gates | ⚡ | No | Test scripts for remaining packages |
| LWM_005 | Python Core | ✅ | No | Complete |
| LWM_006 | Concurrency | ✅ | No | Complete |
| LWM_007 | MCP Registry | ✅ | No | Complete |
| LWM_008 | Graph Engine | ✅ | No | Complete |
| LWM_009 | Schema & Migrations | ⚡ | **Yes** | schema_version docs, TS validator |
| LWM_010 | OperationContext | ⚡ | No | TS mirror, mandatory import |
| LWM_011 | Claims Model | ⚡ | No | Page confidence, ingest integration |
| LWM_012 | Release E2E | ⚡ | **Yes** | Fixture lanes 3-9, deep-research tests |

**Overall:** 4 of 12 complete, 8 partially implemented (with 3 blocking further release cert work).

---

## Cross-Cutting Remaining Gaps

| Gap | PRDs Affected | Priority | Effort |
|-----|:---:|:---:|---:|
| TypeScript OperationContext + ops layer | LWM_010 | MEDIUM | ~2h |
| Provenance scan in CI | LWM_002 | HIGH | ~30min |
| Fixture lanes 3-9 (9 lanes) | LWM_012 | HIGH | ~4h |
| Deep-research deterministic tests | LWM_012 | MEDIUM | ~2h |
| Page confidence from claim state | LWM_011 | LOW | ~1h |
| Ingest `--claims` flag | LWM_011 | LOW | ~1h |
| schema_version in generated docs | LWM_009 | LOW | ~10min |
| TS validator loads JSON schemas | LWM_009 | MEDIUM | ~1h |
| Component tier classification in docs | LWM_001 | LOW | ~15min |
