---
type: synthesis
title: "STANDARDS.md Extraction Summary"
tags:
  - synthesis
  - standards
  - mql5
  - coding-standards
related:
  - "wiki/sources/standards-md"
  - "wiki/concepts/mql5-coding-standards"
  - "wiki/concepts/ea-code-review-checklist"
  - "wiki/concepts/backtest-methodology"
  - "wiki/concepts/research-first-gate"
created: 2026-08-18
updated: 2026-08-18
---

# STANDARDS.md Extraction Summary

Key entities, concepts, claims, relationships, and contradictions extracted from the MT5 Algorithmic Trading Suite standards document.

## Key Entities Extracted

| Entity | Type | Namespace | Purpose |
|--------|------|-----------|---------|
| CTrade | Class | trading | Position management |
| CPositionInfo | Class | trading | Position property reading |
| COrderOps | Class | trading | Extended order operations |
| CGlobalEventBus | Class | core | Inter-component communication |

## Key Concepts Extracted

| Concept | Category | Confidence |
|---------|----------|------------|
| MQL5 Coding Standards | Coding | High |
| Module Guard Macros | Include Files | High |
| Indicator Buffer Rules | Indicators | High |
| Price/Symbol Access Rules | Price Data | High |
| iCustom Handle Pattern | Indicators | High |
| Trade Operations (CTrade) | Trading | High |
| Input Validation in OnInit | Validation | High |
| OnTradeTransaction Lifecycle | Trade Events | High |
| Version Management | Versioning | High |
| Backtest Methodology | Testing | High |
| EA Code Review Checklist | Quality Gates | High |
| Module Contribution Guide | Modules | High |
| Research-First Gate | Methodology | High |

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

## Relationships

- **CTrade** ← used by → **All EAs**
- **CPositionInfo** ← used by → **All EAs**
- **COrderOps** ← delegates to → **CTrade**
- **CGlobalEventBus** ← replaces → **Global Variable IPC**
- **Module Guard Macros** ← required by → **All .mqh files**
- **EA Code Review Checklist** ← enforced by → **ea_reviewer agent**
- **Research-First Gate** ← enforced by → **workflow_orchestrator agent**

## Contradictions / Contested Aspects

1. **MQL4 vs MQL5 Scope**: Document is MT5-focused but wiki title mentions "MQL4/5 Algorithmic Trading" — potential scope confusion
2. **Version Format Inconsistency**: MQL5 uses two-decimal "X.XX" format, Python uses semantic "X.Y.Z", DLL uses "X,Y.Z" — three different versioning schemes in one ecosystem
3. **Backtest Thresholds**: Some thresholds may be too aggressive for certain strategy types (e.g., 200 minimum trades for scalping strategies)
4. **Sharpe Ratio Threshold**: ≥ 1.0 is relatively high for algorithmic strategies — may reject viable strategies

## Pages Created

### Source
- `wiki/sources/standards-md.md` — Main source document

### Concepts (13 pages)
- `wiki/concepts/mql5-coding-standards.md`
- `wiki/concepts/module-guard-macros.md`
- `wiki/concepts/indicator-buffer-rules.md`
- `wiki/concepts/price-symbol-access-rules.md`
- `wiki/concepts/icustom-handle-pattern.md`
- `wiki/concepts/trade-operations-ctrade.md`
- `wiki/concepts/input-validation-oninit.md`
- `wiki/concepts/ontrade-transaction-lifecycle.md`
- `wiki/concepts/version-management.md`
- `wiki/concepts/backtest-methodology.md`
- `wiki/concepts/ea-code-review-checklist.md`
- `wiki/concepts/module-contribution-guide.md`
- `wiki/concepts/research-first-gate.md`

### Entities (4 pages)
- `wiki/entities/ctrade.md`
- `wiki/entities/cpositioninfo.md`
- `wiki/entities/corderops.md`
- `wiki/entities/cglobaleventbus.md`

### Architecture (1 page)
- `wiki/architecture/module-namespace-architecture.md`

### Decisions (2 pages)
- `wiki/decisions/2026-05-18-mql5-native-code-requirement.md`
- `wiki/decisions/2026-05-18-research-first-gate-enforcement.md`

### Synthesis (1 page)
- `wiki/synthesis/standards-md-extraction-summary.md`
