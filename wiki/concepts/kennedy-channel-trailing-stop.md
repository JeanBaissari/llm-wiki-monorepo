---
type: concept
confidence: high
contested: false
implemented_by:
  - "ew-auto-tp"
related:
  - "auto-tp-adjustment"
  - "ind-ew-kennedychannel"
  - "wave-exhaustion-exit"
sources:
  - "raw/src5/shared/modules/ew/EWAutoTP.mqh"
created: 2026-08-17
updated: 2026-08-17
---

# Kennedy Channel Trailing Stop

Dynamic trailing stop that tightens the stop-loss based on Kennedy channel boundaries, adapting to the current wave stage.

## Definition

The Kennedy trailing stop uses KennedyChannel Buffer 8 (`KC_BUF_TRAILING_STOP`) to dynamically trail the stop-loss as the wave progresses. The trail tightens through progressively closer channel boundaries.

## Wave-Stage Behavior

| Wave Stage | Channel Used | Trail Direction |
|-----------|-------------|-----------------|
| During W3 | Base Channel lower | Below lower boundary |
| During W5 | Acceleration Channel lower | Below lower boundary |
| After completion | Final Channel lower | Below lower boundary |
| Bearish (any) | Mirror upper boundaries | Above upper boundary |

## Trail Movement Logic

```mql5
// BUY: only tighten (trail up)
if(orderType == OP_BUY && kennedyTrail > currentSL + _Point)
    shouldMove = true;

// SELL: only tighten (trail down)
if(orderType == OP_SELL && (currentSL <= 0 || kennedyTrail < currentSL - _Point))
    shouldMove = true;
```

The trail only moves in the favorable direction — it never loosens the stop.

## EMPTY_VALUE Handling

Buffer 8 returns `EMPTY_VALUE` when no channel is active. EWAutoTP guards against this:

```mql5
if(kennedyTrail == EMPTY_VALUE || kennedyTrail <= 0) return false;
```

No modification is made when the channel is inactive.

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `trailOffset` | 0.5 | ATR multiplier for breathing room |
| `trailATRPer` | 14 | ATR period for offset calculation |
| `wlFractalBars` | 2 | WaveLabeler SwingEngine FractalBars |
| `wlATRPer` | 14 | WaveLabeler SwingEngine ATRPeriod |
| `wlATRMult` | 1.0 | WaveLabeler SwingEngine ATRMult |
| `wlMinConf` | 50.0 | WaveLabeler MinConfidence |

## Relationship to TP Ladder

The Kennedy trailing stop runs independently of the TP ladder. Both execute per-order in the same bar cycle, but the trailing stop is applied after the TP ladder check. If exhaustion exit closes all orders, neither runs.

## Cross-References

- [[wiki/concepts/auto-tp-adjustment|Auto-TP Adjustment]] — Parent orchestration
- [[wiki/entities/ind-ew-kennedychannel|Ind_EW_KennedyChannel]] — Source of trailing stop price
- [[wiki/entities/ew-auto-tp|EWAutoTP]] — Implementation
