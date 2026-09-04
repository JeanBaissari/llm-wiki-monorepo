---
type: review
status: open
severity: info
entity: order-persistence
created: 2026-08-17
related:
  - "order-persistence"
  - "basket-breakeven-detection"
---

# OrderPersistence — Hardcoded Breakeven Threshold

## Issue

`IsBasketAtBreakeven()` uses a hardcoded threshold of `point * 5` to determine if a stop loss is "at breakeven". This is not configurable per symbol or timeframe.

## Impact

- For symbols with very small point values (e.g., JPY pairs with 3-digit quotes), 5 points may be too tight
- For symbols with large point values (e.g., XAUUSD), 5 points may be too loose
- Different brokers may have different stop level requirements
- No way to adjust without modifying the module source

## Recommendation

Make the threshold configurable:

```mql5
bool IsBasketAtBreakeven(int magic, int breakevenPoints = 5)
```

Or accept it as a parameter in the struct-based refactor.
