---
type: concept
title: Acceleration Factor
confidence: high
contested: false
implemented_by:
  - entities/ind-parabolic
related:
  - concepts/parabolic-sar-calculation
  - concepts/extreme-point-tracking
tags:
  - indicator
  - parabolic-sar
  - parameter
created: 2026-08-17
updated: 2026-08-17
---

# Acceleration Factor

The step multiplier that controls how quickly SAR approaches price.

## Definition

The acceleration factor (AF) starts at `ExtSarStep` (default 0.02) and increases by this amount each time a new extreme point is reached, up to `ExtSarMaximum` (default 0.2).

## Behavior

| Condition | Action |
|-----------|--------|
| New extreme reached | AF += ExtSarStep |
| AF would exceed maximum | AF = ExtSarMaximum |
| Reversal occurs | AF resets to ExtSarStep |

## Implementation

```mql5
if(ep < high[i])  // Long position, new high
{
    if((step + ExtSarStep) <= ExtSarMaximum)
        step += ExtSarStep;
}
```

## Impact

- **Low AF (0.01-0.02)**: Slower SAR movement, fewer false signals, later exits
- **High AF (0.03-0.05)**: Faster SAR movement, more signals, earlier exits
- **Maximum AF**: Caps acceleration to prevent SAR from moving too aggressively

## References

- Wilder, J.W. (1978). "New Concepts in Technical Trading Systems"
