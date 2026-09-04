---
type: concept
title: "EA Code Review Checklist"
confidence: high
contested: false
implemented_by:
  - "wiki/entities/mt5-algo-suite"
tags:
  - code-review
  - quality-gates
  - ea-development
related:
  - "wiki/concepts/mql5-coding-standards"
  - "wiki/concepts/module-guard-macros"
  - "wiki/concepts/indicator-buffer-rules"
  - "wiki/concepts/price-symbol-access-rules"
  - "wiki/concepts/icustom-handle-pattern"
  - "wiki/concepts/trade-operations-ctrade"
  - "wiki/concepts/input-validation-oninit"
  - "wiki/concepts/ontrade-transaction-lifecycle"
  - "wiki/sources/standards-md"
created: 2026-08-18
updated: 2026-08-18
---

# EA Code Review Checklist

12-point validation checklist that must pass before any EA leaves Phase 3 (development).

## Checklist

### 1. All iCustom handles cached in OnInit
- [ ] Every `iCustom` call is in `OnInit`, not `OnTick`
- [ ] Each handle is stored in a `int g_*Handle` global variable
- [ ] Handle validity checked: `== INVALID_HANDLE`, returning `INIT_FAILED`
- [ ] All handles released in `OnDeinit` via `IndicatorRelease()`

### 2. All CopyBuffer calls check return value
- [ ] Every `CopyBuffer` call checks `< countNeeded`
- [ ] Early return on failure, not silent continuation

### 3. CTrade or COrderOps used (no raw OrderSend)
- [ ] `#include <Trade/Trade.mqh>` present
- [ ] `CTrade` instance declared (global or member)
- [ ] No direct `OrderSend()` calls anywhere in the codebase

### 4. PositionGetTicket/PositionSelectByTicket used (no OrderSelect loops)
- [ ] Position iteration uses `for (i = PositionsTotal()-1; i >= 0; i--)`
- [ ] `PositionGetTicket(i)` for position access
- [ ] `PositionSelectByTicket(ticket)` before reading `PositionGet*()`
- [ ] No `OrderSelect` or `OrdersTotal` calls

### 5. Every CTrade call checks ResultRetcode()
- [ ] After every `PositionOpen`, `PositionClose`, `OrderOpen`, `OrderDelete`:
- [ ] `g_trade.ResultRetcode() == TRADE_RETCODE_DONE` verified
- [ ] Failure logged with `ResultRetcodeDescription()`

### 6. All inputs validated in OnInit returning INIT_PARAMETERS_INCORRECT
- [ ] Magic number validated: positive integer, not default test value
- [ ] Risk percentage: within 1-100 range
- [ ] Stop loss / take profit: minimum distance respected
- [ ] Lot size: respects `MODE_MINLOT`, `MODE_MAXLOT`, `MODE_LOTSTEP`
- [ ] Any invalid parameter returns `INIT_PARAMETERS_INCORRECT`

### 7. OnTradeTransaction implemented for trade lifecycle
- [ ] `OnTradeTransaction` handler present in EA
- [ ] Handles at minimum `TRADE_TRANSACTION_ORDER_ADD` and `TRADE_TRANSACTION_DEAL_ADD`
- [ ] Trade tracking updates in response to transaction events

### 8. Magic number is not default test value
- [ ] `inp_Magic != 900001` (the test value)
- [ ] Magic number logged at `OnInit`
- [ ] Warning emitted if magic number is the default

### 9. #property strict present
- [ ] `#property strict` exists in the main `.mq5` file
- [ ] `#property strict` exists in every `.mqh` file (after guard `#define`)

### 10. Guard macros on all #include files
- [ ] Every `.mqh` file has a `__SRC5_<NS>_<NAME>_MQH__` guard
- [ ] No double-inclusion possible in the include graph
- [ ] `#include` graph is cycle-free

### 11. PORTABILITY block in each module
- [ ] Every `.mqh` has a non-trivial `PORTABILITY:` line in its header
- [ ] MQL5-specific APIs documented with MT4 alternatives (where relevant)
- [ ] No "TODO" or placeholder portability notes

### 12. No MQL4 API calls
- [ ] No `OrderSend`, `OrderModify`, `OrderClose`, `OrderSelect`, `OrdersTotal`, `OrderDelete`
- [ ] No `iClose`, `iOpen`, `iHigh`, `iLow`, `iVolume`, `iTime`
- [ ] No `Ask`, `Bid`, `Point`, `Digits` globals
- [ ] No `SetIndexStyle`, `SetIndexBuffer` without explicit type flag
- [ ] No `MarketInfo` — use `SymbolInfoDouble`/`SymbolInfoInteger` instead

## Enforcement

- Enforced by `ea_reviewer` agent
- Required before EA leaves Phase 3 (development)
- Part of the workflow_orchestrator gate process
