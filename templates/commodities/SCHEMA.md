# Commodities Domain Schema

Extends the base schema with commodities-specific page types,
directories, and frontmatter conventions.

## Inherited Base Types

All base page types from `_shared/base-schema.md` are available:

| Type | Directory | Purpose |
|------|-----------|---------|
| `entity` | `wiki/entities/` | Named things — exchanges, regulators, producers |
| `concept` | `wiki/concepts/` | Ideas — contango, backwardation, basis risk, seasonality |
| `source` | `wiki/sources/` | Reports from EIA, S&P Global Platts, exchange publications |
| `comparison` | `wiki/comparisons/` | Side-by-side analysis of related commodities or markets |
| `synthesis` | `wiki/synthesis/` | Cross-cutting summaries and conclusions |
| `overview` | `wiki/` | High-level project summary |

## Extra Directories

| Directory | Purpose |
|-----------|---------|
| `wiki/commodities/` | Individual commodity pages |
| `wiki/market-reports/` | Structured daily/weekly/monthly market analysis |
| `wiki/correlations/` | Documented cross-commodity or macro correlation |
| `wiki/supply-chain/` | Logistics, producers, consumers, bottlenecks |

## Domain Page Types

| Type | Directory | Purpose | Frontmatter Fields |
|------|-----------|---------|--------------------|
| `commodity` | `wiki/commodities/` | A specific commodity (crude oil, copper, corn) | `category: metals \| energy \| agriculture`, `unit`, `exchange`, `ticker`, `contract_size`, `pricing_benchmark` |
| `market_report` | `wiki/market-reports/` | Structured daily/weekly market analysis | `commodity`, `report_type: daily \| weekly \| monthly \| quarterly`, `date`, `author`, `sources: []` |
| `correlation` | `wiki/correlations/` | Cross-commodity or macro correlation | `pair: []`, `correlation_coefficient`, `window`, `macro_factor` |
| `supply_chain` | `wiki/supply-chain/` | Logistics and bottleneck analysis | `commodity`, `region`, `stage: production \| transport \| processing \| consumption`, `risk_factors: []` |

## Naming Conventions

- **Commodities:** `commodity-name.md` (e.g., `crude-oil.md`, `copper.md`, `corn.md`)
- **Market reports:** `commodity-YYYY-MM-DD-report-type.md` (e.g., `crude-oil-2024-06-01-weekly.md`)
- **Correlations:** `commodity-a-vs-commodity-b.md` (e.g., `gold-vs-usd.md`)
- **Supply chains:** `commodity-region.md` (e.g., `lithium-chile.md`)

## Frontmatter Template

```yaml
---
type: commodity | market_report | correlation | supply_chain
title: Human-readable title
tags: []
related: []
sources: []
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

### Commodity-specific
```yaml
type: commodity
category: metals | energy | agriculture
unit: bbl | tonne | bushel | oz | MMBtu
exchange: "CME"
ticker: "CL"
contract_size: "1,000 bbl"
pricing_benchmark: "Brent"
```

### Market Report-specific
```yaml
type: market_report
commodity: crude-oil
report_type: weekly
date: 2024-06-01
author: ""
sources:
  - source-slug
```

### Correlation-specific
```yaml
type: correlation
pair:
  - gold
  - usd-index
correlation_coefficient: -0.45
window: "90-day rolling"
macro_factor: "interest rates"
```

### Supply Chain-specific
```yaml
type: supply_chain
commodity: lithium
region: "South America"
stage: production
risk_factors:
  - "water scarcity"
  - "regulatory changes"
```

## Conventions

1. Every commodity page should record the primary exchange, contract specifications, and pricing benchmark.
2. Market reports should include a forward-looking assessment and note any data revisions from prior reports.
3. Correlation pages should document the observation period, data sources, and whether the correlation is stable or regime-dependent.
4. Supply chain pages should map the full value chain from production to consumption and flag known bottlenecks.
5. When a price benchmark changes (e.g., Brent switching from Dated to Cash BFOE), create a new commodity page or note the transition clearly.
