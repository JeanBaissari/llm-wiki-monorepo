# Design Systems Schema

Extends the shared base schema (`_shared/base-schema.md`) for the design-systems domain. All base page types, frontmatter fields, naming conventions, index format, cross-referencing, and contradiction rules apply unless overridden below.

## Domain Page Types

| Type | Directory | Purpose |
|------|-----------|---------|
| token | design-systems/tokens/ | A design token — color, spacing, typography, shadow, breakpoint |
| component | design-systems/components/ | A UI component — API, states, variants, usage guidance |
| pattern | design-systems/patterns/ | A layout or interaction pattern — usage, examples, best practices |
| guideline | design-systems/guidelines/ | A design or process guideline — accessibility, review, contribution |

## Domain File Naming

- Tokens: `category-name.md` (e.g., `color-primary.md`, `spacing-scale.md`)
- Components: `component-name.md` in kebab-case (e.g., `button.md`, `data-table.md`)
- Patterns: `pattern-name.md` (e.g., `empty-state.md`, `form-layout.md`)
- Guidelines: `kebab-case.md` (e.g., `accessibility-standards.md`, `contribution-process.md`)

## Domain-Specific Frontmatter

All base frontmatter fields (`type`, `title`, `tags`, `related`, `sources`, `created`, `updated`) apply.

### Token pages

```yaml
token_type: string             # color | spacing | typography | shadow | breakpoint | motion | z-index
category: string               # Semantic grouping (e.g., brand, neutral, success)
value: string                  # Primary token value
aliases: [string]              # Equivalent tokens in other naming systems
responsive: boolean            # Whether token has responsive variants
dark_mode: string              # Dark mode equivalent token slug (if applicable)
```

### Component pages (with mandatory status/version)

```yaml
component: string              # Component name
status: string                 # draft | review | stable | deprecated
version: string                # Semver version (e.g., 2.1.0)
props:                         # Component API props
  prop_name:
    type: string               # Prop type
    required: boolean
    default: string            # Default value or null
    description: string
variants: [string]             # Visual variants
states: [string]               # Supported states (hover, active, disabled, error, focus)
accessibility: string          # WCAG compliance level or notes
dependencies: [string]         # Other components this one depends on
```

### Pattern pages

```yaml
pattern: string                # Pattern name
category: string               # layout | navigation | input | feedback | data-display
use_case: [string]             # When to use this pattern
usage: string                  # do | do-not | caution
related_components: [string]   # Components commonly used in this pattern
```

### Guideline pages

```yaml
guideline: string              # Guideline name
category: string               # accessibility | contribution | content | review | process
applies_to: [string]           # What this guideline governs
review_frequency: string       # How often it should be reviewed
owners: [string]               # Responsible team or person
```

## Domain Index

`design-systems/index.md` lists pages grouped by type (tokens, components, patterns, guidelines), plus a "Component status overview" table and a "Design-token reference card".
