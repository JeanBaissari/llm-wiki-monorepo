---
type: concept
confidence: high
contested: false
implemented_by:
  - "ew-auto-tp"
related:
  - "auto-tp-adjustment"
  - "extension-detection"
sources:
  - "raw/src5/shared/modules/ew/EWAutoTP.mqh"
created: 2026-08-17
updated: 2026-08-17
---

# Adjust Delay

Configurable bar delay between extension detection and TP modification. Default: 2 bars.

## Definition

The adjust delay is a safety mechanism that prevents premature TP modification on transient price spikes. After extension is first detected, the system waits a configurable number of full bars before actually modifying the order.

## How It Works

1. Extension detected → detection time persisted via `CGlobalEventBus`
2. Each bar, `barsSinceDetection` is computed via `iBarShift()`
3. TP modification only executes when `barsSinceDetection >= adjustDelayBars`
4. Default `adjustDelayBars = 2`

## Purpose

- **Avoids whipsaw** — Price may briefly touch the 5% zone and retreat
- **Confirms momentum** — 2 bars of sustained proximity signals genuine extension
- **Human oversight window** — If `alertOnAdjust=true`, human is notified on first detection bar

## Alert Timing

Alert fires on the first bar of detection (`barsSinceDetection == 0`), giving the human `adjustDelayBars` bars to intervene if desired.

## State Management

Detection state is stored per-ticket in `CGlobalEventBus` with key `EW_AUTOTP_DET_<ticket>`. State is cleared when:
- Extension is no longer detected (price moves away)
- TP ladder step succeeds (state reset after modification)

## Cross-References

- [[wiki/concepts/auto-tp-adjustment|Auto-TP Adjustment]] — Parent orchestration
- [[wiki/concepts/extension-detection|Extension Detection]] — What triggers the delay
- [[wiki/entities/ew-auto-tp|EWAutoTP]] — Implementation
