---
type: concept
confidence: high
contested: false
implemented_by:
  - "order-persistence"
related:
  - "order-persistence"
  - "martingale-recovery"
  - "corderops"
sources:
  - "raw/src5/trading/OrderPersistence.mqh"
created: 2026-08-17
updated: 2026-08-17
---

# Martingale Recovery Level Detection

Detects if an EA is in recovery mode by scanning open orders and computing the current martingale level from lot sizes.

## Definition

When a martingale EA restarts, it must determine how deep into a recovery cycle it is. This is done by finding the largest open lot size and iteratively multiplying the base lot by the multiplier until the level is found.

## Algorithm

```
1. Scan all open orders for this EA (magic + symbol)
2. Find maxOldLot = largest volume among old trades (opened before today)
3. Start with testLot = inp_LotSize
4. While testLot < maxOldLot - 0.001 AND level < 20:
     testLot *= inp_LotMultiplier
     level++
5. g_recoveryLevel = level + 1
6. Clamp to inp_MaxMartingaleLevels
7. Compute g_recoveryLot = inp_LotSize * pow(inp_LotMultiplier, g_recoveryLevel)
```

## Direction Locking

When `inp_LockRecoveryDirection` is true:
- All old trades are BUY → `g_recoveryDir = 1` (buy only)
- All old trades are SELL → `g_recoveryDir = -1` (sell only)
- Mixed → `g_recoveryDir = 0` (both directions)

When disabled, `g_recoveryDir = 0` always.

## Tolerance

The comparison `testLot < maxOldLot - 0.001` uses a 0.001 lot tolerance to account for floating-point imprecision in lot normalization.

## State Variables Set

| Variable | Type | Description |
|----------|------|-------------|
| `g_inRecovery` | bool | True if any old trades exist |
| `g_recoveryLevel` | int | Current martingale level (1-based) |
| `g_recoveryLot` | double | Next lot size to trade |
| `g_recoveryDir` | int | Direction lock: 1=buy, -1=sell, 0=both |

## Validation

- Level is clamped to `inp_MaxMartingaleLevels` (default 20 hard cap in loop)
- Old trades are only those opened before today's midnight (not from current session)
- Only market orders (type <= OP_SELL) are considered; pending orders are skipped

## Cross-References

- [[wiki/entities/order-persistence|OrderPersistence]] — Implementation
- [[wiki/concepts/martingale-recovery|Martingale Recovery]] — General martingale recovery concept
- [[wiki/entities/corderops|COrderOps]] — Order access wrapper
