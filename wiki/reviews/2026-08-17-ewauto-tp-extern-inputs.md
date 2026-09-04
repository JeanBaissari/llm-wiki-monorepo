---
type: review
status: open
severity: info
entity: ew-auto-tp
created: 2026-08-17
related:
  - "ew-auto-tp"
  - "extern-inputs-in-include"
---

# EWAutoTP — Extern Inputs in Shared Module

## Issue

EWAutoTP declares `extern input` variables at file scope in an `.mqh` include file. Shared module `.mqh` files should NOT declare extern inputs — inputs belong in the consuming EA.

## Impact

Including multiple modules with inputs creates duplicate input declarations in the MetaEditor.

## Recommendation

Remove input declarations from the `.mqh`. The consuming EA should declare its own inputs and pass them as parameters to `ManageAutoTP()`.
