---
type: source
title: "License Taxonomy and Rights Matrix"
authors: ["Provenance and Licensing Owner"]
year: 2026
url: ""
venue: "PS_003, BPS_011"
tags:
  - licensing
  - provenance
  - rights
  - taxonomy
related:
  - "concepts/license-classes"
  - "concepts/rights-axes"
  - "concepts/distribution-channels"
  - "concepts/fidelity-tiers"
  - "concepts/fail-closed-licensing"
  - "concepts/cc-family-handling"
  - "concepts/mpl-reauthoring-rules"
  - "concepts/commercial-licensing-risk"
sources:
  - "raw/docs/license-taxonomy.md"
created: 2026-08-17
updated: 2026-08-17
---

# License Taxonomy and Rights Matrix

## Source Summary

Governing document for source license classification and rights evaluation. Defines accepted license forms, rights axes, distribution channels, fidelity tiers, and fail-closed rules. Extended by v2 (BPS_011) with five studio license classes and per-channel rights matrix.

## Key Sections

### Accepted License Forms

| Form | Accepted? | Notes |
|---|---|---|
| SPDX identifier (`MIT`, `Apache-2.0`, `GPL-3.0-only`) | Yes | Exact identifier required; version-scoped |
| Custom terms identifier | Yes | Requires permission evidence path, rights list, restrictions, reviewer, review date |
| `unknown` | **No — blocking** | Blocks code reuse and every release channel (PS-003-REQ-004, AC-003) |
| Missing license metadata | **No — blocking** | Missing reviewer/review-date/evidence also blocks |
| "Public on the internet" | **No** | Visibility is not permission (PS-DR-014) |

A license ID alone is never sufficient — must carry permission evidence, rights list, restrictions, reviewer, and review date.

### Rights Axes (5 independent dimensions)

1. **Internal evaluation** — using behavior/observations internally
2. **Modification** — changing the source
3. **Internal distribution** — copying within repo/team
4. **Publication** — any TradingView or public release
5. **Redistribution** — shipping source or derived works onward

An allowed axis never implies another (PS-003-REQ-008). Absence never means allowed.

### Distribution Channels

| Channel | Meaning | V1 Record |
|---|---|---|
| `internal_evaluation` | Observe/use behavior internally | per-source |
| `internal_source_copy` | Retain source bytes in repo | per-source |
| `private_release` | Internal/private distribution | per-source |
| `public_open_source` | Public source release | **false** until re-audit |
| `public_protected` | Protected public script | **false** until re-audit |
| `invite_only` | Invite-only publication | **false** until re-audit |
| `documentation_excerpt` | Excerpts beyond a link | **false** (`link_only`) |

V1 product record allows only `repository_internal_private: true`. Product-channel values never broaden source rights.

### Fidelity Tiers (orthogonal to rights)

| Tier | What it permits |
|---|---|
| `T0_PLATFORM_AUTHORITY` | Pine behavior/supported workflow claims from official docs |
| `T1_LICENSED_EXECUTABLE_ORACLE` | Formula/event parity within declared tolerances |
| `T2_INDEPENDENT_GOLDEN_EVIDENCE` | Observed behavior on covered cases |
| `T3_DOCUMENTED_BEHAVIOR` | Conformance to described behavior |
| `T4_NARRATIVE_OR_VISUAL_HINT` | Design inspiration only; no fidelity claim |
| `TX_REJECTED` | No implementation use at all |

High tier never substitutes for permission. T4 screenshot missing metadata cannot exceed T4.

### Fail-Closed Rules

1. Unknown authorship, unknown license, or unspecified channel → no code reuse, no publication
2. Permissioned private source → metadata-only by default; bytes/modifications/distribution require explicit written permission
3. License conflicts with TradingView rules → stricter constraint applies
4. Later license change → append modification history, invalidate approval, re-review

### v2 Extension (BPS_011, WS-1)

1. **Five license classes**: `permissive`, `weak-copyleft`, `strong-copyleft`, `nc-restricted`, `custom-terms`
2. **CC-family handling**: `CC-BY-NC-SA-4.0` and `CC-BY-NC-4.0` are `nc-restricted`; dual-header claims classified by stricter constraint; MPL-2.0 and CC BY-NC-SA 4.0 are incompatible
3. **Rights matrix**: 7 channels × 5 classes, cells exactly one of allowed/conditional/blocked
4. **MPL-2.0 re-authoring rules** for studio derivatives
5. **WS-1 classification**: ICT/RSI/SMT/Triple → weak-copyleft (MPL-2.0); Liquidity Delta Profiler → nc-restricted (conflict, escalated)

## Notable Claims

- "Public on the internet" / "I saw it on a chart" is explicitly **not** permission (PS-DR-014)
- A high fidelity tier never substitutes for permission
- Product-channel values never broaden a source record's rights
- License conflicts → stricter constraint always wins (no averaging)

## Source Document

Original: `work/mt5-algo-suite/PRD/pinescript/00-foundation/PS_003_reference_intake_provenance_and_licensing.md`
v2 extension: `manifest/licenses/taxonomy-v2.yaml`, `manifest/licenses/rights-matrix.yaml`
