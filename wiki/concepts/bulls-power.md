---
type: concept
title: Bulls Power
tags:
  - oscillator
  - buying-pressure
  - trend-strength
confidence: high
contested: false
implemented_by:
  - ind-bulls
sources: []
created: 2026-08-17
updated: 2026-08-17
---

# Bulls Power

Bulls Power is a technical analysis oscillator that measures the strength of buying pressure in the market by comparing the high price to an Exponential Moving Average (EMA).

## Definition

Bulls Power quantifies how far the high price of each bar deviates from the EMA. Positive values indicate the high is above the EMA (buying pressure), while negative values indicate the high is below the EMA (selling pressure).

## Formula

```
Bulls Power = High - EMA(Close, Period)
```

Where:
- `High` = highest price of the current bar
- `EMA(Close, Period)` = Exponential Moving Average of closing prices
- `Period` = EMA period (default: 13)

## Mathematical Properties

- **Range**: Unbounded (can be positive or negative)
- **Zero line**: Represents equilibrium between high price and EMA
- **Smoothing**: Controlled by EMA period parameter

## Trading Interpretation

| Condition | Interpretation |
|-----------|----------------|
| Bulls Power > 0 and rising | Strong buying pressure, uptrend |
| Bulls Power > 0 but falling | Weakening buying pressure |
| Bulls Power < 0 and falling | Strong selling pressure, downtrend |
| Bulls Power < 0 but rising | Weakening selling pressure |
| Zero crossing (up) | Potential bullish signal |
| Zero crossing (down) | Potential bearish signal |

## Relationship to Bears Power

Bulls Power is complementary to Bears Power:

```
Bulls Power = High - EMA
Bears Power = Low - EMA
```

When used together:
- Both positive: Strong uptrend
- Both negative: Strong downtrend
- Bulls positive, Bears negative: Potential reversal zone
- Divergence between them: Trend weakening

## Limitations

1. **Lagging**: EMA introduces lag, especially with longer periods
2. **False signals**: Can generate signals in ranging markets
3. **No overbought/oversold**: Unlike RSI, no fixed boundaries
4. **Period sensitivity**: Results vary significantly with different EMA periods

## Common Settings

| Trading Style | Period | Notes |
|---------------|--------|-------|
| Scalping | 5-8 | More responsive, more noise |
| Day trading | 10-13 | Balanced |
| Swing trading | 14-21 | Smoother, fewer signals |

## Related Concepts

- [[wiki/concepts/bears-power|Bears Power]] — Complementary oscillator for selling pressure
- [[wiki/concepts/ema|EMA]] — Exponential Moving Average used as baseline
- [[wiki/concepts/oscillator|Oscillator]] — Category of technical indicators
