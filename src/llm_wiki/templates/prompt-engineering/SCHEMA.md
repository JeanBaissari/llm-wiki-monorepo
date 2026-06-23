# Prompt Engineering Schema

Extends the shared base schema (`_shared/base-schema.md`) for the prompt-engineering domain. All base page types, frontmatter fields, naming conventions, index format, cross-referencing, and contradiction rules apply unless overridden below.

## Domain Page Types

| Type | Directory | Purpose |
|------|-----------|---------|
| technique | prompt-engineering/techniques/ | A named prompting strategy — how it works, when to use it, variants |
| evaluation | prompt-engineering/evaluations/ | A benchmark or evaluation — metrics, dataset, protocol, results |
| template | prompt-engineering/templates/ | A reusable prompt template with parameters and usage notes |
| provider | prompt-engineering/providers/ | An LLM provider — model family, API, pricing, rate limits |

## Domain File Naming

- Techniques: `kebab-case.md` (e.g., `chain-of-thought.md`, `few-shot-coT.md`)
- Evaluations: `dataset-slug-metric.md` (e.g., `mmlu-accuracy.md`)
- Templates: `kebab-case.md` prefixed with task area (e.g., `code-review.yml`, `summary-bullet.yml`)
- Providers: `lowercase-name.md` (e.g., `openai.md`, `anthropic.md`)

## Domain-Specific Frontmatter

All base frontmatter fields (`type`, `title`, `tags`, `related`, `sources`, `created`, `updated`) apply.

### Technique pages

```yaml
variants: [variant-name]       # Known variants of this technique
best_for: [task-type]          # Tasks this technique excels at
providers: [provider-name]     # Providers tested with
requires: [other-technique]    # Prerequisite techniques
```

### Evaluation pages

```yaml
metric: string                 # Primary metric (accuracy, F1, etc.)
dataset: string                # Dataset name
providers_tested: [provider]   # Which providers were evaluated
result: string                 # Summary result value
```

### Template pages

```yaml
task: string                   # Task category (summarization, classification, etc.)
version: string                # Semver version of this template
provider: string               # Target provider (if provider-specific)
parameters: [param-name]       # Template parameters
```

### Provider pages

```yaml
provider: string               # Provider name
models: [model-name]           # Available models
pricing: string                # Pricing summary or link to pricing page
context_window: int            # Max context tokens
rate_limits: string            # Rate limit summary
```

## Domain Index

`prompt-engineering/index.md` lists pages grouped by type (techniques, evaluations, templates, providers), plus a "Comparison tables" section linking to comparisons.
