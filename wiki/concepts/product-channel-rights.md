---
type: concept
title: "Product-Channel Rights"
confidence: high
contested: false
implemented_by: []
tags:
  - licensing
  - product
  - channels
  - rights
related:
  - "concepts/distribution-channels"
  - "concepts/rights-axes"
  - "concepts/license-taxonomy"
  - "sources/license-taxonomy"
created: 2026-08-17
updated: 2026-08-17
---

# Product-Channel Rights

## Definition

The principle that product distribution channel values never broaden a source record's rights. Every dependency must independently allow the intended internal use — the product's channel selection does not override source-level restrictions.

## Key Rules

1. **No broadening**: Product-channel values never expand what a source allows
2. **Independent evaluation**: Each dependency must independently permit the intended use
3. **V1 restriction**: Only `repository_internal_private: true` allowed in V1
4. **Stricter wins**: If source restricts more than product channel, source restriction applies

## Example

Product channel: `private_release`
Source rights: `internal_evaluation` only

Result: Product can only use source for internal evaluation, not private release — source restriction wins.

## Related Concepts

- [[concepts/distribution-channels]] — the 7 distribution channels
- [[concepts/rights-axes]] — the 5 evaluation dimensions
