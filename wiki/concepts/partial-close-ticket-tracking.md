---
type: concept
confidence: high
contested: false
implemented_by:
  - "order-persistence"
related:
  - "order-persistence"
  - "partial-close-forced-be"
  - "corderops"
sources:
  - "raw/src5/trading/OrderPersistence.mqh"
created: 2026-08-17
updated: 2026-08-17
---

# Partial Close Ticket Tracking

Session-persistent tracking of which tickets have been partially closed to prevent double partial closes.

## Definition

When an EA applies partial close at a TP level, it must remember which tickets have already been partially closed to avoid closing them again on subsequent ticks. This tracking persists for the session (via in-memory array) and is used by `ApplyPartialClose()`.

## Functions

### `IsPartialClosedTicket(int ticket)`
Linear scan of `g_partialClosedTickets[]` array. Returns true if ticket is found.

### `AddPartialClosedTicket(int ticket)`
Appends ticket to `g_partialClosedTickets[]`. Resizes array by 1 each call.

## Partial Close Flow

```
ApplyPartialClose(magic)
├── for each open order (reverse scan):
│   ├── skip if not this magic/symbol
│   ├── skip if not market order
│   ├── skip if already partial-closed (IsPartialClosedTicket)
│   ├── calculate profit pips (CalculateProfitPips — EA-provided)
│   ├── skip if profit < inp_PartialCloseTP1Pips
│   ├── lotsToClose = volume * (inp_PartialClosePct / 100.0)
│   ├── [OrderClose logic — EA-provided]
│   └── AddPartialClosedTicket(ticket)
```

## Limitations

- **O(n) lookup**: Linear scan per order; no hash set or bitmap
- **Unbounded growth**: Array grows by 1 each call; never shrunk or cleaned
- **No deduplication check**: `AddPartialClosedTicket` does not check if ticket already exists before adding
- **Session-only**: State is not persisted via GV; lost on EA restart (reconstructed only if orders are still open)

## Cross-References

- [[wiki/entities/order-persistence|OrderPersistence]] — Implementation
- [[wiki/concepts/partial-close-forced-be|Partial Close Forced BE]] — Related partial close concept
- [[wiki/entities/corderops|COrderOps]] — Order access wrapper
