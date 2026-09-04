---
type: review
title: "Review: TriangleDetector Symmetrical Breakout Target May Be Zero"
severity: medium
status: open
target: "wiki/concepts/apex-projection.md"
tags: [edge-case, apex-calculation, numerical-stability]
related:
  - "ind-ew-triangledetector"
  - "apex-projection"
created: 2026-08-17
updated: 2026-08-17
---

# Review: TriangleDetector Symmetrical Breakout Target May Be Zero

## Issue

In `CalcApexPrice` (used by contracting triangles), when `|upperSlope + lowerSlope| < 1e-10`, the apex defaults to the midpoint of the two intercepts. However, `outBreakoutTarget` is then computed as `apexPrice + breakoutDir * waveA`, which could place the target far from the triangle if the midpoint is near the current price.

Additionally, the running triangle path returns `TRI_NONE` when `apexDenom < 1e-10` rather than using a fallback, which is the safer behavior.

## Evidence

```mql5
// Contracting — fallback to midpoint (may produce misleading target)
if(MathAbs(denom) < 1e-10) return (upperPrice0 + lowerPrice0) / 2.0;

// Running — no fallback, rejects pattern
if(MathAbs(apexDenom) < 1e-10) return TRI_NONE;
```

## Impact

Medium. Near-parallel trendlines produce a degenerate triangle where the apex is far in the future. The midpoint fallback produces a valid but potentially misleading breakout target.

## Recommendation

Consider rejecting the pattern (return TRI_NONE) when trendlines are nearly parallel, matching the running triangle behavior. Or clamp the breakout target to a reasonable multiple of waveA from the current price.
