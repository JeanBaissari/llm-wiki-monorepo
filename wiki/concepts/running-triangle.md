---
type: concept
title: Running Triangle
confidence: medium
contested: false
tags: [elliott-wave, triangle, corrective, running, trend-continuation]
related:
  - "triangle-classification"
  - "contracting-triangle"
  - "ind-ew-triangledetector"
  - "ew-confidence-scoring"
implemented_by:
  - "ind-ew-triangledetector"
created: 2026-08-17
updated: 2026-08-17
---

# Running Triangle

Elliott Wave corrective pattern where both trendlines slope in the same direction, allowing wave B to expand beyond wave A while C and D still contract.

## Definition

A five-wave structure where:
- Wave B amplitude > Wave A amplitude (expansion allowed)
- Wave C amplitude < Wave B amplitude (contraction resumes)
- Wave D amplitude < Wave C amplitude
- Both trendlines slope in the same direction (both positive for bullish, both negative for bearish)
- Upper slope magnitude > lower slope magnitude (for bullish)

## Key Differences from Contracting

| Property | Contracting | Running |
|----------|-------------|---------|
| Wave B vs A | B < A (contraction) | B > A (expansion) |
| Trendline slopes | Opposite directions | Same direction |
| Invalidation | Wave A origin | Wave C price |
| Base confidence | 40 | 45 |
| B retracement quality | 50-80% of A | 100-138.2% of A (Fib extension) |

## Validation Rules

All must pass:
1. 5 swing points alternating High/Low
2. Wave B > Wave A (expansion)
3. Wave C < Wave B, Wave D < Wave C (contraction)
4. Both trendlines slope same direction
5. Upper slope > lower slope magnitude (for bullish)
6. Apex must be ahead of current bar (bApex > 0)

## Invalidation

Invalidation price = wave C price (not wave A as in contracting).

## Breakout Target

Same formula as contracting: `apexPrice ± waveA`, thrust direction opposite to prevailing trend.
