---
type: concept
title: Extreme Point Tracking
confidence: high
contested: false
implemented_by:
  - entities/ind-parabolic
related:
  - concepts/parabolic-sar-calculation
  - concepts/acceleration-factor
  - concepts/sar-reversal-logic
tags:
  - indicator
  - parabolic-sar
  - state
created: 2026-08-17
updated: 2026-08-17
---

# Extreme Point Tracking

The mechanism for tracking the highest high (long) or lowest low (short) since the last reversal.

## Definition

The Extreme Point (EP) represents the most favorable price level achieved during the current trend. It is used in the SAR calculation formula.

## Logic

| Direction | EP Value | Updated When |
|-----------|----------|--------------|
| Long | Highest high | New high > current EP |
| Short | Lowest low | New low < current EP |

## Implementation

```mql5
// Long position
if(ep < high[i])
    ep = last_high = high[i];

// Short position
if(ep > low[i])
    ep = last_low = low[i];
```

## State Variables

- `ExtLastEP`: Current extreme point value
- `ExtLastHigh`: Highest high since reversal (for long)
- `ExtLastLow`: Lowest low since reversal (for short)

## Role in Reversal Detection

EP is critical for:
1. SAR calculation (SAR moves toward EP)
2. Acceleration factor increases (when EP updates)
3. Reversal triggers (when SAR crosses price)

## Edge Cases

- Initial EP set during direction detection
- EP resets on reversal
- EP tracking continues across multiple bars
