---
type: concept
title: "Trade Operations (CTrade)"
confidence: high
contested: false
implemented_by:
  - "wiki/entities/mt5-algo-suite"
tags:
  - mql5
  - trade
  - ctrade
  - order-management
related:
  - "wiki/concepts/mql5-coding-standards"
  - "wiki/concepts/ontrade-transaction-lifecycle"
  - "wiki/sources/standards-md"
created: 2026-08-18
updated: 2026-08-18
---

# Trade Operations (CTrade)

MQL5 provides `CTrade` for position management. All EAs must use `CTrade` (or a wrapper that delegates to it). Never use the raw `OrderSend` API.

## Implementation

```mql5
#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

CTrade       g_trade;
CPositionInfo g_position;

void SendBuy(double volume) {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double sl  = ask - inp_StopLossPoints * _Point;
   double tp  = ask + inp_TakeProfitPoints * _Point;

   if (g_trade.Buy(volume, _Symbol, ask, sl, tp)) {
      Print("Buy opened, ticket: ", g_trade.ResultOrder());
   } else {
      Print("Buy failed: ", g_trade.ResultRetcodeDescription());
   }
}

void CloseAll() {
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong ticket = PositionGetTicket(i);
      if (PositionSelectByTicket(ticket)) {
         if (PositionGetString(POSITION_SYMBOL) == _Symbol) {
            g_trade.PositionClose(ticket);
         }
      }
   }
}
```

## Rules

1. `#include <Trade/Trade.mqh>` present
2. `CTrade` instance declared (global or member)
3. No direct `OrderSend()` calls anywhere in the codebase
4. After every `PositionOpen`, `PositionClose`, `OrderOpen`, `OrderDelete`:
   - `g_trade.ResultRetcode() == TRADE_RETCODE_DONE` verified
   - Failure logged with `ResultRetcodeDescription()`

## Why Not Raw OrderSend

- MT5's OrderSend API is complex and error-prone
- CTrade handles retry logic, slippage, and error reporting
- Consistent error handling across all EAs
