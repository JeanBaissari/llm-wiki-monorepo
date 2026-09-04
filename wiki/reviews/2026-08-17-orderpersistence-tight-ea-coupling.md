---
type: review
status: open
severity: warning
entity: order-persistence
created: 2026-08-17
related:
  - "order-persistence"
  - "extern-inputs-in-include"
---

# OrderPersistence — Tight EA Coupling via Direct Input/Globals Access

## Issue

OrderPersistence directly references EA-level input parameters (`inp_MagicNumber`, `inp_LotSize`, `inp_LotMultiplier`, `inp_MaxMartingaleLevels`, `inp_LockRecoveryDirection`, `inp_GridSpacingPips`, `inp_PartialCloseTP1Pips`, `inp_PartialClosePct`) and EA-level global variables (`g_inRecovery`, `g_recoveryLevel`, `g_recoveryLot`, `g_recoveryDir`, `g_gridLevels[]`, `g_gridCount`, `g_gridSpacing`, `g_partialClosedTickets[]`, `g_partialClosedCount`, `g_dayStartBalance`, `g_peakEquity`) at file scope.

## Impact

- Module cannot be reused across different EAs without matching the exact input/global naming convention
- Changing EA parameter names breaks OrderPersistence at compile time
- Multiple EAs including this module would need identical input declarations (duplicate input conflict)
- Bidirectional coupling (reads inputs, writes globals) makes testing and refactoring difficult

## Recommendation

Refactor to accept parameters via function arguments or a configuration struct:

```mql5
struct RecoveryConfig {
    int magicNumber;
    double lotSize;
    double lotMultiplier;
    int maxMartingaleLevels;
    bool lockDirection;
    // ...
};

void ScanRecoveryState(RecoveryConfig &config, RecoveryState &state);
```

This would make the module portable, testable, and reusable across EAs.
