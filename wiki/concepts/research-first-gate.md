---
type: concept
title: "Research-First Gate"
confidence: high
contested: false
implemented_by:
  - "wiki/entities/mt5-algo-suite"
tags:
  - research
  - gate
  - prd
  - methodology
related:
  - "wiki/concepts/mql5-coding-standards"
  - "wiki/concepts/backtest-methodology"
  - "wiki/sources/standards-md"
created: 2026-08-18
updated: 2026-08-18
---

# Research-First Gate

No strategy reaches Phase 3 (development) without a research PRD. This is a hard gate enforced by the `ea_reviewer` and `workflow_orchestrator`.

## What a Research PRD Must Contain

1. **Hypothesis**: A clear, falsifiable statement of what market condition the strategy exploits
2. **Data requirements**: Symbol(s), timeframe(s), date range, data source
3. **Entry/exit rules**: Exact conditions (not ambiguous)
4. **Parameters to optimize**: List of variables and ranges
5. **Risk model**: Fixed fractional, Kelly, or dynamic sizing
6. **Target metrics**: Minimum profit factor, max drawdown, Sharpe ratio
7. **Benchmark**: What the strategy is compared against (buy-and-hold, simple MA crossover)
8. **Out-of-sample plan**: How overfitting will be detected

## Gate Process

1. Strategy hypothesis → documented in `docs/research/` as PRD
2. `research_analyst` reviews PRD for completeness and plausibility
3. Backtest configuration prepared in `config/research/`
4. Initial parameter sweep executed in MT5 Strategy Tester
5. Results reviewed by `research_analyst` and `backtest_analyst`
6. Only if initial results approach target metrics → strategy advances to Phase 3
7. EA development begins → eventual `ea_reviewer` confirms the implemented strategy matches the PRD

## Purpose

- Prevents development of strategies without research backing
- Ensures strategies are grounded in market hypotheses
- Provides traceability from research to implementation
- Reduces wasted development time on unviable strategies
