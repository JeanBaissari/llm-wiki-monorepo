# docs/ — Project Documentation

This directory organizes project-level documentation into a taxonomy.

## Directory structure

| Directory | Purpose |
|-----------|---------|
| `architecture/` | System design, purpose, and architectural decisions |
| `reference/` | Complete file maps and reference indexes |
| `release/` | Versioning policy and release process |
| `legal/` | Legal notices |
| `getting-started/` | Quick start and onboarding guides |
| `adr/` | Architecture Decision Records |

## Key files

| File | Description |
|------|-------------|
| `architecture/overview.md` | Why this system exists — core principles, success criteria |
| `reference/file-map.md` | Complete file tree with descriptions for every file in the monorepo |
| `release/versioning.md` | Semantic versioning policy and release process |
| `legal/notices.md` | Third-party license notices |
| `adr/` | Architecture Decision Records (individual ADRs as `.md` files) |

## Root-level docs (not moved)

These files must stay at the repo root for tooling requirements:

| File | Why at root |
|------|------------|
| `README.md` | PyPI project description, GitHub landing page |
| `AGENTS.md` | AI agent tooling convention (used by Claude, Codex, etc.) |
