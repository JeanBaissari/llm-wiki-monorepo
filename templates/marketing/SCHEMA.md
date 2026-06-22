# Marketing Schema

Extends the shared base schema (`_shared/base-schema.md`) for the marketing domain. All base page types, frontmatter fields, naming conventions, index format, cross-referencing, and contradiction rules apply unless overridden below.

## Domain Page Types

| Type | Directory | Purpose |
|------|-----------|---------|
| channel | marketing/channels/ | A marketing channel — strategy, metrics, best practices |
| campaign | marketing/campaigns/ | A campaign — plan, execution, results, learnings |
| analytic | marketing/analytics/ | An analytics report, dashboard spec, or metric definition |
| competitor | marketing/competitors/ | A competitor — positioning, strengths, weaknesses, market data |

## Domain File Naming

- Channels: `channel-name.md` (e.g., `google-ads.md`, `linkedin-organic.md`)
- Campaigns: `campaign-name.md` (e.g., `q1-2025-product-launch.md`)
- Analytics: `metric-dash-name.md` (e.g., `mrr-dashboard.md`, `cac-by-channel.md`)
- Competitors: `competitor-name.md` (e.g., `competitor-acme-corp.md`)

## Domain-Specific Frontmatter

All base frontmatter fields (`type`, `title`, `tags`, `related`, `sources`, `created`, `updated`) apply.

### Channel pages

```yaml
channel: string                # Channel name
category: string               # paid | organic | email | social | referral | direct | partner
status: string                 # active | paused | deprecated
metrics:                       # Typical metrics for this channel
  primary: [metric-name]
  secondary: [metric-name]
best_for: [string]             # Goals this channel suits best
budget_share: string           # Typical budget allocation
```

### Campaign pages

```yaml
campaign: string               # Campaign name
status: string                 # planning | active | paused | completed | archived
channels: [string]             # Channels used
budget: string                 # Total budget
start_date: YYYY-MM-DD
end_date: YYYY-MM-DD
target_audience: [persona]     # Target personas
kpis:                          # Target and actual metrics
  metric_name:
    target: value
    actual: value
learnings: [string]            # Key takeaways
```

### Analytic pages

```yaml
metric: string                 # Primary metric
dashboard: string              # Dashboard name or source
frequency: string              # daily | weekly | monthly | quarterly
owners: [string]               # Who owns this analysis
data_sources: [string]         # Source systems (GA4, HubSpot, etc.)
```

### Competitor pages

```yaml
competitor: string             # Company name
market: string                 # Market segment
stage: string                  # startup | growth | mature
strengths: [string]
weaknesses: [string]
products: [string]             # Key products
pricing_model: string          # freemium | subscription | enterprise
market_share: string           # Estimated share text
```

## Domain Index

`marketing/index.md` lists pages grouped by type (channels, campaigns, analytics, competitors), plus a "Channel mix" summary table.
