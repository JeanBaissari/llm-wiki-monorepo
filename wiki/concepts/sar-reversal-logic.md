---
type: concept
title: SAR Reversal Logic
confidence: high
contested: false
implemented_by:
  - entities/ind-parabolic
related:
  - concepts/parabolic-sar-calculation
  - concepts/extreme-point-tracking
  - concepts/sar-clamping
tags:
  - indicator
  - parabolic-sar
  - reversal
  - signal
created: 2026-08-17
updated: 2026-08-17
---

# SAR Reversal Logic

The conditions that trigger a trend reversal in the Parabolic SAR system.

## Reversal Conditions

### Long to Short

```mql5
if(dir_long && low[i] < ExtSARBuffer[i-1])
{
    // Reversal triggered
    SaveLastReverse(i, true, step, low[i], last_high, ep, sar);
    step = ExtSarStep;
    dir_long = false;
    ep = low[i];
    last_low = low[i];
    ExtSARBuffer[i++] = last_high;
    continue;
}
```

### Short to Long

```mql5
if(!dir_long && high[i] > ExtSARBuffer[i-1])
{
    // Reversal triggered
    SaveLastReverse(i, false, step, last_low, high[i], ep, sar);
    step = ExtSarStep;
    dir_long = true;
    ep = high[i];
    last_high = high[i];
    ExtSARBuffer[i++] = last_low;
    continue;
}
```

## Post-Reversal Actions

1. Save current state via `SaveLastReverse`
2. Reset acceleration factor to initial step
3. Update direction flag
4. Set new extreme point
5. Place SAR at previous extreme level

## Signal Interpretation

- Reversal = potential trend change
- SAR dot changes position relative to price
- Color remains constant (lime), position indicates direction

## State Persistence

- `ExtLastReverse`: Bar index saved for incremental calculation
- `ExtDirectionLong`: New direction stored
- All state variables reset for new trend
