---
type: review
title: "Review: TriangleDetector Breakout Target Direction Inversion"
severity: medium
status: open
target: "wiki/concepts/apex-projection.md"
tags: [design, breakout-target, elliott-wave-convention]
related:
  - "ind-ew-triangledetector"
  - "apex-projection"
  - "triangle-breakout-state"
created: 2026-08-17
updated: 2026-08-17
---

# Review: TriangleDetector Breakout Target Direction Inversion

## Issue

For bullish triangles, `breakoutDir = -1.0`, placing the breakout target *below* the apex. For bearish triangles, `breakoutDir = +1.0`, placing it *above* the apex. This assumes triangles always precede a thrust *against* the prevailing trend.

## Evidence

```mql5
double breakoutDir = isBullish ? -1.0 : 1.0;
outBreakoutTarget = outETarget + breakoutDir * waveA;
```

## Impact

This is correct per Elliott Wave convention (triangles precede the final thrust in the larger trend direction, which is opposite to the triangle's direction). However, this may confuse users who expect the breakout target to be in the triangle's breakout direction.

## Recommendation

Document this explicitly in the indicator's chart label or help text. The current label shows direction + variant but does not indicate the breakout target is a thrust target (opposite direction).
