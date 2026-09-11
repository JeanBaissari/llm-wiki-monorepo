# docs/ — Documentation Index

Navigation index for every project-level document. Start at the root [`README.md`](../README.md) for the product overview.

## Getting started

| File | Purpose |
|------|---------|
| [`getting-started/quickstart.md`](getting-started/quickstart.md) | Install, scaffold, and run your first wiki — every command with real examples |
| [`architecture/overview.md`](architecture/overview.md) | Why this system exists — design philosophy, core principles, success criteria |

## Reference

| File | Purpose |
|------|---------|
| [`reference/cli.md`](reference/cli.md) | Full CLI reference — all 27 commands with flags and examples |
| [`reference/mcp-tools.md`](reference/mcp-tools.md) | All 15 MCP tools with schemas and usage examples |
| [`reference/file-map.md`](reference/file-map.md) | Complete file tree with descriptions for every file in the monorepo |
| [`reference/tuning.md`](reference/tuning.md) | Tuning config surface — every constant, precedence, and emit boundary |

## Operations

| File | Purpose |
|------|---------|
| [`operations/index.md`](operations/index.md) | Operational runbooks index |
| [`operations/hybrid-default-search.md`](operations/hybrid-default-search.md) | Hybrid-default search migration note (v0.5.0, LWM_032 / ADR-0020) |
| [`operations/security-and-boundaries.md`](operations/security-and-boundaries.md) | Per-wiki auth/visibility boundary — filesystem + git permissions, no network surface |

## Release & legal

| File | Purpose |
|------|---------|
| [`release/changelog.md`](release/changelog.md) | Canonical version history — features, changes, breaking changes |
| [`release/versioning.md`](release/versioning.md) | Semantic versioning policy and release process |
| [`legal/notices.md`](legal/notices.md) | Third-party license notices |
| [`legal/provenance.md`](legal/provenance.md) | Third-party provenance ledger — origin and license of derived code |

## Decisions & planning

| File | Purpose |
|------|---------|
| [`adr/index.md`](adr/index.md) | Architecture Decision Records index — ADRs 0001–0035 (0015 and 0023 reserved) |
| [`adr/decision-register.md`](adr/decision-register.md) | One-line decision register — status and owning PRD per ADR |
| [`prd/archive/v0.3.1-batch-plan.md`](prd/archive/v0.3.1-batch-plan.md) | Archived v0.3.1 batch execution plan (historical) |
| [`contributing.md`](contributing.md) | Contribution workflow — project structure, tests, code style, PR process |

## Root-level docs

These files stay at the repo root for tooling and convention requirements:

| File | Purpose |
|------|---------|
| [`../README.md`](../README.md) | PyPI project description and GitHub landing page |
| [`../USAGE.md`](../USAGE.md) | Complete user & developer overview — install/wiring, command inventory, worked examples |
| [`../AGENTS.md`](../AGENTS.md) | AI agent tooling convention — architecture, conventions, build/test commands |
| [`../CHANGELOG.md`](../CHANGELOG.md) | GitHub-visibility pointer to the canonical [`release/changelog.md`](release/changelog.md) |
| [`../CONTRIBUTING.md`](../CONTRIBUTING.md) | Root-level entry point for contribution guidelines |
| [`../SECURITY.md`](../SECURITY.md) | Supported versions, private vulnerability reporting, trust boundary summary |
| [`../CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md) | Contributor Covenant v2.1 — community standards and enforcement |
