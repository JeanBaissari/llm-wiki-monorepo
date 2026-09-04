---
type: concept
title: Triangle Breakout State
confidence: high
contested: false
tags: [elliott-wave, triangle, breakout, confirmation, state-machine]
related:
  - "triangle-classification"
  - "ind-ew-triangledetector"
  - "apex-projection"
implemented_by:
  - "ind-ew-triangledetector"
created: 2026-08-17
updated: 2026-08-17
---

# Triangle Breakout State

Three-state machine tracking whether a completed triangle has broken out.

## States

| State | Value | Meaning |
|-------|-------|---------|
| NONE | 0 | No triangle detected or triangle not yet complete |
| PENDING | 1 | Triangle complete but price has not broken trendline |
| CONFIRMED | 2 | Previous bar's close broke the relevant trendline |

## Transition Logic

1. **NONE → PENDING**: When triangle detection succeeds and completion = TRI_COMPLETE
2. **PENDING → CONFIRMED**: When previous bar's close crosses the trendline:
   - Bullish triangle (direction = -1): close < lowerTrendline
   - Bearish triangle (direction = +1): close > upperTrendline

## Design Notes

- Uses **previous bar's close** (bar index 1), not the current forming bar, to avoid repainting
- A completed triangle that hasn't broken out stays PENDING indefinitely
- Once CONFIRMED, state remains CONFIRMED for all subsequent bars in the same detection cycle
