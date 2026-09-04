---
type: concept
title: Apex Projection
confidence: high
contested: false
tags: [elliott-wave, triangle, apex, trendline, projection]
related:
  - "triangle-classification"
  - "ind-ew-triangledetector"
  - "triangle-breakout-state"
implemented_by:
  - "ind-ew-triangledetector"
created: 2026-08-17
updated: 2026-08-17
---

# Apex Projection

Intersection point of upper and lower triangle trendlines, used as the E-wave target and breakout reference.

## Formula

```
apexPrice = upperPrice0 - upSlope * bApex
bApex = (upperPrice0 - lowerPrice0) / (upperSlope + lowerSlope)
```

Where:
- `upperPrice0` / `lowerPrice0` = trendline intercepts at bar 0
- `upSlope` / `lowerSlope` = trendline slopes (bar-indexed)
- `bApex` = bar offset to apex from bar 0

## Degenerate Case

When `|upperSlope + lowerSlope| < 1e-10` (nearly parallel lines), apex defaults to the midpoint of the two intercepts.

## Breakout Target

```
breakoutTarget = apexPrice + breakoutDir * waveA
```

Where `breakoutDir` = -1.0 for bullish triangles, +1.0 for bearish triangles. This places the target on the opposite side of the apex from the triangle, consistent with Elliott Wave convention that triangles precede a final thrust against the prevailing trend.

## Running Triangle Apex

Uses a different formula since both slopes are in the same direction:

```
apexDenom = upSlope - loSlope
bApex = (upperAtBar0 - lowerAtBar0) / apexDenom
```

Requires `apexDenom != 0` and `bApex > 0` (apex must be ahead of current bar).
