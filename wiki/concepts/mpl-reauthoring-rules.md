---
type: concept
title: "MPL-2.0 Re-Authoring Rules"
confidence: high
contested: false
implemented_by: []
tags:
  - licensing
  - mpl-2.0
  - re-authoring
  - derivatives
related:
  - "concepts/license-classes"
  - "concepts/license-taxonomy"
  - "sources/license-taxonomy"
created: 2026-08-17
updated: 2026-08-17
---

# MPL-2.0 Re-Authoring Rules

## Definition

Rules for creating studio derivatives of MPL-2.0 licensed sources. MPL-2.0 is a weak-copyleft license with file-level copyleft requirements.

## The Five Rules

1. **File-level copyleft**: Modifications to MPL-2.0 files must remain under MPL-2.0
2. **Notice retention**: Original copyright notices and license text must be preserved
3. **Source availability**: Modified files must be made available in source form
4. **Larger Work boundary**: MPL-2.0 applies at file level — new files can use different license
5. **BPS_071 mapping**: Studio-specific mapping for how MPL-2.0 requirements apply to derived works

## Key Distinction

MPL-2.0 is **weak copyleft** — it applies only to files that were originally MPL-2.0 or modified from MPL-2.0. New files created independently can use any license.

## Application

| Scenario | MPL-2.0 Applies? |
|---|---|
| Modify existing MPL-2.0 file | Yes — must remain MPL-2.0 |
| Create new file in same project | No — can use any license |
| Combine MPL-2.0 with non-MPL code | Only MPL-2.0 files must stay MPL-2.0 |
| Distribute modified MPL-2.0 file | Must include source and notice |

## Related Concepts

- [[concepts/license-classes]] — MPL-2.0 is `weak-copyleft`
- [[concepts/license-taxonomy]] — the overall classification system
