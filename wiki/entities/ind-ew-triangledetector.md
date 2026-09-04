---
type: entity
language: mql5
namespace: indicators
status: active
version: "1.07"
title: Ind EW TriangleDetector
tags: [elliott-wave, triangle, pattern-detection, indicator, signal]
related:
  - "ew-common-mqh"
  - "ind-ew-swingengine"
  - "ind-ew-wavelabeler"
  - "triangle-classification"
  - "ew-confidence-scoring"
sources:
  - "raw/indicators/custom/EW/Ind_EW_TriangleDetector.mq5"
created: 2026-08-17
updated: 2026-08-17
---

# Ind EW TriangleDetector

MQL5 chart-window indicator that detects contracting and running Elliott Wave triangle patterns (A-B-C-D-E) with variant classification and breakout target projection.

## Overview

Part of the Elliott Wave Suite v2.0. Classifies triangles into 7 variants (NONE, SYMM, ASC, DESC, RUNNING_SYMM, RUNNING_ASC, RUNNING_DESC) and outputs 10 buffers covering pattern state, confidence, trendlines, and breakout targets.

## Dependencies

| Dependency | Type | Purpose |
|------------|------|---------|
| `EW_Common.mqh` | include | Shared profile, calibration, logging |
| `Ind_EW_SwingEngine` | sub-indicator | Swing high/low detection (buffers 0-3) |
| `Ind_EW_WaveLabeler` | sub-indicator | Wave number classification for position validation |

## Input Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `inp_ProfileID` | 1 | Profile ID for sub-indicators |
| `inp_UseSync` | false | Sync flag for WaveLabeler |
| `inp_Theme` | 0 | Theme for WaveLabeler |
| `inp_MinConfidence` | 40 | Minimum confidence threshold for detection |
| `inp_LookbackBars` | 300 | Swing search lookback |
| `inp_FlatSlopeThreshold` | 0.20 | Slope ratio threshold for ASC/DESC variant |
| `inp_ShowLabels` | true | Chart label display |
| `inp_DrawTrendlines` | true | Trendline object drawing |
| `inp_SwingFractalBars` | 2 | Fractal bars for SwingEngine |
| `inp_SwingATRPeriod` | 14 | ATR period for SwingEngine |
| `inp_SwingATRMult` | 1.0 | ATR multiplier for SwingEngine |
| `inp_SwingShowArrows` | false | Arrow display for SwingEngine |
| `inp_EnablePositionValidation` | true | Suppress triangles in Wave 2/A |

## Output Buffers

| Index | Name | Description |
|-------|------|-------------|
| 0 | TriVariant | Pattern variant (0=NONE, 1=SYMM, 2=ASC, 3=DESC, 4=RUN_SYMM, 5=RUN_ASC, 6=RUN_DESC) |
| 1 | Direction | +1=bull, -1=bear, 0=none |
| 2 | Confidence | Score 0-100 |
| 3 | UpperTrendline | Upper trendline price (carry-forward) |
| 4 | LowerTrendline | Lower trendline price (carry-forward) |
| 5 | E_WaveTarget | E-wave apex projection price |
| 6 | BreakoutState | 0=NONE, 1=PENDING, 2=CONFIRMED |
| 7 | Invalidation | Invalidation price level |
| 8 | Completion | 0=FORMING, 1=COMPLETE |
| 9 | BreakoutTarget | Post-triangle thrust target |

## Detection Logic

The indicator runs two detection passes per direction (bullish, bearish):

1. **Contracting triangle** — monotonically decreasing wave amplitudes across A-B-C-D legs. B < A, C < B, D < C.
2. **Running triangle** — B may exceed A (expansion), but C < B and D < C must still hold. Both trendlines slope the same direction.

Variant classification uses slope ratio `|loSlope| / |upSlope|` against `inp_FlatSlopeThreshold`.

## Position Validation

Triangles detected during Wave 2 or Wave A are suppressed via `IsInvalidTrianglePosition()`, which reads wave number from `Ind_EW_WaveLabeler` buffer 0 at bar shift 1 (previous bar, non-repainting).
