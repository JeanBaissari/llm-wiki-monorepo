---
type: concept
confidence: high
contested: false
implemented_by:
  - "order-persistence"
related:
  - "order-persistence"
  - "cglobaleventbus"
  - "state-persistence"
  - "globalvariable-ipc-pattern"
sources:
  - "raw/src5/trading/OrderPersistence.mqh"
created: 2026-08-17
updated: 2026-08-17
---

# GV State Persistence Pattern

Persists EA runtime state across restarts using GlobalVariable publish/subscribe via CGlobalEventBus.

## Definition

Stateful EAs (martingale, grid) need to remember recovery level, lot size, direction, and daily accounting state across terminal restarts. The GV persistence pattern uses `CGlobalEventBus` to publish double values with a namespaced key prefix.

## Key Naming Convention

```
"GV.EA_<Symbol>_<MagicNumber>_<FieldName>"
```

Example: `GV.EA_XAUUSD.12345_RecoveryLevel`

## Persisted Fields

| Field | Key Suffix | Type | Description |
|-------|-----------|------|-------------|
| Recovery Level | `RecoveryLevel` | double (cast to int) | Current martingale level |
| Recovery Lot | `RecoveryLot` | double | Next lot size to trade |
| Recovery Direction | `RecoveryDir` | double (cast to int) | 1=buy, -1=sell, 0=both |
| Day Start Balance | `DayStartBalance` | double | Balance at start of day |
| Peak Equity | `PeakEquity` | double | Highest equity seen today |

## Save/Load Flow

```
SaveStateToGlobal():
  for each field:
    CGlobalEventBus::PublishDouble(key, "value", value)

LoadStateFromGlobal():
  if key exists (ReadPersisted returns true):
    ReadPersisted → ParseDouble → cast to target type
```

## Limitations

- **Double-only storage**: All values stored as doubles; integers require casting
- **No versioning**: No schema version; field additions require backward-compatible reads
- **Prefix coupling**: Key prefix depends on `_Symbol` and `inp_MagicNumber` — if these change, state is orphaned
- **Read-modify-read pattern**: `LoadStateFromGlobal` reads each field twice (first to check existence, then to parse); redundant I/O

## Cross-References

- [[wiki/entities/order-persistence|OrderPersistence]] — Implementation
- [[wiki/entities/cglobaleventbus|CGlobalEventBus]] — Persistence layer
- [[wiki/concepts/state-persistence|State Persistence]] — General state persistence concept
- [[wiki/concepts/gv-state-persistence|GV State Persistence]] — Related GV pattern
