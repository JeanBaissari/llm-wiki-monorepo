---
type: concept
confidence: high
contested: false
implemented_by:
  - "ew-auto-tp"
related:
  - "auto-tp-adjustment"
  - "ind-ew-fibengine"
  - "extension-detection"
sources:
  - "raw/src5/shared/modules/ew/EWAutoTP.mqh"
created: 2026-08-17
updated: 2026-08-17
---

# Fibonacci Extension Ladder

Progressive take-profit stepping through Fibonacci extension levels: 161.8% → 261.8% → 423.6%.

## Definition

The TP ladder upgrades the take-profit target to the next Fibonacci extension level as Wave 3 extends beyond expectations. Each step occurs when price approaches the current target (within a 5% proximity buffer).

## Ladder Progression

| Step | Level | Condition | Action |
|------|-------|-----------|--------|
| 1 | 161.8% | Initial target | Set by entry logic |
| 2 | 261.8% | Current TP ≤ tp161 + eps | Upgrade to tp261 |
| 3 | 423.6% | Current TP ≤ tp261 + eps | Upgrade to tp423 |

The 423.6% target is derived from the 161.8%/261.8% pair:

```
legSize = tp261 - tp161
tp423 = tp161 + 2.618 * legSize
```

This formula is direction-agnostic (works for both buy and sell orders).

## Bearish Ladder

For sell orders, the ladder inverts:
- tp161 > tp261 > tp423 (lower prices = larger profit)
- Conditions check `>=` instead of `<=`
- Same mathematical derivation

## Implementation

```mql5
bool AdjustTPLadder(int ticket, int orderType, double tp161, double tp261)
```

Uses `OrderModify()` to update TP while preserving current SL. Normalizes to `_Digits` precision.

## Why These Specific Levels

- **161.8%** — Standard Fibonacci extension, common Wave 3 target
- **261.8%** — Extended Wave 3, strong momentum continuation
- **423.6%** — Rare but significant extension, only on exceptional moves

## Cross-References

- [[wiki/concepts/auto-tp-adjustment|Auto-TP Adjustment]] — Parent orchestration
- [[wiki/concepts/extension-detection|Extension Detection]] — When to trigger ladder step
- [[wiki/entities/ind-ew-fibengine|Ind_EW_FibEngine]] — Source of Fibonacci price levels
- [[wiki/entities/ew-auto-tp|EWAutoTP]] — Implementation
