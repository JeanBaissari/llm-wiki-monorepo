# Developer Tools Domain Schema

Extends the base schema with developer-tools-specific page types,
directories, and frontmatter conventions.

## Inherited Base Types

All base page types from `_shared/base-schema.md` are available:

| Type | Directory | Purpose |
|------|-----------|---------|
| `entity` | `wiki/entities/` | Named things — tool authors, organizations, plugins |
| `concept` | `wiki/concepts/` | Ideas — continuous integration, static analysis, monorepo management |
| `source` | `wiki/sources/` | Documentation, blog posts, conference talks, RFCs |
| `comparison` | `wiki/comparisons/` | Side-by-side analysis of related tools or platforms |
| `synthesis` | `wiki/synthesis/` | Cross-cutting summaries and conclusions |
| `overview` | `wiki/` | High-level project summary |

## Extra Directories

| Directory | Purpose |
|-----------|---------|
| `wiki/tools/` | Individual developer tool or utility records |
| `wiki/workflows/` | Documented development workflows and setups |
| `wiki/benchmarks/` | Performance comparisons and feature benchmarks |
| `wiki/integrations/` | How two or more tools work together |

## Domain Page Types

| Type | Directory | Purpose | Frontmatter Fields |
|------|-----------|---------|--------------------|
| `tool` | `wiki/tools/` | A specific developer tool or utility | `category: editor \| linter \| ci_cd \| debugger \| profiler \| package_manager \| build_tool \| testing \| monitoring \| security \| database \| other`, `language`, `platform: cli \| gui \| web \| plugin \| library`, `license: proprietary \| open_source \| freeware`, `homepage`, `repo`, `status: active \| archived \| deprecated \| experimental` |
| `workflow` | `wiki/workflows/` | A documented development workflow or setup | `primary_tool`, `difficulty: beginner \| intermediate \| advanced`, `time_estimate`, `prerequisites: []`, `steps` |
| `benchmark` | `wiki/benchmarks/` | Performance comparison or feature benchmark | `benchmark_type: performance \| scalability \| feature_matrix \| usability`, `tools_compared: []`, `metric`, `environment`, `result_summary` |
| `integration` | `wiki/integrations/` | How two or more tools work together | `tools: []`, `direction: bidirectional \| a_to_b \| b_to_a`, `setup_complexity: simple \| moderate \| complex`, `version_compatibility` |

## Naming Conventions

- **Tools:** `tool-name.md` (e.g., `eslint.md`, `docker.md`, `vscode.md`)
- **Workflows:** `verb-tool-description.md` (e.g., `setup-eslint-prettier.md`)
- **Benchmarks:** `tool-a-vs-tool-b-metric.md` (e.g., `webpack-vs-vite-build-time.md`)
- **Integrations:** `tool-a-with-tool-b.md` (e.g., `eslint-with-prettier.md`)

## Frontmatter Template

```yaml
---
type: tool | workflow | benchmark | integration
title: Human-readable title
tags: []
related: []
sources: []
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

### Tool-specific
```yaml
type: tool
category: linter
language: "JavaScript"
platform: cli | plugin
license: open_source
homepage: "https://eslint.org"
repo: "https://github.com/eslint/eslint"
status: active
```

### Workflow-specific
```yaml
type: workflow
primary_tool: docker
difficulty: intermediate
time_estimate: "~30 minutes"
prerequisites:
  - docker
  - docker-compose
steps: 5
```

### Benchmark-specific
```yaml
type: benchmark
benchmark_type: performance
tools_compared:
  - webpack
  - vite
metric: "build time (seconds)"
environment: "MacBook Pro M1, 16GB RAM"
result_summary: "Vite 4x faster than Webpack for cold start"
```

### Integration-specific
```yaml
type: integration
tools:
  - eslint
  - prettier
direction: bidirectional
setup_complexity: simple
version_compatibility: "ESLint 8.x - 9.x, Prettier 3.x"
```

## Conventions

1. Every tool page should document installation, basic usage, and how it integrates into a broader development workflow.
2. Workflow pages should include prerequisites, step-by-step instructions, and troubleshooting tips.
3. Benchmark pages should document the test environment, methodology, and any caveats that affect reproducibility.
4. Integration pages should note version compatibility ranges and any known breaking changes.
5. When a tool is deprecated or archived, update the `status` field and link to its replacement if one exists.
