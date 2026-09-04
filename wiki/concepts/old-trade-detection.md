---
type: concept
confidence: high
contested: false
implemented_by:
  - "order-persistence"
related:
  - "order-persistence"
  - "corderops"
  - "daily-loss-breaker"
sources:
  - "raw/src5/trading/OrderPersistence.mqh"
created: 2026-08-17
updated: 2026-08-17
---

# Old Trade Detection

Detects orders opened before today's midnight boundary, used for recovery detection and daily accounting.

## Definition

An "old trade" is any order whose open time precedes today's midnight (`StringToTime(TimeToString(TimeCurrent(), TIME_DATE))`). Old trades indicate the EA was running in a previous session and may be in a recovery state.

## Functions

### `IsOldTrade(int ticket)`
- Selects order by ticket
- Returns true if `OpenTime < today's midnight`
- Used for per-order checks

### `CountOldTrades(int magic)`
- Scans all open orders for given magic number and symbol
- Counts orders with `OpenTime < today's midnight`
- Only market orders (type <= OP_SELL) are counted
- Used for aggregate daily accounting

## Detection Boundary

```
today = StringToTime(TimeToString(TimeCurrent(), TIME_DATE));
isOld = (orderOpenTime < today);
```

The midnight boundary is server-time based (from `TimeCurrent()`). Orders opened at exactly midnight are NOT considered old (strict less-than).

## Usage in Recovery

`ScanRecoveryState()` uses old trade detection to:
1. Determine if recovery is active (`g_inRecovery = hasOldTrades`)
2. Find max lot among old trades (not current-session trades)
3. Count old buys vs sells for direction locking

## Cross-References

- [[wiki/entities/order-persistence|OrderPersistence]] — Implementation
- [[wiki/concepts/martingale-recovery-level-detection|Martingale Recovery Level Detection]] — Uses old trade detection
- [[wiki/concepts/daily-loss-breaker|Daily Loss Breaker]] — Related daily boundary concept
