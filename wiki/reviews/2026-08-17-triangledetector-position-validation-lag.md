---
type: review
title: "Review: TriangleDetector Position Validation One-Bar Lag"
severity: low
status: open
target: "wiki/concepts/triangle-position-validation.md"
tags: [repainting, position-validation, design-tradeoff]
related:
  - "ind-ew-triangledetector"
  - "triangle-position-validation"
  - "ind-ew-wavelabeler"
created: 2026-08-17
updated: 2026-08-17
---

# Review: TriangleDetector Position Validation One-Bar Lag

## Issue

Position validation reads the wave number from bar shift 1 (previous bar) rather than bar 0. This avoids repainting but introduces a one-bar lag: if the wave label changes on the current bar, the suppression may not take effect until the next bar.

## Evidence

```mql5
double waveNum = ReadWaveLabelerWaveNum(1);  // bar shift 1, not 0
```

## Impact

Low in practice. The one-bar window during which a suppressed triangle might briefly appear is unlikely to affect trading decisions, especially since the triangle itself requires 5+ swings to form.

## Recommendation

No change needed. This is a standard non-repainting design pattern. Document the behavior for future maintainers.
