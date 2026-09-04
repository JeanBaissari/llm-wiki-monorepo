---
type: entity
language: mql5
namespace: "trading"
status: "active"
version: "1.00"
dependencies: []
title: "COrderOps"
tags:
  - mql5
  - trading
  - order-operations
  - custom-module
related:
  - "wiki/entities/ctrade"
  - "wiki/concepts/trade-operations-ctrade"
  - "wiki/concepts/mql5-coding-standards"
sources:
  - "wiki/sources/standards-md"
created: 2026-08-18
updated: 2026-08-18
---

# COrderOps

Custom order operations wrapper that delegates to CTrade. Provides position lifecycle tracking and extended order management.

## Purpose

- Extended order management beyond CTrade's basic operations
- Position lifecycle tracking
- Custom retry logic and error handling
- Alternative to direct CTrade usage for complex order scenarios

## Relationship to CTrade

- COrderOps delegates to CTrade for actual order execution
- Adds position tracking and lifecycle management
- Can be used as alternative to CTrade in EA code review checkpoint 3

## Namespace

- `trading/` namespace
- Tier A (pure MQL5, zero platform-specific dependencies)
