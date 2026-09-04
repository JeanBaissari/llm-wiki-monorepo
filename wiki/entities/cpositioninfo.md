---
type: entity
language: mql5
namespace: "trading"
status: "active"
version: "1.00"
dependencies: []
title: "CPositionInfo"
tags:
  - mql5
  - trading
  - position-info
  - standard-library
related:
  - "wiki/entities/ctrade"
  - "wiki/concepts/trade-operations-ctrade"
  - "wiki/concepts/mql5-coding-standards"
sources:
  - "wiki/sources/standards-md"
created: 2026-08-18
updated: 2026-08-18
---

# CPositionInfo

MQL5 standard library class for reading position properties. Used alongside CTrade for position management.

## Purpose

- Read position properties (symbol, volume, SL, TP, profit, etc.)
- Iterate over open positions
- Required by EA code review checkpoint 4

## Key Methods

- `SelectByTicket(ticket)` — Select position by ticket
- `GetString(property)` — Get string property
- `GetDouble(property)` — Get double property
- `GetInteger(property)` — Get integer property

## Usage Pattern

```mql5
#include <Trade/PositionInfo.mqh>

CPositionInfo g_position;

void CloseAll() {
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong ticket = PositionGetTicket(i);
      if (g_position.SelectByTicket(ticket)) {
         if (g_position.GetString(POSITION_SYMBOL) == _Symbol) {
            g_trade.PositionClose(ticket);
         }
      }
   }
}
```

## Anti-patterns

- Never use `OrderSelect` or `OrdersTotal` loops — use PositionGetTicket
- Always call `SelectByTicket` before reading position properties
- Always iterate positions in reverse order ( PositionsTotal()-1 to 0)
