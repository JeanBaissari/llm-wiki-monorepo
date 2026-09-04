---
type: entity
language: mql5
namespace: trading
status: active
version: "1.00"
tags:
  - state-recovery
  - martingale
  - grid
  - persistence
  - restart
  - globalvariable
related:
  - "order-ops"
  - "corderops"
  - "global-variable-ipc-pattern"
  - "martingale-recovery"
  - "grid-level-reconstruction"
  - "partial-close-ticket-tracking"
  - "old-trade-detection"
  - "basket-breakeven-detection"
  - "cglobaleventbus"
sources:
  - "raw/src5/trading/OrderPersistence.mqh"
created: 2026-08-17
updated: 2026-08-17
---

# OrderPersistence

Recovery primitives for stateful EAs that restart mid-cycle. Provides state reconstruction from open orders and global variable persistence.

## Purpose

When a stateful EA (martingale, grid, basket) restarts — due to terminal restart, deinitialization, or recompilation — it loses all runtime state. OrderPersistence rebuilds that state from two sources:

1. **Open orders** — scan existing positions to reconstruct martingale levels, grid geometry, and partial close history
2. **Global variables** — persist daily state (recovery level, lot, direction, peak equity) across restarts via `CGlobalEventBus`

## Module Structure

```
OrderPersistence.mqh
├── Section 1: Martingale Recovery Level Detection (ScanRecoveryState)
├── Section 2: Grid Level Reconstruction (ReconstructGridLevels, GetNextGridLevel)
├── Section 3: Partial Close Tracking (IsPartialClosedTicket, AddPartialClosedTicket)
├── Section 4: Daily State Persistence (SaveStateToGlobal, LoadStateFromGlobal)
├── Section 5: Old Trade Detection (IsOldTrade, CountOldTrades)
└── Section 6: Basket Breakeven Detection (IsBasketAtBreakeven)
```

## Dependencies

| Dependency | Type | Purpose |
|-----------|------|---------|
| trading/COrderOps | Include | Order selection and data access wrapper |
| core/Utilities | Include | Utility functions (ToPips, LogInfo) |
| core/GlobalEventBus | Include | Global variable persistence layer |

## Key Functions

### `ScanRecoveryState()`
Detects if EA is in recovery mode by scanning open orders. Finds the maximum lot size among old trades (opened before today), then calculates the current martingale level by iteratively multiplying `inp_LotSize * inp_LotMultiplier`. Sets `g_inRecovery`, `g_recoveryLevel`, `g_recoveryLot`, and `g_recoveryDir`.

### `ReconstructGridLevels()`
Rebuilds grid state from open orders. Collects all open prices, sorts them, and computes average spacing in pips. Populates `g_gridLevels[]`, `g_gridCount`, and `g_gridSpacing`.

### `GetNextGridLevel(bool isBuy)`
Returns the next grid entry price. For buys: lowest grid level minus spacing. For sells: highest grid level plus spacing.

### `IsPartialClosedTicket(int ticket)` / `AddPartialClosedTicket(int ticket)`
Session-persistent tracking of which tickets have been partially closed. Prevents double partial closes within a session. State lives in `g_partialClosedTickets[]` array.

### `SaveStateToGlobal()` / `LoadStateFromGlobal()`
Persists and restores EA state via `CGlobalEventBus` publish/subscribe. Saves: `g_recoveryLevel`, `g_recoveryLot`, `g_recoveryDir`, `g_dayStartBalance`, `g_peakEquity`.

### `IsOldTrade(int ticket)` / `CountOldTrades(int magic)`
Detects orders opened before today's midnight. Used for recovery detection and trade counting.

### `IsBasketAtBreakeven(int magic)`
Checks if all open orders have stop loss within 5 points of open price (breakeven zone).

### `ApplyPartialClose(int magic)`
Orchestrator that scans open orders, checks profit against `inp_PartialCloseTP1Pips`, and closes `inp_PartialClosePct`% of volume for qualifying orders.

## Input Parameters (EA-level)

| Parameter | Purpose |
|-----------|---------|
| `inp_MagicNumber` | EA magic number filter |
| `inp_LotSize` | Base lot size |
| `inp_LotMultiplier` | Martingale multiplier |
| `inp_MaxMartingaleLevels` | Maximum recovery levels |
| `inp_LockRecoveryDirection` | Lock to buy/sell direction during recovery |
| `inp_GridSpacingPips` | Grid spacing in pips |
| `inp_PartialCloseTP1Pips` | TP threshold for partial close (pips) |
| `inp_PartialClosePct` | Percentage of volume to close |

## Usage

```mql5
#include "includes/modules/trading/OrderPersistence.mqh"

int OnInit()
{
    LoadStateFromGlobal();
    ScanRecoveryState();
    ReconstructGridLevels();
    return INIT_SUCCEEDED;
}
```

## Known Issues

1. **Tight EA coupling** — References EA-level inputs and globals directly; not parameterized via function arguments
2. **Missing dependency** — `CalculateProfitPips()` is referenced but not provided; EA responsibility
3. **Linear partial close scan** — `IsPartialClosedTicket` uses O(n) linear search; no deduplication on `AddPartialClosedTicket`
4. **Grid spacing from sorted array** — Averages spacing across all levels; uneven grids produce incorrect estimates

## Portability

- **MQL5** — Uses `COrderOps` wrapper for `OrdersTotal`, `PositionGetTicket`, `OrderGetTicket`
- File I/O and `GlobalVariable*` APIs are identical between MQL4 and MQL5
- State reconstruction logic is portable; only the order access layer differs

## Cross-References

- [[wiki/entities/corderops|COrderOps]] — Order access wrapper used by OrderPersistence
- [[wiki/entities/cglobaleventbus|CGlobalEventBus]] — Persistence layer for GV state
- [[wiki/concepts/gv-state-persistence|GV State Persistence]] — Pattern used for state across restarts
- [[wiki/concepts/martingale-recovery|Martingale Recovery]] — Recovery level detection concept
- [[wiki/concepts/grid-level-reconstruction|Grid Level Reconstruction]] — Grid rebuild from open orders
