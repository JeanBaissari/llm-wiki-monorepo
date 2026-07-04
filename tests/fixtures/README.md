# Test Fixtures — Lifecycle Management

Test fixture wikis live under `tests/fixtures/wikis/`. They provide
deterministic, pre-built wikis for the test suite so tests don't
depend on a live LLM or real data.

## Quick Reference

| Fixture    | Purpose | Pages | Sources |
|------------|---------|-------|---------|
| `empty/`   | Bare scaffold — tests that only need directory structure | 0 | 0 |
| `minimal/` | Small wiki: 5 pages, 2 sources, 10 wikilinks | 5 | 2 |
| `stale/`   | Deliberately broken — tests lint_wiki.py detection | ~10 | 2 |
| `populated/` | Large wiki: 50+ pages, complex link graph | 54 | 3 |

## The Rot Problem

Fixture wikis are committed to git. When the wiki schema changes
(new frontmatter fields, template updates, lint rules), the
committed fixtures don't automatically update. Tests pass against
stale fixtures while the real system breaks.

**The fix**: Fixtures declare which schema version they were built
against (`.schema_version` file). CI validates that the schema
hasn't changed since fixtures were last regenerated.

## Schema Version

The schema version is the first 8 characters of SHA256 of
`templates/_shared/base-schema.md`. Any change to wiki conventions
(that file) changes the version hash.

```
$ python3 skill/scripts/validate_fixtures.py --schema-version
8857edf6
```

Each fixture wiki has a `.schema_version` file containing this hash.

## When to Regenerate

Run regeneration after:
- Modifying `templates/_shared/base-schema.md`
- Adding/changing required frontmatter fields
- Updating `lint_wiki.py` with new passes
- Modifying seed files in `tests/fixtures/seeds/`

## How to Regenerate

```bash
# Regenerate all fixtures
python3 skill/scripts/regenerate_fixtures.py

# Regenerate a single fixture
python3 skill/scripts/regenerate_fixtures.py --fixture stale

# Validate after regeneration
python3 skill/scripts/validate_fixtures.py
```

## How to Add a New Fixture

1. Create `tests/fixtures/seeds/<name>.yaml`:
   ```yaml
   template: codebase
   wiki_name: "My Test Wiki"
   description: "What this fixture tests"

   pages:
     - path: wiki/concepts/my_page.md
       title: "My Page"
       type: concept
       tags: [test]
       updated: "2026-06-15"
       content: |
         # My Page
         Content here.

   sources:
     - path: raw/articles/source.md
       content: |
         # Source content
   ```

2. Add the fixture name to `FIXTURE_NAMES` in `skill/scripts/validate_fixtures.py`

3. Regenerate: `python3 skill/scripts/regenerate_fixtures.py --fixture <name>`

## How to Update Expected Lint Failures

When `lint_wiki.py` adds/removes/changes lint rules, the stale
fixture's expected failures must be updated:

1. Edit `tests/fixtures/seeds/stale.yaml` → `expected_lint_failures`
2. Regenerate: `python3 skill/scripts/regenerate_fixtures.py --fixture stale`
3. Validate: `python3 skill/scripts/validate_fixtures.py`

## CI Integration

The `validate-fixtures` CI job runs on every PR and push to main.
It fails if:
- Any fixture's `.schema_version` doesn't match current
- Any page is missing required frontmatter fields
- Any wikilink in non-stale fixtures doesn't resolve
- lint_wiki.py doesn't detect expected issues in the stale fixture

## Determinism

Regeneration is deterministic: same seed + same schema version →
identical output. Safe to run twice. Use `git diff` after
regeneration to verify only expected changes.

## Seeds vs Generated Files

- **Seeds** (`tests/fixtures/seeds/*.yaml`) are the **source of truth**.
  They're version-controlled, reviewed, and declarative.
- **Generated wikis** (`tests/fixtures/wikis/*/`) are the **output**.
  They're committed to git for CI convenience, but should never be
  edited by hand. Edit the seeds, then regenerate.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `FIXTURE STALE: ... Run: python3 skill/scripts/regenerate_fixtures.py` | Schema changed. Regenerate. |
| `missing 'title' in frontmatter` | Seed missing required field. Edit seed, regenerate. |
| `[[Target]] is a dead link` | Wikilink target doesn't exist. Add the page or fix the link. |
| `expected lint rule 'X' not triggered` | lint_wiki.py changed. Update stale.yaml's expected_lint_failures. |
