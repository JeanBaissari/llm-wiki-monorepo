---
type: concept
confidence: high
contested: false
implemented_by:
  - "ew-auto-tp"
related:
  - "auto-tp-adjustment"
  - "fibonacci-extension-ladder"
sources:
  - "raw/src5/shared/modules/ew/EWAutoTP.mqh"
created: 2026-08-17
updated: 2026-08-17
---

# Bearish Ladder Inversion

Inverted TP ladder logic for sell orders where lower prices = larger profit.

## Definition

For sell orders, the Fibonacci extension ladder inverts direction: tp161 > tp261 > tp423 (progressively lower prices). The comparison operators flip accordingly.

## Ladder Comparison

| Direction | Step 1→2 | Step 2→3 |
|-----------|----------|----------|
| BUY | `currentTP <= tp161 + eps` | `currentTP <= tp261 + eps` |
| SELL | `currentTP >= tp161 - eps` | `currentTP >= tp261 - eps` |

## Formula (Direction-Agnostic)

The 423.6% target derivation works identically for both directions:

```mql5
double legSize = tp261 - tp161;   // positive for bull, negative for bear
double tp423   = tp161 + 2.618 * legSize;
```

For sells: `tp261 < tp161`, so `legSize` is negative, making `tp423 < tp261 < tp161`.

## Why This Works

The mathematical relationship between Fibonacci extension levels is preserved regardless of direction. The 2.618 multiplier between 261.8% and 423.6% is constant. Only the comparison operators need to flip.

## Cross-References

- [[wiki/concepts/fibonacci-extension-ladder|Fibonacci Extension Ladder]] — Ladder logic
- [[wiki/entities/ew-auto-tp|EWAutoTP]] — Implementation in AdjustTPLadder()
