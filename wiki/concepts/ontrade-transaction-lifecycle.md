---
type: concept
title: "OnTradeTransaction Lifecycle"
confidence: high
contested: false
implemented_by:
  - "wiki/entities/mt5-algo-suite"
tags:
  - mql5
  - trade-lifecycle
  - ontrade-transaction
related:
  - "wiki/concepts/mql5-coding-standards"
  - "wiki/concepts/trade-operations-ctrade"
  - "wiki/sources/standards-md"
created: 2026-08-18
updated: 2026-08-18
---

# OnTradeTransaction Lifecycle

MT5 requires `OnTradeTransaction` to track order lifecycle events (pending order activation, modification, deletion). All EAs that use pending orders or need to react to order state changes must implement this handler.

## Implementation

```mql5
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result) {
   switch (trans.type) {
      case TRADE_TRANSACTION_ORDER_ADD:
         // Order added to the queue
         break;
      case TRADE_TRANSACTION_ORDER_DONE:
         // Pending order activated as position
         break;
      case TRADE_TRANSACTION_POSITION:
         // Position modified (SL/TP change)
         break;
      case TRADE_TRANSACTION_DEAL_ADD:
         // Deal added (partial fill, etc.)
         break;
   }
}
```

## Required Transaction Types

- `TRADE_TRANSACTION_ORDER_ADD` — Order added to queue
- `TRADE_TRANSACTION_ORDER_DONE` — Pending order activated
- `TRADE_TRANSACTION_POSITION` — Position modified
- `TRADE_TRANSACTION_DEAL_ADD` — Deal added

## Purpose

- Tracks order lifecycle events that occur asynchronously
- Enables reaction to pending order activation
- Supports partial fill handling
- Required for EA code review checkpoint 7
