# Base Schema — Generated from Machine-Readable Contract

> This file is auto-generated from `schema/versions/v0.2.1/page.schema.json`.
> Do not edit by hand. Edit the JSON Schema and regenerate.

## Schema Version

schema_version: v0.2.1

## Required Frontmatter

All wiki pages must include these fields in YAML frontmatter:

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | Schema version hash (first 8 hex chars of SHA256 of canonical schema) |
| `title` | string | Human-readable page title |
| `type` | enum | One of: entity, concept, source, comparison, synthesis, overview |
| `created` | date | YYYY-MM-DD creation date |
| `updated` | date | YYYY-MM-DD last-updated date |
| `sources` | string[] | Source file paths or URLs |
| `tags` | string[] | Freeform tags |

## Optional Quality Fields

| Field | Type | Description |
|-------|------|-------------|
| `confidence` | enum | high, medium, low |
| `contested` | boolean | Whether content is contested |
| `contradictions` | string[] | Slugs of contradicting pages |

## Source Page Fields

| Field | Type | Description |
|-------|------|-------------|
| `authors` | string[] | Author names |
| `year` | string | Publication year (YYYY) |
| `url` | string | External URL |
| `venue` | string | Publication venue |

## Naming Conventions

- Files: `kebab-case.md`
- Entities: match official name
- Concepts: descriptive noun phrases
- Sources: `author-year-slug.md`

## Cross-referencing

- Use `[[page-slug]]` syntax for wikilinks
- Every entity and concept should appear in `wiki/index.md`
- Pages link to sources via `sources:` frontmatter

---

*Generated from `schema/versions/v0.2.1/` — DO NOT EDIT.*
