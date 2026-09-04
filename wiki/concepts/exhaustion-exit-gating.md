---
type: concept
confidence: high
contested: false
implemented_by:
  - "ew-auto-tp"
related:
  - "auto-tp-adjustment"
  - "wave-exhaustion-exit"
sources:
  - "raw/src5/shared/modules/ew/EWAutoTP.mqh"
created: 2026-08-17
updated: 2026-08-17
---

# Exhaustion Exit Gating

When wave exhaustion exit fires in Phase 1, all subsequent phases (TP ladder, Kennedy trailing) are skipped for that bar.

## Definition

The exhaustion exit acts as a priority gate in the `ManageAutoTP()` orchestrator:

```mql5
// Phase 1: Check exhaustion exit
if(CheckExhaustionExit(magic, ...))
    return;  // All orders closed — nothing more to do this bar

// Phase 2-3: Only reached if no exhaustion
```

## Why Gate

If all orders are closed due to exhaustion, there is nothing to apply TP ladder or trailing stop to. The `return` statement is a performance optimization and logical correctness guard.

## Execution Priority

1. Exhaustion exit (once per bar, all orders)
2. FibEngine reads (shared across orders)
3. Per-order: Extension detection → TP ladder
4. Per-order: Kennedy trailing stop

The exhaustion check runs first because it can terminate the entire bar's processing.

## Cross-References

- [[wiki/concepts/wave-exhaustion-exit|Wave Exhaustion Exit]] — The gating condition
- [[wiki/concepts/auto-tp-adjustment|Auto-TP Adjustment]] — Orchestration flow
- [[wiki/entities/ew-auto-tp|EWAutoTP]] — Implementation
