---
type: decision
status: "accepted"
date: 2026-05-18
deciders:
  - "Baissari Enterprises Algo LLC"
supersedes: []
title: "Research-First Gate Enforcement"
tags:
  - decision
  - research
  - gate
  - methodology
related:
  - "wiki/concepts/research-first-gate"
  - "wiki/concepts/backtest-methodology"
  - "wiki/sources/standards-md"
created: 2026-08-18
updated: 2026-08-18
---

# Research-First Gate Enforcement

## Context & Problem Statement

Without a research gate, strategies may reach development without proper validation, leading to wasted development time and potentially dangerous trading systems.

## Decision Drivers

- Prevent development of strategies without research backing
- Ensure strategies are grounded in market hypotheses
- Provide traceability from research to implementation
- Reduce wasted development time on unviable strategies

## Considered Options

1. **Hard gate** — No strategy reaches Phase 3 without research PRD
2. **Soft gate** — Research PRD recommended but not required
3. **No gate** — Development starts immediately

## Decision Outcome

We will enforce a hard gate: no strategy reaches Phase 3 (development) without a research PRD. This is enforced by the `ea_reviewer` and `workflow_orchestrator`.

## Consequences

- **Positive**: Ensures all strategies are research-backed, provides traceability, reduces wasted development
- **Negative**: Adds process overhead, may slow down rapid prototyping
- **Neutral**: Research PRDs must contain hypothesis, data requirements, entry/exit rules, parameters, risk model, target metrics, benchmark, out-of-sample plan
