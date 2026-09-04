---
type: concept
title: "License Classes"
confidence: high
contested: false
implemented_by: []
tags:
  - licensing
  - v2
  - studio
  - classes
related:
  - "concepts/license-taxonomy"
  - "concepts/cc-family-handling"
  - "concepts/mpl-reauthoring-rules"
  - "sources/license-taxonomy"
created: 2026-08-17
updated: 2026-08-17
---

# License Classes

## Definition

The five license classes introduced in v2 (BPS_011) that classify source licenses for studio use. Each class has admit-for-study, admit-for-derivative, and block verdicts.

## The Five Classes

| Class | SPDX Examples | Study | Derivative | Block |
|---|---|---|---|---|
| `permissive` | MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause | Yes | Yes | — |
| `weak-copyleft` | MPL-2.0, LGPL-2.1, LGPL-3.0 | Yes | Conditional (file-level copyleft) | — |
| `strong-copyleft` | GPL-3.0-only, AGPL-3.0-only | Yes | Blocked (studio) | Yes (studio) |
| `nc-restricted` | CC-BY-NC-4.0, CC-BY-NC-SA-4.0 | Yes | Blocked | Yes |
| `custom-terms` | Proprietary, custom licenses | Conditional | Conditional | Depends on terms |

## Studio Classification (WS-1)

| Source | Class | Rationale |
|---|---|---|
| ICT/RSI/SMT/Triple | weak-copyleft (MPL-2.0) | MPL-2.0 licensed |
| Liquidity Delta Profiler | nc-restricted | Conflict flagged, escalated per PS-DR-045, BPS-DR-011 |

## Key Rules

1. **Class alone ≠ permission**: Must also have evidence, rights list, restrictions, reviewer, review date
2. **Stricter wins**: License conflicts with TradingView → stricter constraint applies
3. **No averaging**: Dual-header claims classified by stricter applicable constraint, never averaged into permissive reading

## Related Concepts

- [[concepts/license-taxonomy]] — the overall classification system
- [[concepts/cc-family-handling]] — CC-family NC restrictions
- [[concepts/mpl-reauthoring-rules]] — MPL-2.0 derivative rules
