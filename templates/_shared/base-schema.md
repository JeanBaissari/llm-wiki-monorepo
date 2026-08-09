<!-- GENERATED FROM schema/versions/v0.2.1/page.schema.json — DO NOT EDIT -->
<!-- Generated from schema/versions/v0.2.1/page.schema.json. DO NOT EDIT. -->

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
| community-summary | wiki/summaries/ | Generated per-community / global summary page (LWM_030) — opt-in, machine-generated, never hand-edited |

## Base Frontmatter

All pages must include YAML frontmatter:

```yaml
---
type: entity | concept | source | comparison | synthesis | overview | community-summary
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

## Generated Page Types

### `community-summary` (generated — do not hand-edit)

Written by `llm-wiki summarize-communities` (opt-in, LWM_030/ADR-0025). Pages are
**generated artifacts**: edits are overwritten on regeneration — corrections go
in the underlying member pages, not here.

```yaml
---
title: Human-readable theme title (LLM-written)
type: community-summary
community: 0                  # community id within its level; -1 for the global page
level: 0                      # int (hierarchy level) or "global" for global-summary.md
members: ["Page Title", ...]  # member page titles
key_entities: [Entity, ...]   # LLM key entities, filtered to real member entities
member_sha: <sha256-prefix>   # deterministic member-set key — filenames are keyed on this only
generated_by: summarize-communities
updated: YYYY-MM-DD
tags: []
sources: []
---
```

Conventions:

- Filenames: `wiki/summaries/L{level}-{member_sha}.md` per community; the root
  is `wiki/summaries/global-summary.md` (`level: global`).
- Body: the LLM summary prose, then a `## Members` section with one
  `[[Page Title]]` wikilink per member.
- `member_sha` is the stable key: the same member set always maps to the same
  file (AD-12), and stale pages whose member set left the partition are deleted.
- Summary pages are excluded from community membership and from the graph's
  wikilink structure — they never feed back into the partition they describe.

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
