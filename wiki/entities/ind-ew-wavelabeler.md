---
type: entity
language: mql5
namespace: indicators/ew
status: active
version: "unknown"
tags:
  - elliott-wave
  - wave-labeling
  - wave-number
  - completion
  - indicator
related:
  - "ew-auto-tp"
  - "wave-exhaustion-exit"
  - "ind-ew-fibengine"
  - "ind-ew-kennedychannel"
  - "ind-ew-confirmationengine"
sources:
  - "raw/src5/indicators/ew/Ind_EW_WaveLabeler.mq4"
created: 2026-08-17
updated: 2026-08-17
---

# Ind_EW_WaveLabeler

Elliott Wave labeling indicator providing wave number, state, and completion probability.

## Role in EWAutoTP

EWAutoTP consumes 3 buffers from WaveLabeler:

| Buffer | Constant | Description |
|--------|----------|-------------|
| 0 | `EW_WL_WAVE_NUM` | Wave number: 1-5, 10=A, 11=B, 12=C, 0=IDLE, -1=UNCLASSIFIED |
| 1 | `EW_WL_WAVE_STATE` | Wave state: 0=IDLE, 1=FORMING, 2=COMPLETE |
| 7 | `EW_WL_COMPLETION_P` | Completion probability 0-100 (FORMING waves only) |

Buffer 7 (`EW_WL_COMPLETION_P`) is critical for exhaustion exit detection: when completion > 80 AND divergence != 0, all orders are closed.

## iCustom Parameters

As called by `ReadWaveLabelerAutoTP()` in EWAutoTP:

```
"EW\\Ind_EW_WaveLabeler",
profileId, false, 0,                    // ProfileID, UseSync, Theme
fractalBars, atrPer, atrMult, false,    // SwingEngine params
fractalBars, atrPer, atrMult, false,    // FibEngine SwingEngine params
0.0, 0.0, 10.0, false, false,           // FibEngine cluster/display params
minConf, 60.0, false,                   // WaveLabeler params
bufIdx, bar
```

## Dependencies

- SwingEngine (for swing detection)
- FibEngine (for Fibonacci levels to validate wave structure)

## Cross-References

- [[wiki/concepts/wave-exhaustion-exit|Wave Exhaustion Exit]] — Uses completion probability
- [[wiki/entities/ew-auto-tp|EWAutoTP]] — Primary consumer
