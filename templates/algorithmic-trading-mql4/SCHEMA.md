# Algorithmic Trading (MQL4/5) Domain Schema

Extends the base schema with MQL4/MQL5 algorithmic trading-specific page types,
directories, and frontmatter conventions.

## Inherited Base Types

All base page types from `_shared/base-schema.md` are available:

| Type | Directory | Purpose |
|------|-----------|---------|
| `entity` | `wiki/entities/` | Named things — EAs, indicators, libraries, tools |
| `concept` | `wiki/concepts/` | Ideas, techniques, phenomena, frameworks |
| `source` | `wiki/sources/` | Papers, articles, talks, books, forum posts |
| `comparison` | `wiki/comparisons/` | Side-by-side analysis of related entities |
| `synthesis` | `wiki/synthesis/` | Cross-cutting summaries and conclusions |
| `overview` | `wiki/` | High-level project summary (one per project) |

## Extra Directories

| Directory | Purpose |
|-----------|---------|
| `wiki/architecture/` | Module dependency graphs, include hierarchy, MCP topology |
| `wiki/decisions/` | Architecture Decision Records (ADRs) |
| `wiki/graphs/` | Graph engine artifacts + reports |

## Domain Page Types

| Type | Directory | Purpose | Frontmatter Fields |
|------|-----------|---------|--------------------|
| `entity` | `wiki/entities/` | An EA, custom indicator, library, script, or tool | `language: mql4 \| mql5 \| python`, `namespace: string`, `status: active \| deprecated \| archived \| experimental`, `dependencies: []`, `version: string` |
| `concept` | `wiki/concepts/` | A trading concept — FVG, swing detection, regime filter, state machine | `confidence: high \| medium \| low`, `contested: true \| false`, `implemented_by: []` |
| `architecture` | `wiki/architecture/` | Module structure, dependency graph, include hierarchy | `type: dependency_graph \| include_tree \| data_flow \| mcp_topology`, `language: mql4 \| mql5 \| python \| hybrid` |
| `decision` | `wiki/decisions/` | An Architecture Decision Record (ADR) | `status: proposed \| accepted \| deprecated \| superseded`, `date: YYYY-MM-DD`, `deciders: []`, `supersedes: []` |
| `source` | `wiki/sources/` | Papers, articles, forum posts, documentation | `authors: []`, `year: YYYY`, `url: ""`, `venue: ""` |

## Naming Conventions

- **Entities:** `kebab-case.md` matching the EA/indicator name (e.g., `xau-swinger.md`, `sakura-sniper.md`)
- **Concepts:** `kebab-case.md` — short descriptive noun phrase (e.g., `fvg-detection.md`, `swing-quality-scoring.md`)
- **Architecture:** `topic-name.md` (e.g., `module-dependency-graph.md`, `mcp-server-topology.md`)
- **Decisions (ADRs):** `YYYY-MM-DD-short-title.md` (e.g., `2025-01-15-pulse-event-sourcing.md`)
- **Comparisons:** `entity-a-vs-entity-b.md`

## Frontmatter Templates

### Base (all pages)

```yaml
---
type: entity | concept | architecture | decision | source | comparison | synthesis | overview
title: Human-readable title
tags: []
related: []
sources: []
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

### Entity-specific (EAs, indicators, tools)

```yaml
---
type: entity
language: mql4 | mql5 | python
namespace: "core" | "trading" | "risk" | "indicators" | "tools"
status: active | deprecated | archived | experimental
version: "3.16"
dependencies:
  - "entity-slug"
---
```

### Concept-specific

```yaml
---
type: concept
confidence: high | medium | low
contested: false
implemented_by:
  - "entity-slug-1"
  - "entity-slug-2"
---
```

### Architecture-specific

```yaml
---
type: architecture
architecture_type: dependency_graph | include_tree | data_flow | mcp_topology
language: mql4 | mql5 | python | hybrid
---
```

### Decision-specific (ADR)

```yaml
---
type: decision
status: proposed | accepted | deprecated | superseded
date: 2025-01-15
deciders:
  - "Name"
supersedes:
  - "decision-slug"
---
```

## Conventions

1. **Every EA gets an entity page.** Document its entry logic, exit logic, risk management,
   indicator dependencies, and timeframe preferences.

2. **Every concept gets a concept page.** Define it, explain the math/formula, list EAs
   that implement it, and note any contested aspects with `contested: true` and a note.

3. **Entity pages use `sources:` frontmatter** to link to their source code.
   Format: `"raw/src/experts/<strategy>/<ea_name>.mq5"`.

4. **Architecture pages are created** when the include hierarchy exceeds 5 files,
   or when a module dependency graph is built.

5. **ADRs follow the standard format:**
   - Context & Problem Statement
   - Decision Drivers
   - Considered Options
   - Decision Outcome — "We will … because …"
   - Consequences

6. **Cross-referencing:** Every page should link to related entities and concepts via
   `related:` frontmatter AND `[[wikilinks]]` in the body text.

7. **Version tracking:** When an EA version changes, update the entity page and create
   a changelog entry in `log.md`. Do NOT overwrite old backtest results — versioning
   is key for reproducibility.
