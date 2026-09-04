---
type: architecture
architecture_type: "dependency_graph"
language: "mql5"
title: "Module Namespace Architecture"
tags:
  - architecture
  - modules
  - namespaces
  - dependency-graph
related:
  - "wiki/concepts/module-contribution-guide"
  - "wiki/concepts/module-guard-macros"
  - "wiki/sources/standards-md"
created: 2026-08-18
updated: 2026-08-18
---

# Module Namespace Architecture

Module dependency graph and namespace conventions for the MT5 algorithmic trading suite.

## Namespace Hierarchy

```
core/                    ← Sink rule: no dependencies
├── Logger
├── Utilities
└── CGlobalEventBus

trading/
├── OrderOps
└── TradeManagement

risk/
├── RiskManagement
└── PropFirmRisk

filters/
├── SessionFilter
└── NewsFilter

strategy/
├── SignalAggregation
└── MultiTimeframe

regime/
├── HTFRegimeGate
└── SubscoreWeighting

recovery/
└── RecoveryStrategies

indicators/
└── IndicatorPatterns

ew/
├── EWCore
└── EWFibonacci

_portability/           ← Informational only
_meta/                  ← Library metadata
```

## Dependency Rules

1. **Sink rule**: `core/` modules must have no dependencies
2. **Forward dependency**: Modules can only depend on modules in namespaces listed before them in the hierarchy
3. **No cycles**: Include graph must be cycle-free
4. **Tier encoding**: A (pure MQL5) → B (standard library) → C (DLL imports) → D (platform-specific)

## Module File Structure

- Location: `src5/shared/modules/<ns>/<Name>.mqh`
- Guard macro: `__SRC5_<NS>_<NAME>_MQH__`
- Header block with Version, Status, Namespace, Tier, Dependencies, Description, PORTABILITY
