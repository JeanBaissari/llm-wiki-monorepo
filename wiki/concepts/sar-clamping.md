---
type: concept
title: SAR Clamping
confidence: high
contested: false
implemented_by:
  - entities/ind-parabolic
related:
  - concepts/parabolic-sar-calculation
  - concepts/sar-reversal-logic
tags:
  - indicator
  - parabolic-sar
  - safety
  - validation
created: 2026-08-17
updated: 2026-08-17
---

# SAR Clamping

The mechanism that prevents SAR from moving beyond recent price extremes.

## Purpose

Clamping ensures SAR stays within reasonable bounds relative to recent price action, preventing unrealistic stop levels.

## Implementation

### Long Position Clamping

```mql5
if(sar > low[i-1])
    sar = low[i-1];
if(sar > low[i-2])
    sar = low[i-2];
if(sar > low[i])
{
    // Trigger reversal
    SaveLastReverse(i, true, step, low[i], last_high, ep, sar);
    // ... reversal logic
}
```

### Short Position Clamping

```mql5
if(sar < high[i-1])
    sar = high[i-1];
if(sar < high[i-2])
    sar = high[i-2];
if(sar < high[i])
{
    // Trigger reversal
    SaveLastReverse(i, false, step, last_low, high[i], ep, sar);
    // ... reversal logic
}
```

## Rules

1. **Long SAR**: Cannot exceed lowest low of current and previous 2 bars
2. **Short SAR**: Cannot exceed highest high of current and previous 2 bars
3. **Reversal Trigger**: If clamping would place SAR beyond price, reversal occurs

## Benefits

1. Prevents stop levels that are too tight
2. Accounts for recent volatility
3. Classic Wilder behavior (original algorithm)
4. Reduces whipsaws in ranging markets

## Edge Cases

- First 2 bars: Special handling for initialization
- Volatile markets: Clamping becomes more active
- Tight ranges: Multiple clamping adjustments possible
