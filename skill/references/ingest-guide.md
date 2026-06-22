# Two-Step Chain-of-Thought Ingest Guide

The two-step ingest pipeline produces higher-quality wiki pages by separating analysis from generation. Instead of asking one prompt to both understand a source AND write wiki pages, it splits the work into two specialized stages.

## Why two steps

Single-pass ingest often produces:
- Shallow entity extraction (misses relationships)
- Generic summaries that don't connect to existing wiki content
- No contradiction detection (unaware of what the wiki already says)
- Hallucinated page content for complex sources

Two-step fixes this:
1. Stage 1 (Analysis): LLM focuses entirely on understanding — extracts entities, claims, relationships, contradictions
2. Stage 2 (Generation): LLM takes the analysis as context — writes wiki pages grounded in extracted facts, generates review items for issues

## Architecture

```
Source document
     │
     ▼
┌─────────────────┐
│  Stage 1        │  LLM analyzes source
│  (Analysis)     │  → Entities, concepts, claims
│                 │  → Relationships between entities
│                 │  → Contradictions with existing wiki
│                 │  → Key takeaways
└────────┬────────┘
         │ analysis (structured text)
         ▼
┌─────────────────┐
│  Stage 2        │  LLM generates wiki content
│  (Generation)   │  → FILE blocks for wiki pages
│                 │  → REVIEW blocks for issues
│                 │  → Uses analysis as context only
└────────┬────────┘
         │
         ▼
    Wiki pages + Review items
```

## Stage 1: Analysis Prompt

The LLM receives:
1. CLAUDE.md (wiki schema + conventions)
2. PURPOSE.md (project purpose + scope)
3. wiki/index.md (current page inventory)
4. The source document

Output: Structured analysis covering:
- Key entities (people, tools, organizations, concepts) with descriptions
- Core claims and findings from the source
- Relationships between entities (how entity A relates to entity B)
- Contradictions with existing wiki content (if any — requires checking index.md for related pages)
- Key takeaways (what matters most for this domain)

The analysis is NOT written to disk — it's passed directly to Stage 2 as context.

## Stage 2: Generation Prompt

The LLM receives:
1. CLAUDE.md + PURPOSE.md (conventions)
2. The Stage 1 analysis (context only — must not be echoed)
3. The source identity and source context
4. Instructions to output ONLY structured blocks

Output format:
```
---FILE: wiki/entities/entity-name.md
---
title: Entity Name
type: entity
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: [source-slug]
tags: [tag1, tag2]
---

# Entity Name

<page content>

---FILE: wiki/concepts/concept-name.md
---
...

---REVIEW: missing-page
target: wiki/entities/missing-entity.md
title: Missing Entity
description: This entity is referenced but has no page.
suggestion: Create from source X.
```

## Review items from ingest

The generation stage can produce review items for:
- **missing-page**: An entity/concept mentioned in the source that should have a page but doesn't
- **duplicate-page**: Two existing pages that appear to cover the same topic
- **contradiction**: The source claims something that contradicts an existing wiki page
- **suggestion**: General improvement suggestion for existing content

These review items feed into the bidirectional review system (`mcp-server/src/review.ts`) for human resolution.

## When to use two-step vs single-pass

| Source type | Use | Why |
|---|---|---|
| Academic paper | Two-step | Dense, many entities and claims |
| Technical documentation | Two-step | Complex relationships, needs careful extraction |
| Web article (news) | Single-pass | Simple structure, fewer entities |
| Personal note | Single-pass | Already structured by the human |
| Video transcript | Two-step | Messy structure, needs analysis to organize |
| Book chapter | Two-step | Many characters/themes/plot threads |
| PRD / spec document | Two-step | Domain-critical, can't afford errors |

## Handling long sources

For sources exceeding the LLM's context window:
1. Split into chunks (12K-60K tokens per chunk)
2. Run Stage 1 on each chunk independently
3. Run a consolidation pass: merge all chunk analyses into one coherent analysis
4. Run Stage 2 on the consolidated analysis + first chunk of source context

This preserves thorough analysis while staying within context limits.

## Caching

The Stage 1 analysis is cached per source (keyed by SHA256 of the source content). On re-ingest of an unchanged source, Stage 1 is skipped and the cached analysis is used for Stage 2. This makes re-ingest fast and cheap.

## CLI usage

```bash
python3 skill/scripts/ingest.py <wiki-root> <source-path> [--llm <provider>]
```

Options:
- `--llm <provider>`: Override the default LLM provider
- `--force`: Skip cache, re-run both stages
- `--batch`: Process multiple sources in batch mode (one analysis pass across all)
