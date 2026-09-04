---
type: review
title: "Review: TriangleDetector Running Triangle B-Wave Equality Edge Case"
severity: low
status: open
target: "wiki/entities/ind-ew-triangledetector.md"
tags: [edge-case, running-triangle, validation-logic]
related:
  - "ind-ew-triangledetector"
  - "running-triangle"
created: 2026-08-17
updated: 2026-08-17
---

# Review: Running Triangle B-Wave Equality Edge Case

## Issue

In `CheckRunningTriangle`, wave B validation uses `waveB <= waveA` (inclusive rejection), while all other contraction checks use strict `<`. This means a running triangle where wave B exactly equals wave A is rejected, but the threshold behavior is inconsistent with the rest of the detection logic.

## Evidence

```mql5
// Running triangle — inclusive rejection at equality
if(waveB <= waveA) return TRI_NONE;

// Contracting triangle — strict inequality
if(waveB >= waveA) return TRI_NONE;
if(waveC >= waveB) return TRI_NONE;
if(waveD >= waveC) return TRI_NONE;
```

## Impact

Low. Exact equality of floating-point wave amplitudes is extremely rare. However, this inconsistency could cause subtle confusion during code review.

## Recommendation

Consider aligning the running triangle check to `waveB < waveA` for consistency, or documenting the intentional asymmetry.
