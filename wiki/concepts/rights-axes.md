---
type: concept
title: "Rights Axes"
confidence: high
contested: false
implemented_by: []
tags:
  - licensing
  - rights
  - evaluation
related:
  - "concepts/license-taxonomy"
  - "concepts/distribution-channels"
  - "concepts/fidelity-tiers"
  - "sources/license-taxonomy"
created: 2026-08-17
updated: 2026-08-17
---

# Rights Axes

## Definition

The five independent dimensions on which every source's rights are evaluated. Each axis is decided separately — an allowed axis never implies another (PS-003-REQ-008). Absence never means allowed.

## The Five Axes

| Axis | What it evaluates | Example |
|---|---|---|
| **Internal evaluation** | Using behavior/observations internally | Reading documentation, observing chart patterns |
| **Modification** | Changing the source code | Adapting an indicator to new symbol |
| **Internal distribution** | Copying within repo/team | Sharing source bytes with team members |
| **Publication** | Any TradingView or public release | Publishing a protected script |
| **Redistribution** | Shipping source or derived works onward | Including in external packages |

## Key Rules

1. **Independence**: An allowed axis never implies another axis is allowed
2. **Absence = blocked**: Absence of permission on any axis means that axis is blocked
3. **Per-source**: Each source is evaluated independently on all 5 axes
4. **Never broadened**: Product-channel values never broaden a source record's rights

## Example Evaluation

For a source with `MPL-2.0` license:
- Internal evaluation: **allowed** (permissive class)
- Modification: **conditional** (weak-copyleft — file-level copyleft applies)
- Internal distribution: **allowed** (MPL-2.0 permits)
- Publication: **conditional** (requires MPL-2.0 compliance)
- Redistribution: **conditional** (requires MPL-2.0 source availability)

## Related Concepts

- [[concepts/license-taxonomy]] — the overall classification system
- [[concepts/distribution-channels]] — channels where rights are evaluated
- [[concepts/fidelity-tiers]] — orthogonal dimension (not rights)
