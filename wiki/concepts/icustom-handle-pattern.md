---
type: concept
title: "iCustom Handle Pattern"
confidence: high
contested: false
implemented_by:
  - "wiki/entities/mt5-algo-suite"
tags:
  - mql5
  - indicators
  - icustom
  - handles
related:
  - "wiki/concepts/mql5-coding-standards"
  - "wiki/concepts/indicator-buffer-rules"
  - "wiki/sources/standards-md"
created: 2026-08-18
updated: 2026-08-18
---

# iCustom Handle Pattern

Every custom indicator called from an EA must use the handle-based pattern. Handles are created once in `OnInit` and cached in global variables. `OnTick`/`OnCalculate` only calls `CopyBuffer` — never `iCustom`.

## Implementation

```mql5
// Global handle cache — one per indicator
int g_handleATR = INVALID_HANDLE;
int g_handleFVG = INVALID_HANDLE;

int OnInit() {
   // Create all handles in OnInit (never deferred)
   g_handleATR = iCustom(_Symbol, PERIOD_CURRENT,
      "::Indicators\\custom\\ATR\\Ind_CustomATR.ex5",
      inp_ATRPeriod, inp_ATRMultiplier);
   if (g_handleATR == INVALID_HANDLE) {
      Print("Failed to create handle for Ind_CustomATR");
      return INIT_FAILED;
   }

   g_handleFVG = iCustom(_Symbol, PERIOD_CURRENT,
      "::Indicators\\custom\\FVG\\Ind_FVGDetector.ex5",
      inp_FVGLookback);
   if (g_handleFVG == INVALID_HANDLE) {
      Print("Failed to create handle for Ind_FVGDetector");
      return INIT_FAILED;
   }

   return INIT_SUCCEEDED;
}

void OnTick() {
   double atrBuf[1], fvgBuf[1];
   ArraySetAsSeries(atrBuf, true);
   ArraySetAsSeries(fvgBuf, true);

   // CopyBuffer only in OnTick — never iCustom
   if (CopyBuffer(g_handleATR, 0, 0, 1, atrBuf) < 1) return;
   if (CopyBuffer(g_handleFVG, 0, 0, 1, fvgBuf) < 1) return;

   double atr = atrBuf[0];
   double fvg = fvgBuf[0];
   // ... trade logic ...
}

void OnDeinit(const int reason) {
   // Release handles on deinit
   if (g_handleATR != INVALID_HANDLE) IndicatorRelease(g_handleATR);
   if (g_handleFVG != INVALID_HANDLE) IndicatorRelease(g_handleFVG);
}
```

## Rules

1. Every `iCustom` call is in `OnInit`, not `OnTick`
2. Each handle is stored in a `int g_*Handle` global variable
3. Handle validity checked: `== INVALID_HANDLE`, returning `INIT_FAILED`
4. All handles released in `OnDeinit` via `IndicatorRelease()`
5. `CopyBuffer` calls check `< countNeeded` — early return on failure

## Purpose

- Prevents handle leaks
- Ensures indicators are initialized before use
- Reduces overhead in OnTick (CopyBuffer is faster than iCustom)
