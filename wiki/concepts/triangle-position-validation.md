---
type: concept
title: Triangle Position Validation
confidence: high
contested: false
tags: [elliott-wave, triangle, position-validation, wave-labeling]
related:
  - "ind-ew-triangledetector"
  - "ind-ew-wavelabeler"
implemented_by:
  - "ind-ew-triangledetector"
created: 2026-08-17
updated: 2026-08-17
---

# Triangle Position Validation

Suppression mechanism that filters triangle detections occurring during Wave 2 or Wave A positions, where triangles are invalid per Elliott Wave rules.

## Rules

Triangles are only valid in **Wave 4** or **Wave B** positions. Detections during Wave 2 or Wave A are suppressed.

## Implementation

- Reads wave number from `Ind_EW_WaveLabeler` buffer 0 at **bar shift 1** (previous bar)
- Suppresses detection when wave number = 2 (Wave 2) or 10 (Wave A)
- Configurable via `inp_EnablePositionValidation` (default: true)
- Non-repainting design: reads previous bar, not current forming bar

## Design Note

The one-bar lag means a triangle detected on the current bar may persist for one additional bar before suppression takes effect if the wave label changes on the current bar.
