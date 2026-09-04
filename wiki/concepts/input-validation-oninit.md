---
type: concept
title: "Input Validation in OnInit"
confidence: high
contested: false
implemented_by:
  - "wiki/entities/mt5-algo-suite"
tags:
  - mql5
  - input-validation
  - oninit
related:
  - "wiki/concepts/mql5-coding-standards"
  - "wiki/sources/standards-md"
created: 2026-08-18
updated: 2026-08-18
---

# Input Validation in OnInit

All input parameters must be validated in `OnInit`. Return `INIT_PARAMETERS_INCORRECT` for invalid configurations.

## Implementation

```mql5
int OnInit() {
   if (inp_Magic <= 0) {
      Print("INVALID PARAMETER: inp_Magic must be positive");
      return INIT_PARAMETERS_INCORRECT;
   }
   if (inp_RiskPercent <= 0 || inp_RiskPercent > 100) {
      Print("INVALID PARAMETER: inp_RiskPercent must be 1-100");
      return INIT_PARAMETERS_INCORRECT;
   }
   if (inp_StopLossPoints < 10) {
      Print("INVALID PARAMETER: inp_StopLossPoints minimum is 10");
      return INIT_PARAMETERS_INCORRECT;
   }
   return INIT_SUCCEEDED;
}
```

## Validation Checklist (from 12-Point EA Review)

- [ ] Magic number validated: positive integer, not default test value
- [ ] Risk percentage: within 1-100 range
- [ ] Stop loss / take profit: minimum distance respected
- [ ] Lot size: respects `MODE_MINLOT`, `MODE_MAXLOT`, `MODE_LOTSTEP`
- [ ] Any invalid parameter returns `INIT_PARAMETERS_INCORRECT`

## Purpose

- Prevents invalid configurations from running
- Provides clear error messages for users
- Fails fast before any resources are allocated
