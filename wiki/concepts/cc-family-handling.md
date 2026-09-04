---
type: concept
title: "CC-Family Handling"
confidence: high
contested: false
implemented_by: []
tags:
  - licensing
  - creative-commons
  - nc-restricted
related:
  - "concepts/license-classes"
  - "concepts/license-taxonomy"
  - "sources/license-taxonomy"
created: 2026-08-17
updated: 2026-08-17
---

# CC-Family Handling

## Definition

How Creative Commons licenses are classified and handled in the license taxonomy. CC licenses with NC (NonCommercial) restrictions are classified as `nc-restricted` — they block derivative works and distribution.

## Classification

| License | Class | Rationale |
|---|---|---|
| `CC-BY-NC-SA-4.0` | `nc-restricted` | NC + SA restrictions |
| `CC-BY-NC-4.0` | `nc-restricted` | NC restriction |
| `CC-BY-4.0` | `permissive` | No NC restriction |
| `CC0-1.0` | `permissive` | Public domain dedication |

## Key Rules

1. **NC = blocked**: Any CC license with NC suffix → `nc-restricted` → no derivatives, no distribution
2. **Dual-header claims**: Classified by the stricter applicable constraint, never averaged into a permissive reading
3. **Conflict flag**: When dual-header claims conflict, a conflict flag is raised — never averaged
4. **MPL-2.0 incompatibility**: MPL-2.0 and CC BY-NC-SA 4.0 are incompatible — cannot combine

## Example

A source with dual headers `MPL-2.0` + `CC-BY-NC-SA-4.0`:
- Classification: `nc-restricted` (stricter constraint wins)
- Conflict flag: **raised** (incompatible licenses)
- Result: Study allowed, derivatives blocked

## Related Concepts

- [[concepts/license-classes]] — the five license classes
- [[concepts/license-taxonomy]] — the overall classification system
