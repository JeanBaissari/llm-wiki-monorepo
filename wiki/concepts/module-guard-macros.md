---
type: concept
title: "Module Guard Macros"
confidence: high
contested: false
implemented_by:
  - "wiki/entities/mt5-algo-suite"
tags:
  - mql5
  - guard-macros
  - include-files
related:
  - "wiki/concepts/mql5-coding-standards"
  - "wiki/sources/standards-md"
created: 2026-08-18
updated: 2026-08-18
---

# Module Guard Macros

Every `.mqh` file must use the guard macro format `__SRC5_<NAMESPACE>_<MODULE>_MQH__`.

## Format

```
__SRC5_<NAMESPACE>_<MODULE>_MQH__
```

- All uppercase
- Namespace and module name separated by single underscores
- Examples:
  - `__SRC5_CORE_LOGGER_MQH__`
  - `__SRC5_TRADING_ORDEROPS_MQH__`
  - `__SRC5_RISK_RISKMANAGEMENT_MQH__`

## Implementation

The guard is `#define`d on line 1 after the file header block, and the entire file body is wrapped in `#ifndef` / `#endif`:

```mql5
//+------------------------------------------------------------------+
//| Logger.mqh                                                        |
//+------------------------------------------------------------------+
#ifndef __SRC5_CORE_LOGGER_MQH__
#define __SRC5_CORE_LOGGER_MQH__
#property strict
// ... module body ...
#endif
```

## Purpose

- Prevents double-inclusion in the include graph
- Ensures include graph is cycle-free
- Required for all `.mqh` files (checkpoint 10 in EA code review)
