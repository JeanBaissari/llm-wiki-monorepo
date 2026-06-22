# Algorithmic Trading Domain Schema

Extends the base schema with algorithmic trading-specific page types,
directories, and frontmatter conventions.

## Inherited Base Types

All base page types from `_shared/base-schema.md` are available:

| Type | Directory | Purpose |
|------|-----------|---------|
| `entity` | `wiki/entities/` | Named things — people, tools, organizations, papers, datasets |
| `concept` | `wiki/concepts/` | Ideas, techniques, phenomena, frameworks |
| `source` | `wiki/sources/` | Papers, articles, talks, books |
| `comparison` | `wiki/comparisons/` | Side-by-side analysis of related entities |
| `synthesis` | `wiki/synthesis/` | Cross-cutting summaries and conclusions |
| `overview` | `wiki/` | High-level project summary |

## Extra Directories

| Directory | Purpose |
|-----------|---------|
| `wiki/strategies/` | Trading strategy definitions |
| `wiki/backtests/` | Backtest results and performance analyses |
| `wiki/indicators/` | Technical indicator definitions |
| `wiki/risk/` | Risk models and position sizing rules |

## Domain Page Types

| Type | Directory | Purpose | Frontmatter Fields |
|------|-----------|---------|--------------------|
| `strategy` | `wiki/strategies/` | An algorithmic trading strategy | `type: trend \| mean_reversion \| arbitrage \| market_making \| ml_based \| hybrid`, `timeframe`, `instruments: []` |
| `backtest` | `wiki/backtests/` | Results from a strategy backtest | `sharpe: float`, `max_dd: float`, `win_rate: float`, `trades: int`, `timeframe: string`, `period_start: YYYY-MM-DD`, `period_end: YYYY-MM-DD`, `strategy: []` |
| `indicator` | `wiki/indicators/` | A technical indicator or signal generator | `type: trend \| momentum \| volatility \| volume \| custom`, `parameters: {}`, `inputs: []` |
|| `risk_model` | `wiki/risk/` | A risk management model or position sizing rule | `type: fixed_fraction \\| kelly \\| var \\| cvar \\| dynamic`, `parameters: {}`, `max_position_pct: float` |
|| `module` | `wiki/modules/` | A shared software module, library, or reusable component | `language`, `namespace`, `version`, `dependencies: []`, `exports: []` |

## Naming Conventions

- **Strategies:** `strategy-name.md` (e.g., `dual-moving-average-crossover.md`)
- **Backtests:** `strategy-name-YYYY-MM-DD.md` (e.g., `dual-ma-crossover-2024-01-01.md`)
- **Indicators:** `indicator-name.md` (e.g., `rsi.md`, `bollinger-bands.md`)
- **Risk models:** `risk-model-name.md` (e.g., `optimal-f.md`, `var-95.md`)
- **Modules:** `namespace/module-name.md` (e.g., `core/logger.md`, `trading/order-ops.md`, `risk/risk-management.md`)

## Frontmatter Template

```yaml
---
type: strategy | backtest | indicator | risk_model
title: Human-readable title
tags: []
related: []
sources: []
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

### Strategy-specific
```yaml
type: strategy
type: trend | mean_reversion | arbitrage | market_making | ml_based | hybrid
timeframe: "1h"
instruments:
  - instrument-slug
```

### Backtest-specific
```yaml
type: backtest
strategy:
  - strategy-slug
sharpe: 1.85
max_dd: -12.3
win_rate: 0.62
trades: 450
timeframe: "1h"
period_start: 2023-01-01
period_end: 2023-12-31
```

### Indicator-specific
```yaml
type: indicator
indicator_type: momentum | trend | volatility | volume | custom
parameters:
  period: 14
  overbought: 70
  oversold: 30
inputs:
  - "close_price"
```

### Risk Model-specific
```yaml
type: risk_model
risk_type: fixed_fraction | kelly | var | cvar | dynamic
parameters:
  fraction: 0.02
  max_risk_per_trade: 0.01
max_position_pct: 5.0
```

## Conventions

1. Every backtest must reference its strategy.
2. Backtest pages should record data sources, commission/slippage
   assumptions, and any survivorship bias caveats.
3. Strategy pages should document entry, exit, and position sizing
   logic in full.
4. Indicator pages should include the mathematical formula or a link
   to the reference source.
5. When a strategy version changes, create a new backtest rather than
   overwriting the old one — versioning is key for reproducibility.
