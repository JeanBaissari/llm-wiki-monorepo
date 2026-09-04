---
type: architecture
title: OrderPersistence Dependency Graph
architecture_type: dependency_graph
language: mql5
tags: [trading, architecture, dependency-graph, state-recovery]
related:
  - "order-persistence"
  - "corderops"
  - "cglobaleventbus"
created: 2026-08-17
updated: 2026-08-17
---

# OrderPersistence Dependency Graph

Include and sub-module dependency structure for OrderPersistence.mqh.

## Graph

```
OrderPersistence.mqh
├── trading/COrderOps.mqh (include)
│   ├── OrdersTotal() — total open order count
│   ├── Select() — order selection by position/ticket
│   ├── MagicNumber() — EA magic filter
│   ├── Symbol() — symbol filter
│   ├── Type() — order type (OP_BUY/OP_SELL/pending)
│   ├── OpenTime() — order open timestamp
│   ├── OpenPrice() — order open price
│   ├── Volume() — order lot size
│   ├── StopLoss() — order stop loss price
│   └── Ticket() — order ticket number
├── core/Utilities.mqh (include)
│   ├── ToPips() — price to pip conversion
│   └── LogInfo() — structured logging
└── core/GlobalEventBus.mqh (include)
    ├── PublishDouble() — persist double value
    ├── ReadPersisted() — read persisted value
    └── ParseDouble() — parse double from frame
```

## Data Flow

1. **OnInit**: `LoadStateFromGlobal()` reads GV → sets recovery level, lot, direction, daily accounting
2. **OnInit**: `ScanRecoveryState()` scans open orders → computes martingale level from max lot
3. **OnInit**: `ReconstructGridLevels()` collects open prices → sorted grid array + average spacing
4. **OnTick**: `ApplyPartialClose()` checks profit → closes partial volume for qualifying orders
5. **OnDeinit**: `SaveStateToGlobal()` persists current state → ready for next restart

## Coupling Notes

- OrderPersistence reads EA-level inputs directly (`inp_MagicNumber`, `inp_LotSize`, etc.) — tight coupling to consuming EA
- OrderPersistence writes to EA-level globals (`g_inRecovery`, `g_recoveryLevel`, etc.) — bidirectional coupling
- `CalculateProfitPips()` is referenced but not defined in this module — EA responsibility
