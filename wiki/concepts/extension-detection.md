---
type: concept
confidence: high
contested: false
implemented_by:
  - "ew-auto-tp"
related:
  - "auto-tp-adjustment"
  - "fibonacci-extension-ladder"
  - "adjust-delay"
  - "ind-ew-fibengine"
sources:
  - "raw/src5/shared/modules/ew/EWAutoTP.mqh"
created: 2026-08-17
updated: 2026-08-17
---

# Extension Detection

Detects when price approaches the 161.8% Fibonacci extension target within a 5% proximity buffer, signalling Wave 3 may be extending.

## Definition

Extension detection is the trigger mechanism for the TP ladder. It fires when current price comes within 5% of the 161.8% extension level, providing early warning before the target is reached.

## Detection Formula

```mql5
// BUY: price approaching from below
if(orderType == OP_BUY)
    return (currentPrice > tp161 * 0.95);

// SELL: price approaching from above
if(orderType == OP_SELL)
    return (currentPrice < tp161 * 1.05);
```

The 5% buffer provides early warning so the ladder upgrade can be queued before the adjustment delay elapses.

## Detection Timer

When extension is first detected, the detection time is persisted via `CGlobalEventBus`:

```
Key: "EW_AUTOTP_DET_<ticket>"
Value: iTime(Symbol(), Period(), 0)  — bar open time of first detection
```

The bar shift since detection is computed:

```mql5
int barsSinceDetection = iBarShift(Symbol(), Period(), detectionTime, false);
```

## Delay Gate

The TP ladder only modifies the order when:

```mql5
if(autoAdjustTP && barsSinceDetection >= adjustDelayBars)
```

Default `adjustDelayBars = 2` means 2 full bars must elapse after first detection before the TP is upgraded. This prevents premature modification on transient price spikes.

## State Clearing

When extension is no longer detected (price moves away from 161.8%), the detection state is cleared:

```mql5
CGlobalEventBus::GetInstance().DeletePersisted("GV."+"EW_AUTOTP_DET_"+IntegerToString(ticket));
```

This resets the timer so if price approaches again, a fresh 2-bar delay starts.

## Alert Behavior

If `alertOnAdjust` is true and this is the first bar of detection (`barsSinceDetection == 0`):

```mql5
Alert("EW Auto-TP: Extension detected on ", Symbol(), " ticket=", ticket,
      ". Waiting ", adjustDelayBars, " bars.");
```

## Validation

Detection returns false (no signal) when:
- `tp161 == EMPTY_VALUE` (indicator not loaded)
- `tp161 <= 0` (invalid price)
- `currentPrice <= 0` (invalid price)

## Cross-References

- [[wiki/concepts/auto-tp-adjustment|Auto-TP Adjustment]] — Parent orchestration
- [[wiki/concepts/fibonacci-extension-ladder|Fibonacci Extension Ladder]] — What happens after detection
- [[wiki/concepts/adjust-delay|Adjust Delay]] — Delay mechanism
- [[wiki/entities/ind-ew-fibengine|Ind_EW_FibEngine]] — Source of 161.8% price level
- [[wiki/entities/ew-auto-tp|EWAutoTP]] — Implementation
