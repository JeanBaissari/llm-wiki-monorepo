---
type: concept
title: "Fidelity Tiers"
confidence: high
contested: false
implemented_by: []
tags:
  - licensing
  - fidelity
  - tiers
related:
  - "concepts/rights-axes"
  - "concepts/license-taxonomy"
  - "sources/license-taxonomy"
created: 2026-08-17
updated: 2026-08-17
---

# Fidelity Tiers

## Definition

The classification system for how closely an implementation matches a source. Tiers are **orthogonal** to rights — a high tier never substitutes for permission (PS-003 §Fidelity Tiers).

## Tier Definitions

| Tier | Name | What it permits |
|---|---|---|
| `T0` | Platform Authority | Pine behavior/supported workflow claims from official docs |
| `T1` | Licensed Executable Oracle | Formula/event parity within declared tolerances |
| `T2` | Independent Golden Evidence | Observed behavior on covered cases |
| `T3` | Documented Behavior | Conformance to described behavior |
| `T4` | Narrative or Visual Hint | Design inspiration only; no fidelity claim |
| `TX` | Rejected | No implementation use at all |

## Key Rules

1. **Orthogonal to rights**: Tier does not affect rights evaluation
2. **High tier ≠ permission**: A T0 source still needs explicit license for reuse
3. **Metadata gates**: A T4 screenshot missing symbol/timeframe/timezone/feed/settings cannot exceed T4 (PS-003-AC-007)
4. **Source of truth**: Tier reflects the quality of evidence, not the license

## Example

A `T0` source with `unknown` license:
- Tier: T0 (high fidelity evidence)
- Rights: **blocked** (unknown license → fail-closed)
- Result: Can observe behavior, cannot reuse code

## Related Concepts

- [[concepts/rights-axes]] — the 5 dimensions evaluated independently
- [[concepts/license-taxonomy]] — the classification system
