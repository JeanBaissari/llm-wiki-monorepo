---
type: source
title: Ind EW TriangleDetector Source
authors: ["baissarienterprises@protonmail.com"]
year: 2026
url: ""
venue: ""
tags: [elliott-wave, triangle, indicator, mql5, source]
related:
  - "ind-ew-triangledetector"
created: 2026-08-17
updated: 2026-08-17
---

# Ind EW TriangleDetector Source

Source file for the TriangleDetector indicator.

## File

`raw/indicators/custom/EW/Ind_EW_TriangleDetector.mq5`

## Version History

| Version | Date | Notes |
|---------|------|-------|
| 1.07 | 2026-08-17 | Current version |

## Key Functions

| Function | Purpose |
|----------|---------|
| `CollectRecentSwings` | Gathers swing points from SwingEngine into sorted array |
| `CheckContractingTriangle` | Validates and classifies contracting triangles |
| `CheckRunningTriangle` | Validates and classifies running triangles |
| `CalcApexPrice` | Computes trendline intersection point |
| `IsInvalidTrianglePosition` | Checks WaveLabeler for suppressible positions |
| `GetVariantLabel` | Maps variant constant to display string |

## External Dependencies

- `EW_Common.mqh` — shared profile and logging
- `Ind_EW_SwingEngine.ex5` — swing point detection
- `Ind_EW_WaveLabeler.ex5` — wave number classification
