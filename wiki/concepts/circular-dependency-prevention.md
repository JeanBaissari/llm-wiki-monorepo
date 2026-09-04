---
type: concept
confidence: high
contested: false
implemented_by:
  - "ind-ew-confirmationengine"
related:
  - "ind-ew-kennedychannel"
  - "ind-ew-confirmationengine"
  - "ew-auto-tp"
sources:
  - "raw/src5/shared/modules/ew/EWAutoTP.mqh"
created: 2026-08-17
updated: 2026-08-17
---

# Circular Dependency Prevention

Pattern of hardcoding `UseKennedy=false` in ConfirmationEngine reads to prevent circular include dependencies.

## Problem

ConfirmationEngine optionally depends on KennedyChannel. KennedyChannel depends on WaveLabeler. If ConfirmationEngine loads KennedyChannel, and KennedyChannel is already loaded by the parent (EWAutoTP), a circular dependency can occur:

```
EWAutoTP → KennedyChannel → ConfirmationEngine → KennedyChannel (circular!)
```

## Solution

When EWAutoTP reads ConfirmationEngine, `UseKennedy` is hardcoded to `false`:

```mql5
double ReadConfirmationEngineAutoTP(...)
{
    return iCustom(Symbol(), Period(),
        "EW\\Ind_EW_ConfirmationEngine",
        true, 14, 75.0, 25.0,       // RSI params
        true, 20, 2.0,               // BB params
        true, 14,                    // Divergence params
        true, 1.5,                   // Volume params
        false,                       // UseKennedy=false (prevent circular dependency)
        profileId, false, 0,
        bufIdx, bar);
}
```

## Trade-off

By disabling Kennedy in ConfirmationEngine, the confirmation signal loses one input factor. However, EWAutoTP already reads KennedyChannel directly for trailing stop, so the Kennedy information is still available to the overall system — just not via the ConfirmationEngine aggregation path.

## When This Pattern Applies

This pattern is necessary whenever:
1. An indicator optionally depends on another indicator
2. The parent already loads the optionally-depended indicator
3. The MQL4/5 `#include` system doesn't support conditional/circular includes

## Cross-References

- [[wiki/entities/ind-ew-confirmationengine|Ind_EW_ConfirmationEngine]] — Where the hardcoding happens
- [[wiki/entities/ind-ew-kennedychannel|Ind_EW_KennedyChannel]] — The avoided dependency
- [[wiki/entities/ew-auto-tp|EWAutoTP]] — Consumer that triggers this pattern
