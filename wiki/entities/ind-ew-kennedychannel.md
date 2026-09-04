---
type: entity
language: mql5
namespace: indicators/ew
status: active
version: "unknown"
tags:
  - elliott-wave
  - kennedy-channel
  - trailing-stop
  - channel
  - indicator
related:
  - "ew-auto-tp"
  - "kennedy-channel-trailing-stop"
  - "ind-ew-fibengine"
  - "ind-ew-wavelabeler"
  - "ind-ew-confirmationengine"
sources:
  - "raw/src5/indicators/ew/Ind_EW_KennedyChannel.mq4"
created: 2026-08-17
updated: 2026-08-17
---

# Ind_EW_KennedyChannel

Kennedy channel indicator providing dynamic channel boundaries and trailing stop levels.

## Role in EWAutoTP

EWAutoTP consumes 9 buffers from KennedyChannel:

| Buffer | Constant | Description |
|--------|----------|-------------|
| 0 | `KC_BUF_BASE_UPPER` | Base channel upper boundary |
| 1 | `KC_BUF_BASE_LOWER` | Base channel lower boundary |
| 2 | `KC_BUF_ACCEL_UPPER` | Acceleration channel upper |
| 3 | `KC_BUF_ACCEL_LOWER` | Acceleration channel lower |
| 4 | `KC_BUF_FINAL_UPPER` | Final channel upper |
| 5 | `KC_BUF_FINAL_LOWER` | Final channel lower |
| 6 | `KC_BUF_BREAK` | Break signal: 0=none, 1.0=confirmed, 2.0=+retest |
| 7 | `KC_BUF_VALIDITY` | Channel validity score 0-100 |
| 8 | `KC_BUF_TRAILING_STOP` | Dynamic trailing stop price (EMPTY_VALUE when inactive) |

Buffer 8 (`KC_BUF_TRAILING_STOP`) is the key buffer for EWAutoTP's trailing stop functionality.

## Trailing Stop Behavior

The Kennedy trailing stop adapts by wave stage:
- **During W3:** Trails below Base Channel lower boundary
- **During W5:** Trails below Acceleration Channel lower boundary
- **After completion:** Trails below Final Channel lower boundary
- **Bearish:** Mirrors above upper boundaries

## iCustom Parameters

As called by `ReadKennedyChannel()` in EWAutoTP:

```
"EW\\Ind_EW_KennedyChannel",
profileId, false, 0,                    // ProfileID, UseSync, Theme
wlFractalBars, wlATRPer, wlATRMult, wlMinConf,  // WL passthrough params
false, false, false, false,             // show flags off for EA
trailOffset, trailATRPer,               // trailing config
bufIdx, bar
```

## Dependencies

- WaveLabeler (for wave state to determine which channel boundary to trail)
- SwingEngine (for fractal detection)

## Circular Dependency Note

ConfirmationEngine has `UseKennedy` hardcoded to false to prevent circular dependency (ConfirmationEngine → KennedyChannel → ConfirmationEngine). EWAutoTP itself reads KennedyChannel directly, so it must not be loaded inside ConfirmationEngine.

## Cross-References

- [[wiki/concepts/kennedy-channel-trailing-stop|Kennedy Channel Trailing Stop]] — Trailing stop logic
- [[wiki/entities/ew-auto-tp|EWAutoTP]] — Primary consumer
