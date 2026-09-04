---
type: entity
title: Ind Parabolic
tags:
  - indicator
  - mt5
  - parabolic-sar
  - trend
related:
  - concepts/parabolic-sar-calculation
  - concepts/acceleration-factor
  - concepts/extreme-point-tracking
  - concepts/sar-reversal-logic
  - concepts/sar-clamping
sources:
  - raw/src/indicators/Ind_Parabolic.mq5
created: 2026-08-17
updated: 2026-08-17
language: mql5
namespace: indicators
status: active
version: "1.00"
dependencies: []
---

# Ind Parabolic

Parabolic Stop-And-Reversal indicator for MT5. Implements Wilder's classic SAR algorithm with incremental state management.

## Overview

Standard Parabolic SAR indicator that plots dots above/below price to indicate trend direction and potential reversals. Arrow code 159 (small dot) in lime color.

## Input Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `InpSARStep` | 0.02 | Acceleration factor increment |
| `InpSARMaximum` | 0.2 | Maximum acceleration factor |

## State Variables

| Variable | Type | Purpose |
|----------|------|---------|
| `ExtLastReverse` | int | Bar index of last reversal |
| `ExtDirectionLong` | bool | Current direction (true = long) |
| `ExtLastStep` | double | Current acceleration factor |
| `ExtLastEP` | double | Extreme point |
| `ExtLastSAR` | double | Last SAR value |
| `ExtLastHigh` | double | Highest high since reversal |
| `ExtLastLow` | double | Lowest low since reversal |

## Algorithm

1. **Initialization**: Detects initial direction by finding first bar with clear high/low pattern
2. **SAR Calculation**: `sar = previous_sar + step * (extreme_point - previous_sar)`
3. **Acceleration**: Step increases by `ExtSarStep` when new extreme is reached
4. **Reversal**: Triggered when SAR crosses price
5. **Clamping**: SAR clamped to not exceed previous 2 bars' lows (long) or highs (short)

## Key Implementation Details

- Minimum 3 bars required for calculation
- Input validation with fallback defaults (0.02 for step, 0.2 for maximum)
- Incremental calculation using saved state variables
- `SaveLastReverse` enforces minimum index of 2

## Usage

Standard Parabolic SAR application:
- Dots below price = bullish trend
- Dots above price = bearish trend
- Dot color change = potential reversal signal
