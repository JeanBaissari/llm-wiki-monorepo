# Migration Guide — v1 → v2

This guide walks through migrating an existing wiki from the **v1 format** (the original llm-wiki skill) to the **v2 format** (Lewis's merged format used by the current skill).

## Overview: what changed

| Area | v1 (old) | v2 (new) |
|------|----------|----------|
| Operation log | Single `log.md` file | `log/YYYYMMDD.md` folder — one file per day |
| Wiki pages | Flat or ad-hoc structure | Structured under `wiki/` with `concepts/`, `entities/`, `summaries/`, `comparisons/` subdirectories |
| Schema | `SCHEMA.md` | `CLAUDE.md` (also read as `AGENTS.md` by some tools) |
| Audit directory | Not present | `audit/` and `audit/resolved/` |
| Output queries | Ad-hoc | `outputs/queries/` directory |
| Frontmatter | Basic (title, type, dates, sources, tags) | Adds optional `confidence`, `contested`, `contradictions` fields |
| Comparison pages | Not a standard type | `wiki/comparisons/` + `type: comparison` |

## Directory structure changes

| Old (v1) | New (v2) |
|----------|----------|
| `log.md` | `log/YYYYMMDD.md` (one file per day) |
| `<topic>.md` (at root) | `wiki/concepts/<topic>.md` |
| `entities/<entity>.md` | `wiki/entities/<entity>.md` |
| `summaries/<slug>.md` | `wiki/summaries/<slug>.md` |
| `SCHEMA.md` | `CLAUDE.md` |
| *(not present)* | `audit/` and `audit/resolved/` |
| *(not present)* | `outputs/queries/` |

## Step-by-step migration

### 1. Convert the operation log

Run the migration script to split a single `log.md` into the `log/` folder:

```bash
python3 scripts/migrate_log.py <wiki-root>
```

This parses `log.md`, groups entries by date, creates `log/YYYYMMDD.md` files, and removes the old `log.md`.

### 2. Move wiki pages under `wiki/`

If any concept or entity pages live at the root of your wiki, move them into the appropriate subdirectory:

```bash
mkdir -p <wiki-root>/wiki/concepts <wiki-root>/wiki/entities
mv <wiki-root>/concepts/ <wiki-root>/wiki/concepts/   # if concepts/ exists at root
mv <wiki-root>/entities/ <wiki-root>/wiki/entities/   # if entities/ exists at root
mv <wiki-root>/summaries/ <wiki-root>/wiki/summaries/ # if summaries/ exists at root
```

Update `wiki/index.md` to reflect the new paths.

### 3. Rename SCHEMA.md → CLAUDE.md

```bash
# If only SCHEMA.md exists:
mv <wiki-root>/SCHEMA.md <wiki-root>/CLAUDE.md

# If both exist, merge content:
# - Keep CLAUDE.md's structure as the base
# - Port over any scope, conventions, or open questions from SCHEMA.md that CLAUDE.md is missing
# - Remove SCHEMA.md
```

The new schema document follows the template in `references/schema-guide.md`. After renaming, ensure `CLAUDE.md` has the standard sections: Scope, Naming conventions, Frontmatter, Current articles, Open research questions, Research gaps, Audit backlog, Notes for the LLM.

### 4. Create audit directories

```bash
mkdir -p <wiki-root>/audit <wiki-root>/audit/resolved
```

Add a `.gitkeep` to each if you want them tracked:

```bash
touch <wiki-root>/audit/.gitkeep <wiki-root>/audit/resolved/.gitkeep
```

### 5. Create outputs directories

```bash
mkdir -p <wiki-root>/outputs/queries
```

### 6. Run the linter

```bash
python3 scripts/lint_wiki.py <wiki-root>
```

This identifies:
- Dead or broken wikilinks
- Missing frontmatter fields
- Stray files outside the expected structure
- Invalid file naming
- Orphan pages with no incoming links

Fix each category of issue before proceeding.

## Frontmatter changes

Add these fields to existing pages where appropriate:

```yaml
# Optional quality fields:
confidence: medium      # high | medium | low — how well-supported the claims are
contested: false        # true if the page has unresolved contradictions
# contradictions: [other-page-slug]  # uncomment and list conflicting pages
```

- Set `confidence: high` only for well-supported claims across multiple sources.
- Set `contested: true` when the page has contradictions flagged in other pages.
- Populate `contradictions` as a list when `contested` is `true`.

These fields are optional; add them as you edit pages rather than bulk-editing everything.

## Non-standard page types

If your v1 wiki has custom directories like `architecture/`, `quick_guides/`, `changelogs/`, etc., map them to the v2 standard types:

| Custom type | Suggested mapping |
|-------------|-------------------|
| `architecture/` | `wiki/concepts/` — architecture descriptions are concept pages |
| `quick_guides/` | `wiki/concepts/` with a `guide` tag, or `wiki/entities/` if tool-specific |
| `changelogs/` | Move into `log/` as daily entries, or into `wiki/concepts/` as a "version history" page |
| `references/` | `wiki/concepts/` with a `reference` tag |
| `tutorials/` | `wiki/concepts/` with a `tutorial` tag |
| `faq/` | `wiki/concepts/` with an `faq` tag, or a dedicated folder-split under concepts |

General rule: if it's about a **thing or idea** → `wiki/concepts/`. If it's about a **named entity** → `wiki/entities/`. If it's a **source summary** → `wiki/summaries/`. If it's a **comparison** → `wiki/comparisons/`.

After moving, update wikilinks across the wiki to point to the new locations.

## Post-migration: first `compile`

After all structural changes are complete, run a `compile` operation to restructure the wiki:

```bash
compile <wiki-root>
```

This will:
1. Rebuild `wiki/index.md` from the current page inventory.
2. Validate all wikilinks resolve to existing pages.
3. Check frontmatter consistency.
4. Flag any remaining issues.

After `compile` succeeds, run a final lint:

```bash
python3 scripts/lint_wiki.py <wiki-root>
```

When lint passes cleanly, the migration is complete. The wiki is now ready for normal operations (`ingest`, `query`, `audit`, etc.) using the v2 skill.
