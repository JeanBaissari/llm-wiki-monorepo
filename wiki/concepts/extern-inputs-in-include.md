---
type: concept
confidence: medium
contested: true
implemented_by:
  - "ew-auto-tp"
related:
  - "auto-tp-adjustment"
  - "circular-dependency-prevention"
sources:
  - "raw/src5/shared/modules/ew/EWAutoTP.mqh"
created: 2026-08-17
updated: 2026-08-17
---

# Extern Inputs in Include File

Input declarations in an `.mqh` include file that violate the shared module standard. Preserved in EWAutoTP for source fidelity.

## The Issue

EWAutoTP declares `extern input` variables at file scope:

```mql5
input bool inp_AutoAdjustTP    = true;
input bool inp_AlertOnAdjust   = true;
input int  inp_AdjustDelayBars = 2;
input int  inp_ProfileID       = 1;
```

Shared module `.mqh` files should NOT declare extern inputs — inputs belong in the EA that includes them. Including multiple modules with inputs creates duplicate input declarations.

## Why It Exists

The source reference block (documentation header) of the original file carries these declarations. They are preserved in EWAutoTP only for fidelity with the source reference. At integration time, the consuming EA should:

1. Declare its own input variables
2. Pass them as parameters to `ManageAutoTP()`
3. Remove or guard the input declarations in the `.mqh`

## Contested Aspect

This is debated: some argue the inputs should be removed entirely from the `.mqh`, while others prefer keeping them for documentation/reference purposes with a comment noting they must be removed at integration.

## Cross-References

- [[wiki/concepts/auto-tp-adjustment|Auto-TP Adjustment]] — Uses these parameters
- [[wiki/entities/ew-auto-tp|EWAutoTP]] — Where this issue exists
