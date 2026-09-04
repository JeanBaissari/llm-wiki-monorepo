---
type: entity
language: mql5
namespace: indicators/ew
status: active
version: "unknown"
tags:
  - elliott-wave
  - fibonacci
  - extension
  - retracement
  - indicator
related:
  - "ew-auto-tp"
  - "fibonacci-extension-ladder"
  - "ew-fibonacci"
  - "ind-ew-wavelabeler"
  - "ind-ew-kennedychannel"
sources:
  - "raw/src5/indicators/ew/Ind_EW_FibEngine.mq4"
created: 2026-08-17
updated: 2026-08-17
---

# Ind_EW_FibEngine

Elliott Wave Fibonacci extension/retracement indicator providing price levels for TP ladder targeting.

## Role in EWAutoTP

EWAutoTP consumes 4 buffers from FibEngine:

| Buffer | Constant | Description |
|--------|----------|-------------|
| 3 | `FE_BUF_161` | 161.8% extension price (carry-forward) |
| 4 | `FE_BUF_261` | 261.8% extension price (carry-forward) |
| 6 | `FE_BUF_LEG_START` | Wave leg start price (carry-forward) |
| 7 | `FE_BUF_LEG_END` | Wave leg end price (carry-forward) |

The 161.8% and 261.8% levels form the core of the TP ladder (161.8 → 261.8 → 423.6%).

## iCustom Parameters

As called by `ReadFibEngine()` in EWAutoTP:

```
"EW\\Ind_EW_FibEngine",
profileId, false, 0,              // ProfileID, UseSync, Theme
0,                                // FibMode: 0=AUTO
fractalBars, atrPer, atrMult, false,  // SwingEngine params
0.0, 0.0,                         // ManualStart, ManualEnd
10.0, false, false,               // ClusterTolerance, ShowLevels, ShowLabels
bufIdx, bar
```

## Dependencies

- SwingEngine (for swing detection to determine wave legs)
- Referenced by EWAutoTP, Ind_EW_KennedyChannel, Ind_EW_WaveLabeler

## Cross-References

- [[wiki/concepts/fibonacci-extension-ladder|Fibonacci Extension Ladder]] — TP ladder stepping logic
- [[wiki/entities/ew-auto-tp|EWAutoTP]] — Primary consumer of FibEngine buffers
