# Changelog

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
- 19 domain templates (audited and consistent)
- CI/CD pipeline (GitHub Actions) with full integration tests
- One-command install script (`install.sh`)
- VERSIONING.md — semantic versioning policy
