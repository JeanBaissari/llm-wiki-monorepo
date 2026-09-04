---
type: concept
title: "MQL5 Coding Standards"
confidence: high
contested: false
implemented_by:
  - "wiki/entities/mt5-algo-suite"
  - "wiki/entities/mt4-algo-suite"
tags:
  - mql5
  - coding-standards
  - naming-conventions
related:
  - "wiki/sources/standards-md"
  - "wiki/concepts/module-guard-macros"
  - "wiki/concepts/indicator-buffer-rules"
  - "wiki/concepts/price-symbol-access-rules"
created: 2026-08-18
updated: 2026-08-18
---

# MQL5 Coding Standards

Professional coding standards for the MT5 algorithmic trading suite.

## Naming Conventions

| Element | Convention | Example | Rationale |
|---------|------------|---------|-----------|
| Classes | `C` prefix, PascalCase | `COrderOps`, `CGlobalEventBus`, `CHTFComposite` | Distinguishes classes from structs and primitives |
| Class members | `m_` prefix, camelCase | `m_handle`, `m_symbol`, `m_lastBar` | Prevents shadowing with function params and globals |
| Global variables | `g_` prefix, camelCase | `g_fvgBuf`, `g_riskPercent` | Visually distinct; easy to grep all global state |
| Input parameters | `inp_` prefix, PascalCase | `inp_Magic`, `inp_RiskPercent` | Standard MT5 practice; immediately identifiable |
| Constants | `UPPER_SNAKE_CASE` | `MAX_POSITIONS`, `DEFAULT_MAGIC` | Universal convention for immutable values |
| Functions | `PascalCase` | `GetSignal`, `ValidateEntry`, `CalculateATR` | MQL5 standard library convention |
| Files | PascalCase with prefix | `EA_XAUSwinger.mq5`, `Ind_EW_SwingEngine.mq5` | Prefix encodes domain for sorting |

## Key Rules

1. **MQL5-native code required** — not MQL4 compatibility mode
2. **Guard macros mandatory** on all `.mqh` files
3. **Canonical header block** on every `.mq5` and `.mqh` file
4. **Explicit buffer types** for all indicator buffers
5. **SymbolInfoDouble/Integer** instead of Ask/Bid/Point/Digits globals
6. **Handle-based iCustom** pattern for indicator access
7. **CTrade** for all order operations — no raw OrderSend
8. **Input validation** in OnInit returning INIT_PARAMETERS_INCORRECT
9. **OnTradeTransaction** for trade lifecycle tracking

## MQL4 Anti-patterns to Avoid

| MQL4 Anti-pattern | MQL5 Correct Pattern |
|-------------------|---------------------|
| `Ask` | `SymbolInfoDouble(_Symbol, SYMBOL_ASK)` |
| `Bid` | `SymbolInfoDouble(_Symbol, SYMBOL_BID)` |
| `Point` | `SymbolInfoDouble(_Symbol, SYMBOL_POINT)` |
| `Digits` | `(int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS)` |
| `iClose(sym, tf, shift)` | `CopyClose(sym, tf, shift, 1, buf)` |
| `OrderSend(...)` | `CTrade::PositionOpen(...)` |
| `OrderSelect/OrdersTotal` loop | `PositionGetTicket(i)` or `CPositionInfo` |
