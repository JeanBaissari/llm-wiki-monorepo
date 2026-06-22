# Commodities Schema

Extends `_shared/base-schema.md`.

## Domain-Specific Page Types

| Type | Directory | Purpose |
|------|-----------|---------|
| commodity | wiki/commodities/ | A specific commodity (crude oil, copper, corn) |
| market_report | wiki/market-reports/ | Structured daily/weekly market analysis |
| correlation | wiki/correlations/ | Documented cross-commodity or macro correlation |
| supply_chain | wiki/supply-chain/ | Logistics, producers, consumers, bottlenecks |

## Domain-Specific Frontmatter

### commodity
```yaml
type: commodity
category: metals | energy | agriculture
unit: bbl | tonne | bushel | oz | MMBtu
exchange: ""           # primary exchange (e.g., "CME", "LME")
ticker: ""             # futures ticker (e.g., "CL", "HG")
contract_size: ""      # e.g., "1,000 bbl"
pricing_benchmark: ""  # e.g., "Brent", "WTI", "LME Copper Grade A"
```

### market_report
```yaml
type: market_report
commodity: ""          # slug of the commodity page
report_type: daily | weekly | monthly | quarterly
date: YYYY-MM-DD
author: ""
sources: []            # slugs of source pages
```

### correlation
```yaml
type: correlation
pair: ["commodity-a", "commodity-b"]
correlation_coefficient: 0.00  # optional
window: ""             # e.g., "90-day rolling"
macro_factor: ""       # e.g., "USD index", "interest rates"
```

### supply_chain
```yaml
type: supply_chain
commodity: ""          # slug of the commodity
region: ""             # geographic focus
stage: production | transport | processing | consumption
risk_factors: []       # list of risks
```

## Extra Directories

See `extra-dirs.json`.
