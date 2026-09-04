---
type: concept
title: Contracting Triangle
confidence: high
contested: false
tags: [elliott-wave, triangle, corrective, contraction]
related:
  - "triangle-classification"
  - "ind-ew-triangledetector"
  - "running-triangle"
  - "ew-confidence-scoring"
implemented_by:
  - "ind-ew-triangledetector"
created: 2026-08-17
updated: 2026-08-17
---

# Contracting Triangle

Elliott Wave corrective pattern where wave amplitudes decrease monotonically across four legs (A-B-C-D), with both trendlines converging toward an apex.

## Definition

A five-wave corrective structure (A-B-C-D-E) where:
- Wave B amplitude < Wave A amplitude
- Wave C amplitude < Wave B amplitude
- Wave D amplitude < Wave C amplitude
- Upper and lower trendlines converge toward an apex

## Hard Validation Rules

All must pass for detection:

1. Exactly 5 swing points alternating High/Low in correct order
2. Monotonic contraction: `waveB < waveA`, `waveC < waveB`, `waveD < waveC`
3. For bullish: highs rise (C > A, E > C), lows fall (B < D)
4. For bearish: highs fall (C < A, E < C), lows rise (B > D)
5. Trendlines must converge (upper positive, lower negative for bullish)
6. Upper trendline intercept > lower trendline intercept at bar 0
7. All wave amplitudes > 0

## Trendline Construction

Upper trendline: connects swing highs (waves B and D)
Lower trendline: connects swing lows (waves A and C)

```
upperAtBar0 = pts[3].price - upSlope * pts[3].bar
lowerAtBar0 = pts[2].price + loSlope * pts[2].bar
```

## Invalidation

Invalidation price = wave A origin (p0). A close beyond this level invalidates the triangle.

## Breakout Target

```
breakoutTarget = apexPrice ± waveA
```

Direction: opposite to the triangle's prevailing trend (triangles precede final thrust against the larger trend).
