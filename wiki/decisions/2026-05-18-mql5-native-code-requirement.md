---
type: decision
status: "accepted"
date: 2026-05-18
deciders:
  - "Baissari Enterprises Algo LLC"
supersedes: []
title: "MQL5-Native Code Requirement"
tags:
  - decision
  - mql5
  - coding-standards
  - architecture
related:
  - "wiki/concepts/mql5-coding-standards"
  - "wiki/concepts/price-symbol-access-rules"
  - "wiki/sources/standards-md"
created: 2026-08-18
updated: 2026-08-18
---

# MQL5-Native Code Requirement

## Context & Problem Statement

MetaTrader 5 is a fundamentally different platform from MT4. It has a true multi-threaded tick execution engine, a 64-bit architecture, built-in hedging via netting, and a proper OOP trade API. Every pattern that worked in MT4 because of its single-threaded FIFO model is wrong in MT5.

## Decision Drivers

- MT5's multi-threaded execution model creates race conditions with MQL4-style globals
- Backtest mode doesn't populate Ask/Bid globals correctly
- Broker portability requires SymbolInfo-based access
- Maintainability across MT5 build updates

## Considered Options

1. **MQL5-native code** — Write pure MQL5 with modern patterns
2. **MQL4 compatibility mode** — Use MQL4 patterns under MQL5 compatibility
3. **Hybrid approach** — Mix MQL4 and MQL5 patterns as needed

## Decision Outcome

We will write MQL5-native code — not MQL4 code compiled under MQL5 compatibility mode. This eliminates undefined behavior, ensures correct order lifecycle tracking, and makes the suite maintainable across MT5 build updates.

## Consequences

- **Positive**: Eliminates race conditions, ensures correct backtest behavior, improves broker portability
- **Negative**: Requires learning MQL5-specific patterns, more verbose code in some cases
- **Neutral**: All EAs must use CTrade, SymbolInfoDouble/Integer, handle-based iCustom
