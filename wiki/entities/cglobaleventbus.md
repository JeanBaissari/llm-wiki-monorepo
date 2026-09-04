---
type: entity
language: mql5
namespace: "core"
status: "active"
version: "1.00"
dependencies: []
title: "CGlobalEventBus"
tags:
  - mql5
  - event-bus
  - ipc
  - core
related:
  - "wiki/concepts/mql5-coding-standards"
  - "wiki/concepts/module-contribution-guide"
sources:
  - "wiki/sources/standards-md"
created: 2026-08-18
updated: 2026-08-18
---

# CGlobalEventBus

Event bus class for inter-component communication within MT5. Provides publish/subscribe pattern for decoupled component interaction.

## Purpose

- Decoupled communication between EA components
- Event-driven architecture support
- Replaces global variable-based IPC
- Core module with no dependencies (sink rule)

## Namespace

- `core/` namespace
- Tier A (pure MQL5, zero platform-specific dependencies)
- Must have no dependencies (sink rule for core modules)

## Guard Macro

```
__SRC5_CORE_CGLOBALEVENTBUS_MQH__
```
