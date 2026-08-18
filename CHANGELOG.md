# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.3] - 2026-08-18

### Fixed
- **opencode provider deadlock** — replaced broken filesystem IPC (prompt.json/.ready/response.json polling) with HTTP API calls to `localhost:4096`. Eliminates the deadlock that made `llm-wiki ingest --llm opencode` unusable inside opencode sessions.
- **MCP server dist/** — rebuilt from source (was missing `main.js`, stale since Jul 5).
- **graph-engine dist/** — rebuilt from source (43 days stale, golden test was failing).
- **Test failures** — fixed 3 opencode tests that assumed no running server; now mock the HTTP layer correctly.

### Changed
- **Batch mode file extensions** — `--batch` now processes `.mq5`, `.mq4`, `.mqh`, `.py`, `.ts`, `.js` in addition to `.md`, `.txt`, `.json`, `.yaml`, `.yml`. New `--ext` flag allows custom extensions.
- **opencode provider initialization** — `LLM_WIKI_AGENT_MODE=1` now works as a session_id fallback without requiring `HERMES_SESSION_ID` or similar markers.

### Added
- `OPENCODE_URL` environment variable for configurable opencode server URL (default: `http://localhost:4096`).
- ADR-0034: HTTP API provider design decision (supersedes ADR-0009).

### Deprecated
- ADR-0009 pipe-based IPC mechanism (superseded by ADR-0034).

## [0.6.2] - 2026-07-05

### Changed
- Previous release (see git log for details).
