# VERSIONING.md — Semantic Versioning Policy

## Current Version

The llm-wiki-monorepo Python package is at **0.6.5** (PyPI: `baissarienterprises-llm-wiki`).

| Milestone | Description |
|-----------|-------------|
| v0.6.5    | Patch — `llm-wiki embed` degrades cleanly when the model is unavailable at runtime; provenance scanner ignores wiki/build content; CI green end-to-end |
| v0.6.4    | Release integrity — graphify/code-analysis surface removed (ADR-0035), clean-room MIT relevance/insights, install.sh installs the Python package, wheels ship the 20 templates, race-free locking + verifiable backups, truthful release gates |
| v0.6.3    | opencode HTTP API provider, batch-mode file extensions (`--ext`), MCP/graph-engine dist rebuilds |
| v0.6.2    | Documentation accuracy — install.sh builds graph-bridge/web-viewer/obsidian-audit, .hermes/ gitignore, scaffold.py dict-format extra-dirs.json handling |
| v0.6.1    | Documentation cleanup — post-v0.6.0 repo-state alignment (USAGE.md, AGENTS.md, SKILL.md, file-map, quickstart); no shipped-surface code change |
| v0.6.0    | Epistemic & Surface — `setup` (one-command client wiring), `demo` wiki, `ask` (grounded QA), `contradictions` + evidence confidence, web-viewer derived overlay + Sigma.js + JSON Canvas/JSON-LD exports, recommended-extras profile, gold-set curation loop |
| v0.5.0    | Graph Precision — entity resolution, Leiden, typed/derived edges, community summaries, tuning config, hybrid search default |
| v0.4.0    | Semantic Core — pluggable embeddings, in-file vector store, hybrid search (opt-in), semantic link suggestion, eval harness |
| v0.3.4    | Stabilization line — modularization, health checks, benchmarks |
| v0.2.1    | Release integrity — manifest, docs truth, workspace gates, CI matrix |
| v0.2.0    | Foundation — LLM SDK, concurrency, graph optimization, search, link suggestion |
| v0.1.1    | Templates shipped inside package for pip-installed users |
| v0.1.0    | Initial PyPI release — 11 CLI commands, 15-pass lint, graph engine, MCP server, 20 templates |

## Version Scheme

This repo follows **Semantic Versioning** (`MAJOR.MINOR.PATCH`). The canonical version source is `pyproject.toml` (`project.version`); `package.json`/`package-lock.json`, `llm_wiki.__version__`, and `release-manifest.json` mirror it. This is recorded machine-readably in `release-manifest.json` as `release.canonical_version_source`.

Given a version number `MAJOR.MINOR.PATCH`, increment the:

1. **MAJOR** version when you make incompatible API or structural changes
2. **MINOR** version when you add functionality in a backward-compatible manner
3. **PATCH** version when you make backward-compatible bug fixes

## MAJOR Bumps — Breaking Changes

A MAJOR version increment signals that consumers must take action to update. Examples include:

- **Wiki directory structure changes** — e.g., removing or renaming the `wiki/` subdirectory
- **Frontmatter format changes** — removing or renaming required YAML frontmatter fields (`title`, `type`, `created`, `updated`, `sources`, `tags`)
- **MCP API breaking changes** — removing tools, changing JSON-RPC message format, altering tool input/output schemas
- **Template schema breaking changes** — structural changes to `src/llm_wiki/templates/_shared/base-schema.md` that all templates extend
- **Dropping support for existing scripts/CLI flags** — removing a script or breaking flag semantics
- **Python version requirement bumps** — raising minimum Python version (e.g., 3.10 → 3.12)
- **Node.js version requirement bumps** — raising minimum Node version (e.g., 18 → 20)

## MINOR Bumps — New Functionality

A MINOR version increment adds capability without breaking existing consumers. Examples include:

- **New operations** — new Python scripts (e.g., a new `skill/scripts/` entry), new MCP tools
- **New templates** — adding domain templates under `src/llm_wiki/templates/`
- **New CLI flags** — optional, non-breaking flag additions to existing scripts
- **New wiki features** — optional frontmatter fields, new conventions or conventions that don't invalidate existing files
- **New documentation** — reference guides, README updates, QUICKGUIDE additions
- **New packages** — adding a workspace to the monorepo (e.g., a new integration)
- **Deprecation warnings** — marking features as deprecated without removing them

## PATCH Bumps — Fixes

A PATCH version increment makes backward-compatible fixes. Examples include:

- **Bug fixes** — correcting incorrect behavior while preserving the API contract
- **Documentation updates** — fixing typos, clarifying instructions, updating examples
- **Performance improvements** — faster execution without changing observable behavior
- **Test additions** — new or improved tests for existing functionality
- **Code refactoring** — restructuring code with no behavioral change
- **Dependency updates** — updating dependencies to newer patch versions within compatible ranges
- **Build infrastructure** — CI/CD config changes, tooling improvements

## Pre-release Tags

Pre-release versions may be used for work-in-progress that has not yet reached the stability of a full release.

Format: `MAJOR.MINOR.PATCH-<tag>.<number>`

| Tag | Meaning |
|-----|---------|
| `alpha` | Early development, unstable, may be incomplete |
| `beta` | Feature-complete, testing in progress |
| `rc`   | Release candidate — final testing before release |

Examples:

- `3.1.0-alpha.1` — First alpha of the 3.1.0 release
- `3.1.0-beta.2` — Second beta of the 3.1.0 release
- `3.1.0-rc.1` — First release candidate for 3.1.0
- `4.0.0-alpha.1` — First alpha of the next MAJOR version

Pre-release versions have lower precedence than a normal version. `3.1.0-rc.1` sorts before `3.1.0`.

## Release Process

Releases are tag-driven and automated. Pushing a `v*` tag triggers
[`.github/workflows/release.yml`](../../.github/workflows/release.yml), which
builds, certifies, publishes to PyPI via OIDC, and creates the GitHub Release.

1. **Ensure CI passes** — All checks on the target commit must be green (lint, typecheck, integration tests).
2. **Update `docs/release/changelog.md`** — The canonical changelog. Add the new version entry with Breaking Changes, New Features, and Bug Fixes.
3. **Update version** — Bump `pyproject.toml` (`project.version`), then sync the mirrors: `src/llm_wiki/__init__.py`, `package.json`/`package-lock.json`, and `release-manifest.json` (`python3 scripts/release_manifest.py` verifies them).
4. **Commit** — Commit with the repository's actual convention: `release: vX.Y.Z` (e.g., `release: v0.6.5`), optionally with an em-dash summary of the release (`release: v0.6.5 — embed degradation fix`).
5. **Tag and push the tag**:

   ```bash
   git tag v<version>
   git push origin --tags
   ```

6. **Automated pipeline** (on the `v*` tag push):
   - **`build`** — installs the package, smoke-tests the CLI/import, builds the wheel + sdist, installs the wheel in a clean venv, and verifies the wheel version matches the tag.
   - **`certify`** — runs `python3 scripts/release_certify.py` (release manifest, docs truth check, Python test suite, TypeScript gates, eval gates). The publish job is gated on this job (`needs: [build, certify]`).
   - **`publish`** — uploads to PyPI with trusted OIDC publishing (`pypa/gh-action-pypi-publish`, no API tokens) and PEP 740 digital attestations, then creates the GitHub Release with generated release notes and the `dist/*` artifacts attached.

   Release notes are generated from the tag by the workflow — no manual
   GitHub Release step is required. If the tag must be re-released, delete and
   re-push the tag after the fix (never force-push `main`).

## Backward Compatibility Guarantee

Within a **MAJOR** version:

- Wiki files created by an older MINOR/PATCH must work with newer versions without modification
- Scripts invoked with the same flags must produce the same (or superseded) behavior
- MCP tools must accept the same input schemas and return compatible output schemas
- Templates must produce valid wikis that are compatible with all tools across the MAJOR version

**Exception**: Security fixes may break backward compatibility with prior notice. Such changes must be documented in the release notes with clear migration instructions.
