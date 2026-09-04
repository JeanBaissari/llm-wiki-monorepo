---
type: concept
title: "Permission Evidence"
confidence: high
contested: false
implemented_by: []
tags:
  - licensing
  - evidence
  - governance
related:
  - "concepts/license-taxonomy"
  - "concepts/fail-closed-licensing"
  - "sources/license-taxonomy"
created: 2026-08-17
updated: 2026-08-17
---

# Permission Evidence

## Definition

The required evidence that must accompany a license claim. A license ID alone is never sufficient — the record must also carry permission evidence, an explicit rights list, restrictions, reviewer, and review date.

## Required Fields

| Field | Purpose | Missing → |
|---|---|---|
| License ID | SPDX identifier or custom terms | **Blocking** |
| Permission evidence path | Documented proof of permission | **Blocking** |
| Rights list | Explicit list of allowed uses | **Blocking** |
| Restrictions | What is NOT allowed | **Blocking** |
| Reviewer | Person who reviewed the source | **Blocking** |
| Review date | When the review occurred | **Blocking** |

## Evidence Types

- Written permission from copyright holder
- License file in source repository
- Official documentation stating terms
- Email/communication confirming rights

## Fail-Closed

If any required field is missing, the source is blocked from all channels. There are no exceptions.

## Related Concepts

- [[concepts/license-taxonomy]] — the classification system
- [[concepts/fail-closed-licensing]] — default-deny rules
