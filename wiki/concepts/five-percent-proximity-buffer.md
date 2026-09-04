---
type: concept
confidence: high
contested: false
implemented_by:
  - "ew-auto-tp"
related:
  - "extension-detection"
  - "auto-tp-adjustment"
sources:
  - "raw/src5/shared/modules/ew/EWAutoTP.mqh"
created: 2026-08-17
updated: 2026-08-17
---

# 5% Proximity Buffer

Early-warning zone around the 161.8% Fibonacci extension target. Triggers TP ladder upgrade when price comes within 5% of the target.

## Definition

The 5% proximity buffer is the detection threshold for extension detection. Rather than waiting for price to reach the exact 161.8% level, the system triggers when price is within 5% of it.

## Formula

```mql5
// BUY: price approaching from below
currentPrice > tp161 * 0.95

// SELL: price approaching from above
currentPrice < tp161 * 1.05
```

## Why 5%

- **Early warning** — Provides headroom for the 2-bar adjustment delay
- **Avoids late modification** — If waiting for exact touch, TP might not be updated in time
- **Buffer against spread** — Account for bid/ask spread differences
- **Momentum confirmation** — 5% proximity with 2-bar delay = sustained approach

## Interaction with Adjust Delay

The 5% buffer and 2-bar delay work together:
1. Price enters 5% zone → detection fires, timer starts
2. 2 bars elapse → TP modification executes
3. If price retreats from zone before 2 bars → detection cleared, no modification

## Cross-References

- [[wiki/concepts/extension-detection|Extension Detection]] — Uses this buffer
- [[wiki/concepts/adjust-delay|Adjust Delay]] — Works in conjunction
- [[wiki/entities/ew-auto-tp|EWAutoTP]] — Implementation
