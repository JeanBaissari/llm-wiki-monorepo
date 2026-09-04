---
type: entity
language: mql5
namespace: "trading"
status: "active"
version: "1.00"
dependencies: []
title: "CTrade"
tags:
  - mql5
  - trading
  - order-management
  - standard-library
related:
  - "wiki/concepts/trade-operations-ctrade"
  - "wiki/concepts/mql5-coding-standards"
  - "wiki/concepts/ea-code-review-checklist"
sources:
  - "wiki/sources/standards-md"
created: 2026-08-18
updated: 2026-08-18
---

# CTrade

MQL5 standard library class for position management. All EAs must use CTrade (or a wrapper that delegates to it).

## Purpose

- Wraps MT5's order execution API
- Handles retry logic, slippage, and error reporting
- Provides consistent error handling across all EAs
- Required by EA code review checkpoint 3

## Key Methods

- `Buy(volume, symbol, price, sl, tp)` — Open buy position
- `Sell(volume, symbol, price, sl, tp)` — Open sell position
- `PositionClose(ticket)` — Close position
- `ResultRetcode()` — Get last operation return code
- `ResultRetcodeDescription()` — Get human-readable error description

## Usage Pattern

```mql5
#include <Trade/Trade.mqh>

CTrade g_trade;

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
```

## Anti-patterns

- Never use raw `OrderSend()` — use CTrade
- Never ignore `ResultRetcode()` after order operations
- Never skip error logging with `ResultRetcodeDescription()`
