# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.4] - 2026-09-11

### Release integrity

The release-integrity patch: licensing-clean graph code, packaging that actually
installs the product, and release gates that can fail. No new user-facing
surface — every change fixes shipped behavior or the truth of the release
contract.

### Removed

- **graphify / code-analysis surface removed (ADR-0035)** — the
  `@sentropic/graphify` integration and its promotion are gone; `graph-bridge`
  is retained as an adapter with no default consumer. Local-model promotion
  (Ollama, model downloads, torch) is also out of the default story; `[ner]`
  stays a legacy opt-in that degrades to the regex extractor.

### Changed

- **graph-engine relevance/insights clean-room rewrite** — `relevance.ts` and
  `insights.ts` rewritten under MIT with no GPL-derived code or provenance;
  public contracts and the golden/parity tests are unchanged.
- **install.sh installs the Python package** — `pip install -e .` is now a
  first-class install step, so the `llm-wiki` console script exists after
  `bash install.sh`.
- **Wheels ship the 20 templates** — `src/llm_wiki/templates/**` is package
  data; `llm-wiki scaffold --template <name>` works from an installed wheel.
- **Race-free locking + verifiable atomic backups** — per-page lock
  acquisition/stealing is race-free; backups verify integrity and restore
  atomically.
- **Config/search/provider error semantics** — fail-closed config parsing,
  explicit search-mode errors, and provider-registry error contracts.
- **Packaging/CI truth fixes** — `release-manifest.json` points at the real
  registries (`mcp-server/src/registry.ts`; MCP 15 / CLI 27 / templates 20 /
  scripts 26) and the real workspace versions; `release_manifest.py
  --json-only` exits nonzero on failure; the certifier gates the PyPI publish
  and includes the ask-eval gate; CI drops the `audit-shared` zero-test
  exemption, adds a slow-benchmark lane, and enforces a Python coverage floor.
- **Docs truth check expanded** to the live user-facing docs, failing on stale
  surface counts.

### Version

- Bumped to **0.6.4** across `pyproject.toml`, `llm_wiki.__version__`,
  `package.json`, `package-lock.json`, and `release-manifest.json`
  (canonical source: `pyproject.toml:project.version`).

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
