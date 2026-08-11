# Redis Internals Knowledge Base

> Schema document — read at the start of every session together with `wiki/index.md`.

## Scope

What this wiki covers:
- Redis internal architecture: data structures, event loop, scripting, persistence.

What this wiki deliberately excludes:
- API reference documentation and operator runbooks — this is an internal-mechanics wiki.

## Operations

This wiki follows the llm-wiki skill's operations: `compile`, `ingest`, `query`, `lint`, `audit`, `research`, `insights`.
Every operation appends an entry to `log/YYYYMMDD.md`.

## Naming conventions

- **Concept pages** (`wiki/concepts/`): Title Case noun phrases; filenames kebab-case.
- **Entity pages** (`wiki/entities/`): Proper names; filenames kebab-case.
- **Summary pages** (`wiki/summaries/`): kebab-case source slug.

All pages require YAML frontmatter: `title`, `type`, `created`, `updated`, `sources`, `tags`.

Wikilinks are case-sensitive and use the filename stem (`[[sds]]`) or a relative path
with alias (`[[entities/redis|Redis]]`) so every link resolves.

## Current articles

- Entities: Redis, Salvatore Sanfilippo, Redis Cluster.
- Concepts: Simple Dynamic Strings, Event Loop, Lua Scripting.
- Summaries: Redis Internals Overview, Redis Persistence.

## Notes for the LLM

- Language: en
- Tone: neutral, technical
- Depth: survey-level internal mechanics
