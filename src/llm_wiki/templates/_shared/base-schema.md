# Shared Template Primitives

These are the base building blocks that all domain templates extend.
Templates reference these via `{{include: _shared/base-*.md}}` or copy them at scaffold time.

## Base Page Types

| Type | Directory | Purpose |
|------|-----------|---------|
| entity | wiki/entities/ | Named things — people, tools, organizations, papers, datasets |
| concept | wiki/concepts/ | Ideas, techniques, phenomena, frameworks |
| source | wiki/sources/ | Papers, articles, talks, books, blog posts |
| comparison | wiki/comparisons/ | Side-by-side analysis of related entities |
| synthesis | wiki/synthesis/ | Cross-cutting summaries and conclusions |
| overview | wiki/ | High-level project summary (one per project) |

## Base Frontmatter

All pages must include YAML frontmatter:

```yaml
---
type: entity | concept | source | comparison | synthesis | overview
title: Human-readable title
tags: []
related: []
sources: []
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

Optional quality fields:
```yaml
confidence: high | medium | low
contested: true | false
contradictions: [other-page-slug]
```

Source pages additionally include:
```yaml
authors: []
year: YYYY
url: ""
venue: ""
```

## Base Naming Conventions

- Files: `kebab-case.md`
- Entities: match official name (e.g., `openai.md`, `gpt-4.md`)
- Concepts: descriptive noun phrases (e.g., `chain-of-thought.md`)
- Sources: `author-year-slug.md` (e.g., `wei-2022-cot.md`)
- Comparisons: `entity-a-vs-entity-b.md`

## Base Index Format

`wiki/index.md` lists all pages grouped by type:

```markdown
# Index — <Topic>

## Concepts
- [[concepts/page-slug]] — one-line description

## Entities
- [[entities/page-slug]] — one-line description

## Comparisons
- [[comparisons/page-slug]] — one-line description

## Summaries (chronological)
- YYYY-MM-DD — [[summaries/source-slug]] — source title

## Open Questions
- Q: ...
```

## Base Cross-referencing

- Use `[[page-slug]]` syntax to link between wiki pages
- Every entity and concept should appear in `wiki/index.md`
- Pages link to their sources via `sources:` frontmatter
- Synthesis pages cite all contributing sources

## Base Contradiction Handling

When sources contradict each other:
1. Note the contradiction in the relevant concept or entity page
2. State both claims explicitly with source attribution
3. Add to the page's "Open questions" section
4. Add to CLAUDE.md "Open research questions"
5. Do NOT silently pick one — contradictions are valuable signal
