# Audit Entry Fixtures

Deterministic audit entries for testing audit-shared schema, anchor resolution,
and serialization across web viewer and Obsidian plugin.

## Structure

```
audit_entries/
  valid_anchored.md          — Valid audit with anchor context
  unanchored_review.md       — Review-style audit without anchor
  duplicate_anchor.md        — Duplicate anchor ambiguity
  invalid_range.md           — Anchor with invalid line range
```

## Usage

Copy fixture files into a temp wiki's `audit/` directory before testing
audit list, create, and resolve operations.

## Schema Version

Audit entries follow the shared audit schema defined in `audit-shared/src/schema.ts`.
When the schema changes, regenerate these fixtures.
