---
type: concept
confidence: high
contested: false
implemented_by:
  - "ew-auto-tp"
related:
  - "fibonacci-extension-ladder"
  - "kennedy-channel-trailing-stop"
  - "wave-exhaustion-exit"
  - "extension-detection"
  - "adjust-delay"
  - "ind-ew-fibengine"
  - "ind-ew-kennedychannel"
  - "ind-ew-wavelabeler"
  - "ind-ew-confirmationengine"
sources:
  - "raw/src5/shared/modules/ew/EWAutoTP.mqh"
created: 2026-08-17
updated: 2026-08-17
---

# Auto-TP Adjustment

Dynamic take-profit management during Wave 3 extensions. Progressively upgrades TP targets as price moves through Fibonacci extension levels, while applying Kennedy channel trailing stops and closing on wave exhaustion.

## Definition

Auto-TP is a three-phase per-bar orchestration that manages take-profit levels dynamically:

1. **Exhaustion exit** — If wave exhaustion detected (completion > 80 + divergence), close all orders immediately
2. **TP ladder upgrade** — If price approaches 161.8% extension (within 5% buffer), step TP to next Fibonacci level
3. **Kennedy trailing stop** — Apply dynamic trailing stop from Kennedy channel boundary

## How It Works

The system reads Fibonacci extension prices from FibEngine and wave state from WaveLabeler. When price approaches the 161.8% target, a detection timer starts. After a configurable delay (default 2 bars), the TP is upgraded to 261.8%, and subsequently to 423.6% if price continues extending.

Separately, the Kennedy channel trailing stop tightens the stop-loss as the wave progresses through W3 → W5 → completion, using progressively tighter channel boundaries.

## Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `inp_AutoAdjustTP` | true | Enable auto TP modification |
| `inp_AlertOnAdjust` | true | Alert human before modifying |
| `inp_AdjustDelayBars` | 2 | Bars to wait after detection |
| `inp_ProfileID` | 1 | EW system profile ID |

## Persistence

Detection timing is persisted via `CGlobalEventBus` per-ticket. Key format: `EW_AUTOTP_DET_<ticket>`. State is cleared when extension is no longer detected or after successful ladder step.

## When It Does NOT Act

- If exhaustion exit closes all orders first (Phase 1 gates Phase 2-3)
- If price hasn't reached the 5% proximity zone around 161.8%
- If the adjustment delay hasn't elapsed yet
- If Kennedy trailing stop returns EMPTY_VALUE (no active channel)
- If the order's SL is already tighter than the Kennedy trail

## Cross-References

- [[wiki/concepts/fibonacci-extension-ladder|Fibonacci Extension Ladder]] — TP stepping logic
- [[wiki/concepts/kennedy-channel-trailing-stop|Kennedy Channel Trailing Stop]] — Trailing stop logic
- [[wiki/concepts/wave-exhaustion-exit|Wave Exhaustion Exit]] — Exit trigger
- [[wiki/concepts/extension-detection|Extension Detection]] — Proximity detection
- [[wiki/entities/ew-auto-tp|EWAutoTP]] — Implementation
