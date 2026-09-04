---
type: concept
title: "Module Contribution Guide"
confidence: high
contested: false
implemented_by:
  - "wiki/entities/mt5-algo-suite"
tags:
  - modules
  - contribution
  - shared-modules
related:
  - "wiki/concepts/mql5-coding-standards"
  - "wiki/concepts/module-guard-macros"
  - "wiki/sources/standards-md"
created: 2026-08-18
updated: 2026-08-18
---

# Module Contribution Guide

When to add shared modules, module template, and contribution workflow.

## When to Add a Shared Module

A new shared module should be added to `src5/shared/modules/` when:
- The same utility function or struct is needed by 2+ EAs or indicators
- The logic encapsulates a domain concept that belongs in a single canonical location
- The function has a well-defined interface, no side effects, and no EA-specific state

Do **not** promote a module to `src5/shared/modules/` if:
- It is used by only one EA (keep it EA-local under `includes/`)
- It has not been validated in backtesting
- Its interface is still in flux

## Module Template

```mql5
//+------------------------------------------------------------------+
//| ModuleName.mqh                                                    |
//| Version: 1.00    Status: Draft                                    |
//| Namespace: <ns>  Tier: A                                         |
//| Dependencies: core/Logger                                         |
//| Description: One-line description of what this module does         |
//| PORTABILITY: MQL5-only | Cross-platform | Wine+x64 required        |
//+------------------------------------------------------------------+
#ifndef __SRC5_<NS>_<NAME>_MQH__
#define __SRC5_<NS>_<NAME>_MQH__
#property strict

// --- Includes ---
#include "core/Logger.mqh"

// --- Constants ---
#define MODULE_VERSION "1.00"

// --- Structs ---

// --- Global Variables (module scope, no extern) ---

// --- Functions ---

#endif
```

## Contribution Workflow

1. **Propose**: Open a discussion with the module spec (name, namespace, public API, dependencies)
2. **Review**: `shared_module_steward` runs header compliance, dependency graph check, and portability audit
3. **Approve**: Verdict of PASS with `Version: 1.00`, dependency declarations confirmed
4. **Commit**: Module file created under `src5/shared/modules/<ns>/<Name>.mqh`
5. **Index**: MODULES_INDEX.md regenerated
6. **Consume**: EA owner copies module into EA's `includes/modules/<ns>/<Name>.mqh`

## Namespace Conventions

| Namespace | Purpose | Example Modules |
|-----------|---------|----------------|
| `core/` | Logging, math, time helpers | `Logger`, `Utilities` |
| `trading/` | Order execution, position tracking | `OrderOps`, `TradeManagement` |
| `risk/` | Position sizing, drawdown gates | `RiskManagement`, `PropFirmRisk` |
| `filters/` | Market condition gating | `SessionFilter`, `NewsFilter` |
| `strategy/` | Signal composition, MTF, validation | `SignalAggregation`, `MultiTimeframe` |
| `regime/` | Market regime classification | `HTFRegimeGate`, `SubscoreWeighting` |
| `recovery/` | Recovery/hedge strategy dispatchers | `RecoveryStrategies` |
| `indicators/` | Indicator-side helpers and adapters | `IndicatorPatterns` |
| `ew/` | Elliott Wave domain modules | `EWCore`, `EWFibonacci` |
| `_portability/` | Cross-platform reference (informational) | `README.md` |
| `_meta/` | Library-level metadata | `version.mqh` |
