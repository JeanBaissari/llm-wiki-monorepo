---
type: concept
confidence: high
contested: false
implemented_by:
  - "ew-auto-tp"
related:
  - "auto-tp-adjustment"
  - "ind-ew-wavelabeler"
  - "ind-ew-confirmationengine"
  - "kennedy-channel-trailing-stop"
sources:
  - "raw/src5/shared/modules/ew/EWAutoTP.mqh"
created: 2026-08-17
updated: 2026-08-17
---

# Wave Exhaustion Exit

Emergency close of all magic-scoped orders when wave exhaustion conditions are met: completion probability > 80 AND divergence signal != 0.

## Definition

Wave exhaustion exit is a safety mechanism that closes all open orders for a given magic number when the wave is nearly complete AND a divergence signal is present. This prevents holding through a potential reversal.

## Exhaustion Criteria

Both conditions must be true simultaneously:

1. **Completion > 80** — From WaveLabeler Buffer 7 (`EW_WL_COMPLETION_P`). Indicates the current wave is ≥80% complete.
2. **Divergence != 0** — From ConfirmationEngine Buffer 3 (`CE_BUF_DIVERGENCE`). Any non-zero value indicates bearish or bullish divergence.

The AND logic is critical — high completion alone does not trigger exit (waves can extend). Divergence alone does not trigger exit (divergence can resolve). Only the combination signals genuine exhaustion.

## Execution Flow

```
CheckExhaustionExit()
├── Read completion from WaveLabeler Buffer 7
├── Read divergence from ConfirmationEngine Buffer 3
├── if completion == EMPTY_VALUE: return false
├── if divergence == EMPTY_VALUE: return false
├── if completion <= 80: return false
├── if divergence == 0: return false
└── Close all orders for this magic number + symbol
```

## Close Behavior

- Iterates all open orders in reverse order
- Filters by magic number AND current symbol
- Uses `OrderClose()` with 3-point slippage
- Logs errors for failed closes
- Returns true if at least one order was closed

## Gating Effect

When exhaustion exit fires, it returns `true` and `ManageAutoTP()` returns immediately — skipping all TP ladder and Kennedy trailing logic for that bar. This is intentional: if the wave is exhausting, adjusting TP targets is pointless.

## Canonical References

- FAQ 27 (extensions)
- FAQ 34 (until support breaks)
- ew_canonical_rules.md Part 5 (Kennedy)

## Cross-References

- [[wiki/concepts/auto-tp-adjustment|Auto-TP Adjustment]] — Parent orchestration
- [[wiki/entities/ind-ew-wavelabeler|Ind_EW_WaveLabeler]] — Source of completion probability
- [[wiki/entities/ind-ew-confirmationengine|Ind_EW_ConfirmationEngine]] — Source of divergence signal
- [[wiki/entities/ew-auto-tp|EWAutoTP]] — Implementation
