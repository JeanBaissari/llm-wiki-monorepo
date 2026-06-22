# Research Domain Schema

Extends the base schema with research-specific page types, directories,
and frontmatter conventions.

## Extra Directories

| Directory | Purpose |
|-----------|---------|
| `wiki/methodology/` | Research methods, experimental protocols, frameworks |
| `wiki/findings/` | Specific results, observations, data points |
| `wiki/thesis/` | Overarching theses, hypotheses, research questions |

## Domain Page Types

| Type | Directory | Purpose | Frontmatter Fields |
|------|-----------|---------|--------------------|
| `thesis` | `wiki/thesis/` | A guiding hypothesis or research question | `status: proposed \| active \| challenged \| abandoned \| confirmed`, `principal_investigator`, `start_date` |
| `methodology` | `wiki/methodology/` | A research method, experimental design, or protocol | `field`, `validation: theoretical \| empirical \| both`, `limitations: []` |
| `finding` | `wiki/findings/` | A specific result, observation, or data point | `thesis: []`, `methodology: []`, `confidence: high \| medium \| low`, `significance: \| effect_size \| p_value` |

## Naming Conventions

- **Theses:** `kebab-case-thesis-name.md` (e.g., `attention-is-all-you-need-thesis.md`)
- **Methodologies:** `descriptive-method-name.md` (e.g., `few-shot-prompting.md`)
- **Findings:** `brief-result-description.md` (e.g., `transformer-parallelization-speedup.md`)

## Frontmatter Template

```yaml
---
type: thesis | methodology | finding
title: Human-readable title
tags: []
related: []
sources: []
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

### Thesis-specific
```yaml
type: thesis
status: proposed | active | challenged | abandoned | confirmed
principal_investigator: "Name"
start_date: YYYY-MM-DD
```

### Methodology-specific
```yaml
type: methodology
field: "sub-discipline"
validation: theoretical | empirical | both
limitations:
  - "limitation 1"
  - "limitation 2"
```

### Finding-specific
```yaml
type: finding
thesis:
  - thesis-slug
methodology:
  - methodology-slug
confidence: high | medium | low
significance:
  effect_size: 0.XX
  p_value: 0.XX
```

## Conventions

1. Every finding must link to at least one thesis and one methodology.
2. Conflicting findings under the same thesis should be noted with
   `contested: true` and cross-referenced via `contradictions:`.
3. Methodology pages should document limitations explicitly.
4. Thesis pages should be updated when new findings shift confidence.
