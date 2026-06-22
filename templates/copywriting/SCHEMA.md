# Copywriting Schema

Extends the shared base schema (`_shared/base-schema.md`) for the copywriting domain. All base page types, frontmatter fields, naming conventions, index format, cross-referencing, and contradiction rules apply unless overridden below.

## Domain Page Types

| Type | Directory | Purpose |
|------|-----------|---------|
| copy_example | copywriting/copy/ | An example of effective copy — ad, landing page, email, social post |
| framework | copywriting/frameworks/ | A messaging or voice framework — tone guidelines, brand pillars, messaging hierarchy |
| persona | copywriting/personas/ | An audience persona — demographics, goals, pain points, messaging hooks |
| campaign | copywriting/campaigns/ | A campaign — channel mix, goals, copy variants, performance data |

## Domain File Naming

- Copy examples: `channel-purpose-slug.md` (e.g., `email-welcome-series.md`, `social-twitter-launch.md`)
- Frameworks: `kebab-case.md` (e.g., `brand-tone-voice.md`, `messaging-pyramid.md`)
- Personas: `short-descriptor.md` (e.g., `technical-decision-maker.md`, `budget-conscious-smb.md`)
- Campaigns: `campaign-name.md` (e.g., `q3-product-launch.md`, `holiday-2024.md`)

## Domain-Specific Frontmatter

All base frontmatter fields (`type`, `title`, `tags`, `related`, `sources`, `created`, `updated`) apply.

### Copy example pages

```yaml
channel: string                # Channel (email, social, landing_page, ad, sms)
medium: string                 # Sub-channel or format (newsletter, instagram_feed, google_search)
brand: string                  # Brand or product name
audience: [persona-slug]       # Target persona references
variant: string                # Variant label if A/B tested
metrics:                       # Performance metrics (optional)
  impressions: int
  clicks: int
  conversions: int
  ctr: float
```

### Framework pages

```yaml
brand: string                  # Brand this framework belongs to
dimensions: [string]           # Framework dimensions (e.g., [formal-casual, authoritative-friendly])
pillars: [string]              # Brand messaging pillars
```

### Persona pages

```yaml
demographics:                  # Demographic profile
  age_range: string
  role: string
  industry: string
goals: [string]                # Primary goals
pain_points: [string]          # Key pain points
channels: [string]             # Preferred communication channels
```

### Campaign pages

```yaml
campaign: string               # Campaign name
status: string                 # draft | active | completed | archived
goals: [string]                # Campaign objectives
channels: [string]             # Channels used
start_date: YYYY-MM-DD
end_date: YYYY-MM-DD
budget: string                 # Budget summary
kpis:                          # Key results (optional)
  metric_name: value
```

## Domain Index

`copywriting/index.md` lists pages grouped by type (copy examples, frameworks, personas, campaigns), plus a "Brands" cross-reference section.
