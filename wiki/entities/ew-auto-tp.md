---
type: entity
language: mql5
namespace: shared/ew
status: active
version: "1.00"
tags:
  - elliott-wave
  - take-profit
  - trailing-stop
  - auto-tp
  - wave-3
  - fibonacci
  - kennedy-channel
  - exhaustion
related:
  - "ind-ew-fibengine"
  - "ind-ew-kennedychannel"
  - "ind-ew-wavelabeler"
  - "ind-ew-confirmationengine"
  - "ew-fibonacci"
  - "fibonacci-extension-ladder"
  - "kennedy-channel-trailing-stop"
  - "wave-exhaustion-exit"
  - "extension-detection"
sources:
  - "raw/src5/shared/modules/ew/EWAutoTP.mqh"
created: 2026-08-17
updated: 2026-08-17
---

# EWAutoTP

Auto-adjusting TP ladder, Kennedy trailing stop, and wave-exhaustion exit orchestrator.

## Purpose

Dynamic take-profit management during Wave 3 extensions. Orchestrates three phases per bar:

1. **Exhaustion exit** — Closes all magic-scoped orders when wave exhaustion is detected
2. **TP ladder upgrade** — Steps TP to next Fibonacci extension level on extension detection
3. **Kennedy trailing stop** — Applies dynamic trailing stop from Kennedy channel boundaries

## Module Structure

```
shared/ew/EWAutoTP.mqh
├── Section 1: Buffer-index constants (4 consumed indicators)
├── Section 2: iCustom() reader wrappers
├── Section 3: Extension proximity detection
├── Section 4: TP ladder stepping (161.8 → 261.8 → 423.6%)
├── Section 5: Kennedy channel trailing stop
├── Section 6: Wave exhaustion exit
└── Section 7: ManageAutoTP orchestrator
```

## Dependencies

| Dependency | Type | Purpose |
|-----------|------|---------|
| core/Logger | Include | Structured logging (LogInfo, LogError) |
| ew/EWHelpers | Include | Shared EW utility functions |
| ew/EWFibonacci | Include | Fibonacci calculation helpers |
| core/GlobalEventBus | Include | Per-ticket persistence (detection time tracking) |
| Ind_EW_FibEngine | Indicator | Fibonacci extension price levels |
| Ind_EW_KennedyChannel | Indicator | Kennedy channel boundaries + trailing stop |
| Ind_EW_WaveLabeler | Indicator | Wave number, state, completion probability |
| Ind_EW_ConfirmationEngine | Indicator | Confirmation count + divergence signal |

## Key Functions

### `ManageAutoTP()`
Master orchestrator. Runs extension detection, TP ladder upgrade, Kennedy trailing stop, and exhaustion exit for all open orders. Call from `ManageOpenTrades()` or new-bar section of `OnTick()`. Gate with `IsNewBar()`.

### `DetectExtension()`
Returns true when price approaches 161.8% TP target (within 5% buffer). Signals Wave 3 may be extending.

### `AdjustTPLadder()`
Steps TP to next Fibonacci extension level: 161.8% → 261.8% → 423.6%. Modifies order via `OrderModify()`, preserving current SL.

### `ApplyKennedyTrailing()`
Applies Kennedy channel trailing stop (Buffer 8). During W3: trails below Base Channel lower. During W5: Acceleration Channel lower. After completion: Final Channel lower.

### `CheckExhaustionExit()`
Closes all magic-number orders when: completion > 80 AND divergence != 0. Evaluated once per bar, shared across all orders.

### `ReadFibEngine()`, `ReadKennedyChannel()`, `ReadWaveLabelerAutoTP()`, `ReadConfirmationEngineAutoTP()`
iCustom() wrappers for the 4 consumed indicators. Each returns a single buffer value at a given bar shift.

## Buffer Constants

### FibEngine (Ind_EW_FibEngine)
| Constant | Buffer | Description |
|----------|--------|-------------|
| `FE_BUF_161` | 3 | 161.8% extension price (carry-forward) |
| `FE_BUF_261` | 4 | 261.8% extension price (carry-forward) |
| `FE_BUF_LEG_START` | 6 | Wave leg start price (carry-forward) |
| `FE_BUF_LEG_END` | 7 | Wave leg end price (carry-forward) |

### KennedyChannel (Ind_EW_KennedyChannel)
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

### WaveLabeler (Ind_EW_WaveLabeler)
| Constant | Buffer | Description |
|----------|--------|-------------|
| `EW_WL_WAVE_NUM` | 0 | Wave number: 1-5, 10=A, 11=B, 12=C, 0=IDLE, -1=UNCLASSIFIED |
| `EW_WL_WAVE_STATE` | 1 | Wave state: 0=IDLE, 1=FORMING, 2=COMPLETE |
| `EW_WL_COMPLETION_P` | 7 | Completion probability 0-100 (FORMING waves only) |

### ConfirmationEngine (Ind_EW_ConfirmationEngine)
| Constant | Buffer | Description |
|----------|--------|-------------|
| `CE_BUF_CONF_COUNT` | 0 | Active confirmation count (0-5) |
| `CE_BUF_DIVERGENCE` | 3 | Divergence: -2=strong bear, -1=bear, 0=none, +1=bull, +2=strong bull |

## Execution Flow

```
ManageAutoTP()
├── CheckExhaustionExit()          ← Phase 1: once per bar
│   └── if exhausted: return       ← skip all TP/trailing
├── ReadFibEngine(FE_BUF_161)      ← shared read
├── ReadFibEngine(FE_BUF_261)      ← shared read
└── for each open order:
    ├── DetectExtension()          ← Phase 2: per order
    │   └── if extending: AdjustTPLadder()
    └── ApplyKennedyTrailing()     ← Phase 3: per order
```

## Input Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `inp_AutoAdjustTP` | true | Enable auto TP adjustment |
| `inp_AlertOnAdjust` | true | Alert human before auto-adjustment |
| `inp_AdjustDelayBars` | 2 | Bars to wait before auto-modifying |
| `inp_ProfileID` | 1 | EW system profile ID |

## Known Issues

1. **Hardcoded indicator paths** — `"EW\\Ind_EW_FibEngine"` etc. are hardcoded strings, not parameterizable
2. **Section 8 collision** — Redefines `PipFactor()`, `LogInfo()`, `LogError()` inline, which COLLIDE with core/Logger and ew/EWHelpers when included together. Must drop one copy at integration time.
3. **Extern inputs in include file** — Input declarations violate the shared module standard (preserved for source fidelity)

## Portability

- **MQL5 only** — Uses `iCustom()` with indicator handles + `CopyBuffer`
- `OrderSelect`/`OrderModify`/`OrderClose` → `CTrade`/`COrderInfo`
- `CGlobalEventBus` persistence → chart globals or custom persistence layer

## Usage

```mql5
#include "src5/shared/modules/ew/EWAutoTP.mqh"

if(IsNewBar())
    ManageAutoTP(inp_MagicNumber, inp_AutoAdjustTP,
                 inp_AlertOnAdjust, inp_AdjustDelayBars,
                 inp_ProfileID);
```
