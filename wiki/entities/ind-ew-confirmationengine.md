---
type: entity
language: mql5
namespace: indicators/ew
status: active
version: "unknown"
tags:
  - elliott-wave
  - confirmation
  - divergence
  - rsi
  - bollinger
  - volume
  - indicator
related:
  - "ew-auto-tp"
  - "wave-exhaustion-exit"
  - "circular-dependency-prevention"
  - "ind-ew-kennedychannel"
  - "ind-ew-wavelabeler"
sources:
  - "raw/src5/indicators/ew/Ind_EW_ConfirmationEngine.mq4"
created: 2026-08-17
updated: 2026-08-17
---

# Ind_EW_ConfirmationEngine

Multi-factor confirmation engine combining RSI, Bollinger Bands, divergence, volume, and optionally Kennedy channel signals.

## Role in EWAutoTP

EWAutoTP consumes 2 buffers from ConfirmationEngine:

| Buffer | Constant | Description |
|--------|----------|-------------|
| 0 | `CE_BUF_CONF_COUNT` | Active confirmation count (0-5) |
| 3 | `CE_BUF_DIVERGENCE` | Divergence: -2=strong bear, -1=bear, 0=none, +1=bull, +2=strong bull |

Buffer 3 (`CE_BUF_DIVERGENCE`) is critical for exhaustion exit: when completion > 80 AND divergence != 0, all orders are closed.

## Divergence Signal Values

| Value | Constant | Meaning |
|-------|----------|---------|
| -2 | `CE_DIV_STRONG_BEAR` | Strong bearish divergence |
| -1 | `CE_DIV_BEAR` | Bearish divergence |
| 0 | `CE_DIV_NONE` | No divergence |
| +1 | `CE_DIV_BULL` | Bullish divergence |
| +2 | `CE_DIV_STRONG_BULL` | Strong bullish divergence |

## Circular Dependency Prevention

`UseKennedy` is hardcoded to `false` when EWAutoTP reads ConfirmationEngine:

```mql5
false,  // UseKennedy=false (prevent circular dependency)
```

This prevents: ConfirmationEngine → KennedyChannel → ConfirmationEngine circular loading.

## iCustom Parameters

As called by `ReadConfirmationEngineAutoTP()` in EWAutoTP:

```
"EW\\Ind_EW_ConfirmationEngine",
true, 14, 75.0, 25.0,       // UseRSI, RSIPeriod, RSIOverbought, RSIOversold
true, 20, 2.0,               // UseBB, BBPeriod, BBDeviation
true, 14,                    // UseDivergence, DivergenceLookback
true, 1.5,                   // UseVolume, VolumeSpikeMultiplier
false,                       // UseKennedy=false (prevent circular dependency)
profileId, false, 0,         // ProfileID, UseSync, Theme
bufIdx, bar
```

## Dependencies

- RSI (built-in)
- Bollinger Bands (built-in)
- Volume analysis
- Optionally: KennedyChannel (disabled in EWAutoTP context)

## Cross-References

- [[wiki/concepts/wave-exhaustion-exit|Wave Exhaustion Exit]] — Uses divergence signal
- [[wiki/concepts/circular-dependency-prevention|Circular Dependency Prevention]] — UseKennedy=false pattern
- [[wiki/entities/ew-auto-tp|EWAutoTP]] — Primary consumer
