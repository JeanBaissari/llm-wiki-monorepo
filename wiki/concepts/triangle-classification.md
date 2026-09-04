---
type: concept
title: Triangle Classification
confidence: high
contested: false
tags: [elliott-wave, triangle, pattern-classification, corrective]
related:
  - "ind-ew-triangledetector"
  - "ew-confidence-scoring"
  - "contracting-triangle"
  - "running-triangle"
implemented_by:
  - "ind-ew-triangledetector"
created: 2026-08-17
updated: 2026-08-17
---

# Triangle Classification

Elliott Wave triangle pattern variants classified by trendline slope ratio.

## Overview

Triangles are corrective patterns that form during wave 4 or wave B positions. The variant is determined by the relative flatness of the upper vs lower trendline, quantified as a slope ratio.

## Variant Taxonomy

### Contracting Triangles

Wave amplitudes contract monotonically: B < A, C < B, D < C. Both trendlines converge toward an apex.

| Variant | Slope Ratio | Characteristic |
|---------|-------------|----------------|
| Symmetrical (SYMM) | 0.20–0.80 | Both trendlines converge at similar angles |
| Ascending (ASC) | < 0.20 | Upper trendline is relatively flat; lower rises steeply |
| Descending (DESC) | > 0.80 | Lower trendline is relatively flat; upper falls steeply |

### Running Triangles

Both trendlines slope in the same direction. Wave B may expand beyond A (B > A), but C < B and D < C must still hold.

| Variant | Slope Ratio | Characteristic |
|---------|-------------|----------------|
| Running Symmetrical (RUN_SYMM) | 0.20–0.80 | Both trendlines slope same direction, converge |
| Running Ascending (RUN_ASC) | < 0.20 | Upper is flatter in running config |
| Running Descending (RUN_DESC) | > 0.80 | Lower is flatter in running config |

## Slope Ratio Formula

```
ratio = |loSlope| / (|upSlope| + |loSlope|)
```

Where:
- `upSlope` = trendline connecting swing highs
- `loSlope` = trendline connecting swing lows
- Threshold default: `inp_FlatSlopeThreshold = 0.20`

## Bullish vs Bearish

- **Bullish triangle**: Upper trendline slopes down (positive slope), lower slopes up (negative slope). Breakout expected to the downside (thrust against prevailing trend).
- **Bearish triangle**: Upper slopes up, lower slopes down. Breakout expected to the upside.

## Key Properties

- Minimum 5 swing points required (A-B-C-D-E)
- Swing points must alternate High/Low in correct order
- Wave amplitudes must be > 0
- Upper trendline intercept must exceed lower at bar 0
- Time symmetry (non-zero spans between all legs) adds confidence
