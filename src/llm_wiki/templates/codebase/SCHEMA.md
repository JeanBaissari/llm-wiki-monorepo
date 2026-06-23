# Codebase Domain Schema

Extends the base schema with codebase-specific page types, directories,
and frontmatter conventions.

## Extra Directories

| Directory | Purpose |
|-----------|---------|
| `wiki/architecture/` | System architecture overviews and diagrams |
| `wiki/modules/` | Individual module/component documentation |
| `wiki/apis/` | API surface documentation |
| `wiki/decisions/` | Architecture Decision Records (ADRs) |

## Domain Page Types

| Type | Directory | Purpose | Frontmatter Fields |
|------|-----------|---------|--------------------|
| `module` | `wiki/modules/` | A software module, library, or component | `language`, `framework`, `status: stable \| active \| deprecated \| experimental` |
| `api` | `wiki/apis/` | A public API surface (internal or external) | `protocol: rest \| grpc \| graphql \| websocket \| rpc`, `version`, `authentication`, `rate_limiting` |
| `decision` | `wiki/decisions/` | An Architecture Decision Record (ADR) | `status: proposed \| accepted \| deprecated \| superseded`, `deciders: []`, `date: YYYY-MM-DD`, `supersedes: []` |

## Naming Conventions

- **Modules:** `module-name.md` matching the module's package directory (e.g., `auth-service.md`)
- **APIs:** `api-endpoint-name.md` (e.g., `user-api-v1.md`)
- **Decisions (ADRs):** `YYYY-MM-DD-short-title.md` (e.g., `2024-03-15-postgres-vs-mongodb.md`)

## Frontmatter Template

```yaml
---
type: module | api | decision
title: Human-readable title
tags: []
related: []
sources: []
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

### Module-specific
```yaml
type: module
language: "Python"
framework: "FastAPI"
status: stable | active | deprecated | experimental
```

### API-specific
```yaml
type: api
protocol: rest | grpc | graphql | websocket | rpc
version: "v1"
authentication: "JWT"
rate_limiting: "100 req/min"
```

### Decision-specific (ADR)
```yaml
type: decision
status: proposed | accepted | deprecated | superseded
deciders:
  - "Name Surname"
  - "Name Surname"
date: YYYY-MM-DD
supersedes:
  - decision-slug
```

## Conventions

1. Every ADR must follow the standard ADR format:
   - **Context & Problem Statement**
   - **Decision Drivers**
   - **Considered Options**
   - **Decision Outcome** — "We will … because …"
   - **Consequences**
2. An ADR with `status: superseded` must point to its replacement in `supersedes:`.
3. Module pages should list their key APIs and link to the relevant
   `api` pages.
4. Each module page should document dependencies and link to related
   modules.
