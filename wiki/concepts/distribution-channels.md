---
type: concept
title: "Distribution Channels"
confidence: high
contested: false
implemented_by: []
tags:
  - licensing
  - distribution
  - channels
related:
  - "concepts/rights-axes"
  - "concepts/license-taxonomy"
  - "sources/license-taxonomy"
created: 2026-08-17
updated: 2026-08-17
---

# Distribution Channels

## Definition

The seven channels through which sources can be distributed. Each channel has a specific meaning and V1 record status. Product-channel values never broaden a source record's rights — every dependency must independently allow the intended use.

## Channel Matrix

| Channel | Meaning | V1 Record |
|---|---|---|
| `internal_evaluation` | Observe/use behavior internally | per-source |
| `internal_source_copy` | Retain source bytes in repo | per-source |
| `private_release` | Internal/private distribution | per-source |
| `public_open_source` | Public source release | **false** until re-audit (PS-DR-044) |
| `public_protected` | Protected public script | **false** until re-audit |
| `invite_only` | Invite-only publication | **false** until re-audit |
| `documentation_excerpt` | Excerpts beyond a link | **false** (`link_only`) |

## Key Rules

1. **V1 restriction**: Only `repository_internal_private: true` is allowed in V1
2. **No broadening**: Product-channel values never broaden source rights
3. **Independent**: Each dependency must independently allow intended use
4. **Fail-closed**: Unspecified channel → no reuse, no publication

## Related Concepts

- [[concepts/rights-axes]] — the 5 dimensions evaluated per channel
- [[concepts/license-taxonomy]] — the classification system
