---
type: concept
title: "Backtest Methodology"
confidence: high
contested: false
implemented_by:
  - "wiki/entities/mt5-algo-suite"
tags:
  - backtesting
  - methodology
  - pass-fail-criteria
related:
  - "wiki/concepts/mql5-coding-standards"
  - "wiki/sources/standards-md"
created: 2026-08-18
updated: 2026-08-18
---

# Backtest Methodology

Constructing valid backtests and applying pass/fail criteria for strategy validation.

## Valid Backtest Configuration

A valid backtest requires these minimum elements:

1. **Tick data**: Use real tick data (not M1 OHLC) for all tests that will be compared against production
2. **Symbol**: The exact symbol name as traded by the broker
3. **Timeframe**: The primary timeframe of the EA (or `PERIOD_CURRENT`)
4. **Date range**: Minimum 12 months, with at least 3 months out-of-sample
5. **Spread**: Realistic spread model — either fixed at the broker's typical spread or use "Every Tick" mode
6. **Commission**: Include broker commission if applicable (futures, CFDs)
7. **Slippage**: Set to realistic value (10-50 points depending on symbol liquidity)
8. **Deposit**: Match the account type (e.g., $10,000 for standard account)
9. **Parameters**: Set file from `config/research/` with all `inp_` parameters

## Tick Data Requirements

| Data Quality | Use Case | Source |
|--------------|----------|--------|
| Real ticks (RFT) | Final validation, production confidence | Broker Dukascopy, TrueFX |
| M1 OHLC | Initial parameter sweeps, fitness evaluation | MT5 built-in |
| Custom ticks (generated) | Sensitivity analysis, stress testing | Custom generator |

**Minimum tick data duration**: 12 months for swing strategies, 3 months for scalping strategies.

## Pass/Fail Criteria

A backtest **passes** when ALL of these metrics are met:

| Metric | Threshold | Notes |
|--------|-----------|-------|
| Profit Factor | ≥ 1.5 | Adjusted for realistic spread/slippage |
| Max Drawdown | ≤ 30% | Equity curve peak-to-trough |
| Total Trades | ≥ 200 | Statistical significance floor |
| Win Rate | ≥ 35% | Except for high RR strategies (RR ≥ 3:1 allows ≥ 25%) |
| Sharpe Ratio | ≥ 1.0 | Risk-adjusted return |
| Modeling Quality | ≥ 90% | Every tick mode preferred |
| Consecutive Losses | ≤ 10 | Streak resilience check |

A backtest **fails** if ANY metric is below the threshold. Optimization is required before re-testing.

## Contested Aspects

- 200 minimum trades may be too aggressive for certain strategy types
- 30% max drawdown may be too conservative for aggressive strategies
- Sharpe Ratio ≥ 1.0 is relatively high for algorithmic strategies
