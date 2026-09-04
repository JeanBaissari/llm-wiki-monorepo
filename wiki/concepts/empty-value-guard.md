---
type: concept
confidence: high
contested: false
implemented_by:
  - "ew-auto-tp"
related:
  - "auto-tp-adjustment"
  - "indicator-buffer-constants"
sources:
  - "raw/src5/shared/modules/ew/EWAutoTP.mqh"
created: 2026-08-17
updated: 2026-08-17
---

# EMPTY_VALUE Guard

Pattern of checking `indicator == EMPTY_VALUE` before using buffer values from iCustom() calls.

## Definition

When reading indicator buffers via `iCustom()`, the return value is `EMPTY_VALUE` when:
- The indicator is not loaded
- The buffer has no valid data at the requested bar
- The indicator hasn't warmed up yet

EWAutoTP consistently guards against this:

```mql5
if(tp161 == EMPTY_VALUE || tp161 <= 0) return false;
if(kennedyTrail == EMPTY_VALUE || kennedyTrail <= 0) return false;
if(completion == EMPTY_VALUE) return false;
if(divergence == EMPTY_VALUE) return false;
```

## Why It Matters

Using `EMPTY_VALUE` (typically `DBL_MAX` or a large sentinel) as a price would cause:
- Erroneous TP/SL modifications to extreme prices
- False extension detection triggers
- False exhaustion exits

## Pattern

```mql5
double value = ReadIndicator(buffer, bar, ...);
if(value == EMPTY_VALUE || value <= 0) return false;  // guard
// ... use value safely
```

The `<= 0` check catches cases where the indicator returns 0 instead of EMPTY_VALUE for invalid data.

## Cross-References

- [[wiki/entities/ew-auto-tp|EWAutoTP]] — Where this pattern is used throughout
- [[wiki/concepts/indicator-buffer-constants|Indicator Buffer Constants]] — Buffer source
