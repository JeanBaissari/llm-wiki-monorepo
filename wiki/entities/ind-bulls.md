---
type: entity
title: Ind Bulls
tags:
  - indicator
  - oscillator
  - bulls-power
related:
  - ind-bears
  - ema
sources:
  - raw/src/indicators/ind_bulls.mq5
created: 2026-08-17
updated: 2026-08-17
language: mql5
namespace: indicators
status: active
version: "1.00"
dependencies:
  - ema
---

# Ind Bulls

Bulls Power is an oscillator that measures the strength of buying pressure by calculating the difference between the high price and an Exponential Moving Average (EMA).

## Formula

```
Bulls Power = High - EMA(Period)
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `InpBullsPeriod` | 13 | EMA period for the baseline calculation |

## Calculation

1. Compute EMA of closing prices using `InpBullsPeriod`
2. For each bar: `Bulls Power = High[i] - EMA[i]`
3. Values are plotted as a histogram in a separate window

## Interpretation

- **Positive values**: High is above EMA, indicating buying pressure
- **Negative values**: High is below EMA, indicating selling pressure
- **Zero crossing**: Potential trend change signal

## Implementation Details

- Uses `iMA()` handle for EMA calculation
- Two buffers: `ExtBullsBuffer` (data) and `ExtTempBuffer` (calculations)
- Incremental calculation for performance
- Separate window display with histogram visualization

## Related

- [[wiki/entities/ind-bears|Ind Bears]] — Complementary indicator measuring selling pressure
- [[wiki/concepts/ema|EMA]] — Exponential Moving Average used as baseline
