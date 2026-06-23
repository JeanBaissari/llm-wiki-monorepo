# Finance Domain Schema

Extends the base schema with finance-specific page types, directories,
and frontmatter conventions.

## Extra Directories

| Directory | Purpose |
|-----------|---------|
| `wiki/markets/` | Financial market reference pages |
| `wiki/instruments/` | Tradable instruments (stocks, bonds, options, futures, crypto) |
| `wiki/strategies/` | Trading and investment strategies |
| `wiki/reports/` | Periodic performance and analytic reports |

## Domain Page Types

| Type | Directory | Purpose | Frontmatter Fields |
|------|-----------|---------|--------------------|
| `market` | `wiki/markets/` | A financial market or exchange | `region`, `asset_class`, `open_hours`, `currency`, `settlement` |
| `instrument` | `wiki/instruments/` | A tradable financial instrument | `type: equity \| bond \| option \| future \| etf \| crypto \| forex`, `ticker`, `exchange`, `currency`, `sector` |
| `strategy` | `wiki/strategies/` | A trading or investment strategy | `style: discretionary \| systematic \| hybrid`, `timeframe: scalping \| intraday \| swing \| position`, `markets: []`, `instruments: []` |
| `report` | `wiki/reports/` | A periodic performance or analytic report | `period_start: YYYY-MM-DD`, `period_end: YYYY-MM-DD`, `strategy: []`, `metrics: { ... }` |

## Naming Conventions

- **Markets:** `market-name.md` (e.g., `nyse.md`, `binance.md`)
- **Instruments:** `ticker-symbol.md` (e.g., `aapl.md`, `btc-usd.md`)
- **Strategies:** `strategy-name.md` (e.g., `momentum-mean-reversion.md`)
- **Reports:** `YYYY-MM-strategy-name.md` (e.g., `2024-06-momentum-report.md`)

## Frontmatter Template

```yaml
---
type: market | instrument | strategy | report
title: Human-readable title
tags: []
related: []
sources: []
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

### Market-specific
```yaml
type: market
region: "US"
asset_class: "equity"
open_hours: "09:30-16:00 ET"
currency: "USD"
settlement: "T+2"
```

### Instrument-specific
```yaml
type: instrument
ticker: "AAPL"
exchange: "NASDAQ"
currency: "USD"
sector: "Technology"
```

### Strategy-specific
```yaml
type: strategy
style: discretionary | systematic | hybrid
timeframe: scalping | intraday | swing | position
markets:
  - market-slug
instruments:
  - instrument-slug
```

### Report-specific
```yaml
type: report
period_start: YYYY-MM-DD
period_end: YYYY-MM-DD
strategy:
  - strategy-slug
metrics:
  total_return_pct: 12.5
  sharpe_ratio: 1.8
  max_drawdown_pct: -8.3
```

## Conventions

1. Instrument pages should link to their primary market.
2. Strategy pages should document entry/exit rules, risk management,
   and position sizing logic.
3. Reports should include summary statistics and link to the strategies
   they evaluate.
4. Market pages should describe trading hours, holidays, and
   settlement conventions.
