---
type: review
status: open
severity: info
entity: order-persistence
created: 2026-08-17
related:
  - "order-persistence"
  - "grid-level-reconstruction"
---

# OrderPersistence — Grid Spacing Mismatch Between Reconstruction and Next Level

## Issue

`ReconstructGridLevels()` computes `g_gridSpacing` from the actual open order prices (average spacing). However, `GetNextGridLevel()` uses `inp_GridSpacingPips` (the EA input) rather than the reconstructed spacing to compute the next grid level.

## Impact

- If the EA was restarted after grid levels were placed with modified spacing (e.g., dynamic grid), the next level will use the original input spacing rather than the actual observed spacing
- Grid geometry can become inconsistent after restart
- The reconstructed `g_gridSpacing` is computed but never used by `GetNextGridLevel`

## Recommendation

Either:
1. Use `g_gridSpacing` in `GetNextGridLevel` instead of recomputing from input, or
2. Remove the reconstruction of `g_gridSpacing` if it's not intended to be used, or
3. Add a configuration option to choose between input-based and reconstructed spacing
