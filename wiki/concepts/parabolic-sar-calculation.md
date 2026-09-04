---
type: concept
title: Parabolic SAR Calculation
confidence: high
contested: false
implemented_by:
  - entities/ind-parabolic
related:
  - concepts/acceleration-factor
  - concepts/extreme-point-tracking
  - concepts/sar-reversal-logic
  - concepts/sar-clamping
tags:
  - indicator
  - parabolic-sar
  - trend
  - algorithm
created: 2026-08-17
updated: 2026-08-17
---

# Parabolic SAR Calculation

The core mathematical formula for computing Parabolic Stop-And-Reversal values.

## Formula

```
SAR[i] = SAR[i-1] + step × (EP - SAR[i-1])
```

Where:
- `SAR[i]` = Current bar's SAR value
- `SAR[i-1]` = Previous bar's SAR value
- `step` = Current acceleration factor
- `EP` = Extreme point (highest high for long, lowest low for short)

## Implementation

```mql5
sar = ExtSARBuffer[i-1] + step * (ep - ExtSARBuffer[i-1]);
```

## Properties

1. **Convergent**: SAR moves toward price over time
2. **Accelerating**: Step increases when new extremes are reached
3. **Asymmetric**: Different behavior for long vs short positions
4. **Stateful**: Requires previous SAR value and extreme point

## Edge Cases

- First calculation: SAR initialized to previous bar's high/low
- Invalid inputs: Falls back to defaults (step=0.02, max=0.2)
- Minimum bars: Requires at least 3 bars for calculation
