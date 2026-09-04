---
type: concept
title: "Price/Symbol Access Rules"
confidence: high
contested: false
implemented_by:
  - "wiki/entities/mt5-algo-suite"
tags:
  - mql5
  - price-access
  - symbol-info
related:
  - "wiki/concepts/mql5-coding-standards"
  - "wiki/sources/standards-md"
created: 2026-08-18
updated: 2026-08-18
---

# Price/Symbol Access Rules

Rules that exist because MT5's execution model differs fundamentally from MT4's. Using old globals creates race conditions, incorrect values in backtest, and portability issues across brokers.

## MQL4 Anti-patterns vs MQL5 Correct Patterns

| MQL4 Anti-pattern | MQL5 Correct Pattern |
|-------------------|---------------------|
| `Ask` | `SymbolInfoDouble(_Symbol, SYMBOL_ASK)` |
| `Bid` | `SymbolInfoDouble(_Symbol, SYMBOL_BID)` |
| `Point` | `SymbolInfoDouble(_Symbol, SYMBOL_POINT)` |
| `Digits` | `(int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS)` |
| `iClose(sym, tf, shift)` | `CopyClose(sym, tf, shift, 1, buf)` |
| `iOpen(sym, tf, shift)` | `CopyOpen(sym, tf, shift, 1, buf)` |
| `iHigh(sym, tf, shift)` | `CopyHigh(sym, tf, shift, 1, buf)` |
| `iLow(sym, tf, shift)` | `CopyLow(sym, tf, shift, 1, buf)` |
| `iVolume(sym, tf, shift)` | `CopyTickVolume(sym, tf, shift, 1, buf)` |

## Correct Multi-Symbol Price Access

```mql5
double GetAsk(string symbol) {
   return SymbolInfoDouble(symbol, SYMBOL_ASK);
}

double GetBid(string symbol) {
   return SymbolInfoDouble(symbol, SYMBOL_BID);
}

bool GetClose(string symbol, ENUM_TIMEFRAMES tf, int shift, double &out) {
   double buf[1];
   if (CopyClose(symbol, tf, shift, 1, buf) < 1) return false;
   out = buf[0];
   return true;
}
```

## Rationale

- MT5 is multi-threaded — global variables create race conditions
- Backtest mode doesn't populate Ask/Bid globals correctly
- Broker portability requires SymbolInfo-based access
