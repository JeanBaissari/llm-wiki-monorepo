---
type: concept
title: "Indicator Buffer Rules"
confidence: high
contested: false
implemented_by:
  - "wiki/entities/mt5-algo-suite"
tags:
  - mql5
  - indicators
  - buffers
related:
  - "wiki/concepts/mql5-coding-standards"
  - "wiki/sources/standards-md"
created: 2026-08-18
updated: 2026-08-18
---

# Indicator Buffer Rules

MT5 indicators are buffer-first: the primary contract is the data in the buffers, not the visual display.

## Buffer Types

Every buffer declaration must be explicit about its type:

```mql5
// WRONG — MQL4 style
SetIndexBuffer(0, g_lineBuffer);

// CORRECT — MQL5 style with explicit type
SetIndexBuffer(0, g_lineBuffer, INDICATOR_DATA);
SetIndexBuffer(1, g_tempBuffer, INDICATOR_CALCULATIONS);
SetIndexBuffer(2, g_colorBuffer, INDICATOR_COLOR);
```

## Rules

1. Always pass the third argument: `INDICATOR_DATA`, `INDICATOR_CALCULATIONS`, or `INDICATOR_COLOR`
2. Call `ArraySetAsSeries(arr, true)` on every buffer in `OnInit` that will be accessed with array indexes (0=current bar)
3. Use `PlotIndexSetInteger` for all drawing properties — never `SetIndexStyle` (deprecated in MQL5)
4. `#property indicator_plots` must exactly match the number of `INDICATOR_DATA` buffers
5. Maximum 512 buffers (MT5 limit), but keep below 16 for readability

## Buffer Type Semantics

| Type | Purpose | Example |
|------|---------|---------|
| `INDICATOR_DATA` | Plotted data visible on chart | MA line, RSI values |
| `INDICATOR_CALCULATIONS` | Internal calculations, not plotted | Temporary buffers, intermediate values |
| `INDICATOR_COLOR` | Color buffer for multi-color plots | Bar coloring based on condition |
