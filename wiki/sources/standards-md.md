---
type: source
title: "STANDARDS.md — MT5 Algorithmic Trading Suite"
authors: ["Baissari Enterprises Algo LLC"]
year: 2026
url: ""
venue: "Internal Standards Document"
tags:
  - standards
  - mql5
  - coding-standards
  - quality-gates
  - backtest-methodology
related:
  - "wiki/concepts/mql5-coding-standards"
  - "wiki/concepts/module-guard-macros"
  - "wiki/concepts/indicator-buffer-rules"
  - "wiki/concepts/price-symbol-access-rules"
  - "wiki/concepts/icustom-handle-pattern"
  - "wiki/concepts/trade-operations-ctrade"
  - "wiki/concepts/input-validation-oninit"
  - "wiki/concepts/ontrade-transaction-lifecycle"
  - "wiki/concepts/version-management"
  - "wiki/concepts/backtest-methodology"
  - "wiki/concepts/ea-code-review-checklist"
  - "wiki/concepts/module-contribution-guide"
  - "wiki/concepts/research-first-gate"
created: 2026-08-18
updated: 2026-08-18
---

# STANDARDS.md — MT5 Algorithmic Trading Suite

Professional coding standards, quality gates, and contribution guides for the Baissari Enterprises Algo LLC MT5 ecosystem.

## Document Structure

1. **MQL5 Coding Standards** — Naming conventions, guard macros, header blocks, buffer rules, price access, iCustom handles, trade operations, input validation, OnTradeTransaction
2. **Python Standards** — Conventions, type hints, Pydantic models, structured logging, async-first
3. **DLL Standards** — Calling convention, static CRT, SEH, cross-compilation, return codes
4. **Version Management** — MQL5 (#property version), Python (__version__), DLL (FILEVERSION)
5. **Backtest Methodology** — Tick data requirements, pass/fail criteria
6. **12-Point EA Code Review Checklist** — Validation gates before Phase 3
7. **Module Contribution Guide** — When to add shared modules, namespace conventions
8. **Research-First Gate** — No strategy reaches development without research PRD

## Key Claims

### MQL5 vs MT4
- MT5 is fundamentally different from MT4 (multi-threaded, 64-bit, netting/hedging, OOP trade API)
- Every pattern that worked in MT4 because of single-threaded FIFO model is wrong in MT5
- MQL5-native code required — not MQL4 compatibility mode

### Backtest Pass/Fail Criteria
- Profit Factor ≥ 1.5
- Max Drawdown ≤ 30%
- Total Trades ≥ 200
- Win Rate ≥ 35% (25% for high RR strategies)
- Sharpe Ratio ≥ 1.0
- Modeling Quality ≥ 90%
- Consecutive Losses ≤ 10

### Research-First Gate
- No strategy reaches Phase 3 (development) without a research PRD
- Hard gate enforced by ea_reviewer and workflow_orchestrator

## Contradictions / Contested Aspects

1. **MQL4 vs MQL5 Scope**: Document is MT5-focused but wiki title mentions "MQL4/5 Algorithmic Trading" — potential scope confusion
2. **Version Format Inconsistency**: MQL5 uses two-decimal "X.XX" format, Python uses semantic "X.Y.Z", DLL uses "X,Y,Z" — three different versioning schemes in one ecosystem
3. **Backtest Thresholds**: Some thresholds may be too aggressive for certain strategy types (e.g., 200 minimum trades for scalping strategies)

## Relationships

- Depends on: MT5 platform, MQL5 language, Python 3.x, MSVC/MinGW compilers
- Referenced by: All EA development, module contributions, backtest validation
- Enforced by: CI pipelines, ea_reviewer agent, workflow_orchestrator agent
