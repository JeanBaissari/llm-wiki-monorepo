---
type: concept
title: "Fail-Closed Licensing"
confidence: high
contested: false
implemented_by: []
tags:
  - licensing
  - fail-closed
  - governance
related:
  - "concepts/license-taxonomy"
  - "concepts/rights-axes"
  - "sources/license-taxonomy"
created: 2026-08-17
updated: 2026-08-17
---

# Fail-Closed Licensing

## Definition

The default-deny rules that govern when license information is unknown, missing, or conflicting. If any critical metadata is absent, the system blocks all reuse and distribution — no exceptions.

## The Four Fail-Closed Rules

1. **Unknown authorship, unknown license, or unspecified channel** → no code reuse, no publication
2. **Permissioned private source** → metadata-only by default; bytes, modifications, and distribution require explicit written permission for the exact version/channel (PS-DR-046, REQ-015)
3. **License conflicts with TradingView rules** → stricter constraint applies; unresolved conflicts escalate to owner/counsel
4. **Later license change** → append modification history, invalidate approval, re-review before any continued use (PS-003-REQ-009)

## Application

| Scenario | Result |
|---|---|
| License: `unknown` | **Blocked** — all channels |
| License missing entirely | **Blocked** — all channels |
| Reviewer missing | **Blocked** — metadata incomplete |
| "I saw it on a chart" | **Blocked** — visibility ≠ permission |
| License conflicts with platform | **Stricter constraint** applies |
| License changed after approval | **Invalidated** — must re-review |

## Key Principle

**Absence never means allowed.** If permission is not explicitly documented, it does not exist.

## Related Concepts

- [[concepts/license-taxonomy]] — the classification system
- [[concepts/rights-axes]] — the dimensions where fail-closed applies
