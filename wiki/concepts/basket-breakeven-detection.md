---
type: concept
confidence: high
contested: false
implemented_by:
  - "order-persistence"
related:
  - "order-persistence"
  - "corderops"
  - "break-even"
sources:
  - "raw/src5/trading/OrderPersistence.mqh"
created: 2026-08-17
updated: 2026-08-17
---

# Basket Breakeven Detection

Checks if all open orders in a basket have their stop loss set at or near breakeven (within 5 points of open price).

## Definition

A basket is "at breakeven" when every order's stop loss has been moved to within 5 points of its open price. This is a common milestone in martingale/grid recovery — once all positions are at breakeven, the basket is risk-free.

## Algorithm

```
allAtBreakeven = true
for each open order (magic + symbol + market):
    openPrice = order open price
    sl = order stop loss
    if |sl - openPrice| > point * 5:
        allAtBreakeven = false
        break
return allAtBreakeven
```

## Threshold

The 5-point threshold (in price, not pips) accounts for:
- Normal SL placement rounding
- Broker stop level requirements
- Minor deviations in SL modification

For a 5-digit broker on XAUUSD (point = 0.01), 5 points = 0.05 price units.

## Limitations

- **No partial breakeven**: Returns false if ANY order is outside the threshold; no partial credit
- **Hardcoded threshold**: 5 points is hardcoded; not configurable per symbol or timeframe
- **No SL existence check**: If SL is 0 (no stop loss), `|0 - openPrice|` will be large, correctly returning false
- **Point-based not pip-based**: Uses raw point; may need adjustment for 3-digit vs 5-digit brokers

## Cross-References

- [[wiki/entities/order-persistence|OrderPersistence]] — Implementation
- [[wiki/concepts/break-even|Break Even]] — General breakeven concept
- [[wiki/entities/corderops|COrderOps]] — Order access wrapper
