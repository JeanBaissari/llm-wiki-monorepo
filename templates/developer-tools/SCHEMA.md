# Developer Tools Schema

Extends `_shared/base-schema.md`.

## Domain-Specific Page Types

| Type | Directory | Purpose |
|------|-----------|---------|
| tool | wiki/tools/ | A specific developer tool or utility |
| workflow | wiki/workflows/ | A documented development workflow or setup |
| benchmark | wiki/benchmarks/ | Performance comparison or feature benchmark |
| integration | wiki/integrations/ | How two or more tools work together |

## Domain-Specific Frontmatter

### tool
```yaml
type: tool
category: editor | linter | ci_cd | debugger | profiler | package_manager | build_tool | testing | monitoring | security | database | other
language: ""           # primary language ecosystem
platform: cli | gui | web | plugin | library
license: proprietary | open_source | freeware
homepage: ""           # URL
repo: ""               # GitHub/GitLab URL
status: active | archived | deprecated | experimental
```

### workflow
```yaml
type: workflow
primary_tool: ""       # slug of the main tool
difficulty: beginner | intermediate | advanced
time_estimate: ""      # e.g., "~30 minutes"
prerequisites: []      # slugs of required tools or concepts
steps: 0               # number of steps
```

### benchmark
```yaml
type: benchmark
benchmark_type: performance | scalability | feature_matrix | usability
tools_compared: []     # slugs of tools being compared
metric: ""             # primary metric (e.g., "build time", "memory usage")
environment: ""        # test environment description
result_summary: ""     # brief result
```

### integration
```yaml
type: integration
tools: []              # slugs of the tools involved
direction: bidirectional | a_to_b | b_to_a
setup_complexity: simple | moderate | complex
version_compatibility: ""  # e.g., "v2.x - v3.x"
```

## Extra Directories

See `extra-dirs.json`.
