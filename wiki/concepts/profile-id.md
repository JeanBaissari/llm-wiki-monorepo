---
type: concept
confidence: high
contested: false
implemented_by:
  - "ew-auto-tp"
related:
  - "auto-tp-adjustment"
sources:
  - "raw/src5/shared/modules/ew/EWAutoTP.mqh"
created: 2026-08-17
updated: 2026-08-17
---

# Profile ID

EW system profile identifier for parameterization. Default: 1. Passed to all consumed indicators.

## Definition

The Profile ID is an integer that selects a pre-configured parameter set for the EW indicator suite. It is passed to every iCustom() call in EWAutoTP, ensuring all indicators use consistent parameters.

## Usage in EWAutoTP

Every reader function receives `profileId` as its first parameter:

```mql5
ReadFibEngine(bufIdx, bar, profileId, ...)
ReadKennedyChannel(bufIdx, bar, profileId, ...)
ReadWaveLabelerAutoTP(bufIdx, bar, profileId, ...)
ReadConfirmationEngineAutoTP(bufIdx, bar, profileId, ...)
```

And passed through to each iCustom() call:

```mql5
iCustom(Symbol(), Period(), "EW\\...", profileId, false, 0, ...)
```

## Purpose

- **Multi-strategy support** — Different EAs can use different profiles
- **Parameter isolation** — Profile 1 settings don't affect Profile 2
- **Runtime selection** — Profile ID is an input parameter, changeable without recompilation

## Default

`inp_ProfileID = 1` — The standard EW profile.

## Cross-References

- [[wiki/concepts/auto-tp-adjustment|Auto-TP Adjustment]] — Uses profile ID
- [[wiki/entities/ew-auto-tp|EWAutoTP]] — Implementation
