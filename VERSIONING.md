# VERSIONING.md — Semantic Versioning Policy

## Current Version

The llm-wiki-monorepo Python package is at **0.1.1** (PyPI: `baissarienterprises-llm-wiki`).

| Milestone | Description |
|-----------|-------------|
| v0.1.0    | Initial PyPI release — 11 CLI commands, 15-pass lint, graph engine, MCP server, 19 templates |
| v0.1.1    | Templates shipped inside package for pip-installed users |

## Version Scheme

This repo follows **Semantic Versioning** (`MAJOR.MINOR.PATCH`). The version is declared in `package.json` at the repository root.

Given a version number `MAJOR.MINOR.PATCH`, increment the:

1. **MAJOR** version when you make incompatible API or structural changes
2. **MINOR** version when you add functionality in a backward-compatible manner
3. **PATCH** version when you make backward-compatible bug fixes

## MAJOR Bumps — Breaking Changes

A MAJOR version increment signals that consumers must take action to update. Examples include:

- **Wiki directory structure changes** — e.g., removing or renaming the `wiki/` subdirectory
- **Frontmatter format changes** — removing or renaming required YAML frontmatter fields (`title`, `type`, `created`, `updated`, `sources`, `tags`)
- **MCP API breaking changes** — removing tools, changing JSON-RPC message format, altering tool input/output schemas
- **Template schema breaking changes** — structural changes to `templates/_shared/base-schema.md` that all templates extend
- **Dropping support for existing scripts/CLI flags** — removing a script or breaking flag semantics
- **Python version requirement bumps** — raising minimum Python version (e.g., 3.10 → 3.12)
- **Node.js version requirement bumps** — raising minimum Node version (e.g., 18 → 20)

## MINOR Bumps — New Functionality

A MINOR version increment adds capability without breaking existing consumers. Examples include:

- **New operations** — new Python scripts (e.g., a new `skill/scripts/` entry), new MCP tools
- **New templates** — adding domain templates under `templates/`
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

1. **Ensure CI passes** — All checks on the target commit must be green (lint, typecheck, integration tests).
2. **Update CHANGELOG.md** — If a CHANGELOG exists, add the new version entry. If one does not exist, create it with entries for Breaking Changes, New Features, and Bug Fixes.
3. **Update version** — Bump the version in `package.json` at the repository root.
4. **Commit** — Commit with message format: `Release v<version>` (e.g., `Release v3.1.0`).
5. **Tag in git**:

   ```bash
   git tag v<version>
   git push origin --tags
   ```

6. **Release notes** — On GitHub, create a release with notes summarizing:
   - **Breaking Changes** — What changed and migration steps
   - **New Features** — What was added
   - **Bug Fixes** — What was fixed
   - **Full changelog** — Link to the commit range

## Backward Compatibility Guarantee

Within a **MAJOR** version:

- Wiki files created by an older MINOR/PATCH must work with newer versions without modification
- Scripts invoked with the same flags must produce the same (or superseded) behavior
- MCP tools must accept the same input schemas and return compatible output schemas
- Templates must produce valid wikis that are compatible with all tools across the MAJOR version

**Exception**: Security fixes may break backward compatibility with prior notice. Such changes must be documented in the release notes with clear migration instructions.
