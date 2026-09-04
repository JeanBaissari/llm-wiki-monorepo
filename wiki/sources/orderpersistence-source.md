---
type: source
title: OrderPersistence Source
authors: ["Baissari Enterprises"]
year: 2026
url: ""
venue: ""
tags: [trading, state-recovery, martingale, grid, mql5, source]
related:
  - "order-persistence"
created: 2026-08-17
updated: 2026-08-17
---

# OrderPersistence Source

Source file for the OrderPersistence recovery module.

## File

`raw/src5/trading/OrderPersistence.mqh`

## Version History

| Version | Date | Notes |
|---------|------|-------|
| 1.00 | 2026-08-17 | Initial version |

## Key Functions

| Function | Purpose |
|----------|---------|
| `ScanRecoveryState` | Detect martingale level from open order lot sizes |
| `ReconstructGridLevels` | Rebuild grid from open order prices |
| `GetNextGridLevel` | Calculate next grid entry price |
| `IsPartialClosedTicket` | Check if ticket was already partially closed |
| `AddPartialClosedTicket` | Mark ticket as partially closed |
| `ApplyPartialClose` | Orchestrate partial close for qualifying orders |
| `SaveStateToGlobal` | Persist state via CGlobalEventBus |
| `LoadStateFromGlobal` | Restore state on EA restart |
| `IsOldTrade` | Check if order opened before today |
| `CountOldTrades` | Count old orders per magic |
| `IsBasketAtBreakeven` | Check if all orders have SL at breakeven |

## External Dependencies

- `trading/COrderOps.mqh` — Order selection and data access
- `core/Utilities.mqh` — Utility functions (ToPips, LogInfo)
- `core/GlobalEventBus.mqh` — Global variable persistence layer
