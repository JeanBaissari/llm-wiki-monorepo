---
type: review
status: open
severity: warning
entity: ew-auto-tp
created: 2026-08-17
related:
  - "ew-auto-tp"
---

# EWAutoTP — Hardcoded Indicator Paths

## Issue

EWAutoTP hardcodes indicator paths as string literals:

```mql5
"EW\\Ind_EW_FibEngine"
"EW\\Ind_EW_KennedyChannel"
"EW\\Ind_EW_WaveLabeler"
"EW\\Ind_EW_ConfirmationEngine"
```

## Impact

- Cannot reuse EWAutoTP with different indicator versions
- Cannot test with mock indicators
- Path changes require recompilation

## Recommendation

Consider making indicator paths input parameters or constants defined in a shared config header.
