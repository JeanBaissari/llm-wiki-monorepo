---
type: concept
confidence: high
contested: false
implemented_by:
  - "ew-auto-tp"
related:
  - "ind-ew-fibengine"
  - "ind-ew-kennedychannel"
  - "ind-ew-wavelabeler"
  - "ind-ew-confirmationengine"
sources:
  - "raw/src5/shared/modules/ew/EWAutoTP.mqh"
created: 2026-08-17
updated: 2026-08-17
---

# Indicator Buffer Constants

Named constants mapping buffer indices for the 4 consumed indicators. Used by EWAutoTP to read specific data from each indicator.

## FibEngine Constants

| Constant | Buffer | Description |
|----------|--------|-------------|
| `FE_BUF_161` | 3 | 161.8% extension price (carry-forward) |
| `FE_BUF_261` | 4 | 261.8% extension price (carry-forward) |
| `FE_BUF_LEG_START` | 6 | Wave leg start price (carry-forward) |
| `FE_BUF_LEG_END` | 7 | Wave leg end price (carry-forward) |

## KennedyChannel Constants

| Constant | Buffer | Description |
|----------|--------|-------------|
| `KC_BUF_BASE_UPPER` | 0 | Base channel upper boundary |
| `KC_BUF_BASE_LOWER` | 1 | Base channel lower boundary |
| `KC_BUF_ACCEL_UPPER` | 2 | Acceleration channel upper |
| `KC_BUF_ACCEL_LOWER` | 3 | Acceleration channel lower |
| `KC_BUF_FINAL_UPPER` | 4 | Final channel upper |
| `KC_BUF_FINAL_LOWER` | 5 | Final channel lower |
| `KC_BUF_BREAK` | 6 | Break signal: 0=none, 1.0=confirmed, 2.0=+retest |
| `KC_BUF_VALIDITY` | 7 | Channel validity score 0-100 |
| `KC_BUF_TRAILING_STOP` | 8 | Dynamic trailing stop price (EMPTY_VALUE when inactive) |

## WaveLabeler Constants

| Constant | Buffer | Description |
|----------|--------|-------------|
| `EW_WL_WAVE_NUM` | 0 | Wave number: 1-5, 10=A, 11=B, 12=C, 0=IDLE, -1=UNCLASSIFIED |
| `EW_WL_WAVE_STATE` | 1 | Wave state: 0=IDLE, 1=FORMING, 2=COMPLETE |
| `EW_WL_COMPLETION_P` | 7 | Completion probability 0-100 (FORMING waves only) |

## ConfirmationEngine Constants

| Constant | Buffer | Description |
|----------|--------|-------------|
| `CE_BUF_CONF_COUNT` | 0 | Active confirmation count (0-5) |
| `CE_BUF_DIVERGENCE` | 3 | Divergence: -2=strong bear, -1=bear, 0=none, +1=bull, +2=strong bull |

## Divergence Signal Values

| Value | Constant | Meaning |
|-------|----------|---------|
| -2 | `CE_DIV_STRONG_BEAR` | Strong bearish divergence |
| -1 | `CE_DIV_BEAR` | Bearish divergence |
| 0 | `CE_DIV_NONE` | No divergence |
| +1 | `CE_DIV_BULL` | Bullish divergence |
| +2 | `CE_DIV_STRONG_BULL` | Strong bullish divergence |

## Carry-Forward Note

Buffers marked "carry-forward" retain their value across bars when no new data is available. This means stale values can persist — EWAutoTP must guard against EMPTY_VALUE and invalid prices.

## Cross-References

- [[wiki/entities/ew-auto-tp|EWAutoTP]] — Where these constants are defined
- [[wiki/entities/ind-ew-fibengine|Ind_EW_FibEngine]] — FibEngine buffer source
- [[wiki/entities/ind-ew-kennedychannel|Ind_EW_KennedyChannel]] — KennedyChannel buffer source
- [[wiki/entities/ind-ew-wavelabeler|Ind_EW_WaveLabeler]] — WaveLabeler buffer source
- [[wiki/entities/ind-ew-confirmationengine|Ind_EW_ConfirmationEngine]] — ConfirmationEngine buffer source
