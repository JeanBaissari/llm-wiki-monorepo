---
type: concept
title: "License Taxonomy"
confidence: high
contested: false
implemented_by: []
tags:
  - licensing
  - provenance
  - taxonomy
  - governance
related:
  - "concepts/rights-axes"
  - "concepts/distribution-channels"
  - "concepts/fidelity-tiers"
  - "concepts/fail-closed-licensing"
  - "concepts/license-classes"
  - "sources/license-taxonomy"
created: 2026-08-17
updated: 2026-08-17
---

# License Taxonomy

## Definition

The classification system for source licenses governing code reuse, modification, and distribution. Every source must have an SPDX license identifier (or custom terms with evidence), and a license ID alone is never sufficient — the record must also carry permission evidence, an explicit rights list, restrictions, reviewer, and review date.

## Accepted License Forms

| Form | Accepted? | Notes |
|---|---|---|
| SPDX identifier (`MIT`, `Apache-2.0`, `GPL-3.0-only`) | Yes | Exact identifier required; version-scoped |
| Custom terms identifier | Yes | Requires permission evidence path, rights list, restrictions, reviewer, review date |
| `unknown` | **No — blocking** | Blocks code reuse and every release channel |
| Missing license metadata | **No — blocking** | Missing reviewer/review-date/evidence also blocks |
| "Public on the internet" | **No** | Visibility is not permission (PS-DR-014) |

## License Classes (v2)

| Class | SPDX Examples | Admit for Study | Admit for Derivative | Block |
|---|---|---|---|---|
| `permissive` | MIT, Apache-2.0, BSD-2-Clause | Yes | Yes | — |
| `weak-copyleft` | MPL-2.0, LGPL-2.1 | Yes | Conditional | — |
| `strong-copyleft` | GPL-3.0-only, AGPL-3.0-only | Yes | Blocked (studio) | Yes (studio) |
| `nc-restricted` | CC-BY-NC-4.0, CC-BY-NC-SA-4.0 | Yes | Blocked | Yes |
| `custom-terms` | Proprietary, custom | Conditional | Conditional | Depends on terms |

## Fail-Closed Defaults

- Unknown license → no reuse, no publication
- Missing metadata → blocks all channels
- Absence of permission → never means allowed

## Related Concepts

- [[concepts/rights-axes]] — the 5 independent evaluation dimensions
- [[concepts/distribution-channels]] — the 7 distribution channels
- [[concepts/fidelity-tiers]] — orthogonal to rights
- [[concepts/fail-closed-licensing]] — default-deny rules
- [[concepts/license-classes]] — v2 studio license classes
