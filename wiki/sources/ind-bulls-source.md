---
type: source
title: Ind Bulls Source
authors:
  - Baissari Enterprises
year: 2026
url: https://www.baissarienterprises.com
venue: MQL5 Source Code
tags:
  - mql5
  - indicator
  - bulls-power
related:
  - ind-bulls
  - bulls-power
created: 2026-08-17
updated: 2026-08-17
---

# Ind Bulls Source

Source code for the Bulls Power indicator in MQL5.

## File Location

```
raw/src/indicators/ind_bulls.mq5
```

## Code Analysis

### Header Properties

```mql5
#property copyright "https://www.baissarienterprises.com"
#property version "1.00"
#property description "Bulls Power"
#property strict
```

- **Author**: Baissari Enterprises
- **Version**: 1.00
- **Description**: Bulls Power indicator

### Indicator Properties

```mql5
#property indicator_separate_window
#property indicator_plots 1
#property indicator_buffers 2
#property indicator_type1 DRAW_HISTOGRAM
#property indicator_color1 clrSilver
```

- Displays in separate window
- Single plot (histogram)
- Two buffers (data + calculations)
- Silver color for histogram bars

### Input Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `InpBullsPeriod` | int | 13 | EMA period for baseline calculation |

### Buffer Allocation

```mql5
double ExtBullsBuffer[];    // INDICATOR_DATA - Bulls Power values
double ExtTempBuffer[];     // INDICATOR_CALCULATIONS - EMA values
```

### OnInit Function

1. Sets up indicator buffers with `SetIndexBuffer()`
2. Configures plot type as DRAW_HISTOGRAM
3. Sets empty value to EMPTY_VALUE
4. Configures indicator digits to match symbol
5. Creates short name "Bulls(period)"
6. Creates EMA handle using `iMA()`:
   - Symbol: `_Symbol` (current chart)
   - Period: `_Period` (current timeframe)
   - MA Period: `InpBullsPeriod`
   - MA Shift: 0
   - MA Method: `MODE_EMA`
   - Applied Price: `PRICE_CLOSE`

### OnCalculate Function

```mql5
for(int i=0; i<limit; i++)
{
    ExtTempBuffer[i] = maBuf[i];
    ExtBullsBuffer[i] = high[i] - ExtTempBuffer[i];
}
```

**Logic:**
1. Calculate limit based on `rates_total` and `prev_calculated`
2. Copy EMA buffer data using `CopyBuffer()`
3. For each bar: `Bulls Power = High - EMA`
4. Store EMA in temp buffer for reference

### Error Handling

- Returns `INIT_FAILED` if EMA handle creation fails
- Returns `0` if not enough bars (`rates_total <= InpBullsPeriod`)
- Returns `0` if `CopyBuffer()` fails

## Implementation Notes

1. **Incremental Calculation**: Uses `prev_calculated` to avoid recalculating all bars
2. **Handle-based**: Uses `iMA()` handle for efficient EMA calculation
3. **Array Direction**: Arrays are not set as series (oldest to newest)
4. **Memory Management**: Buffers are automatically managed by MT5

## Code Quality Observations

- Clean, straightforward implementation
- Proper error handling for handle creation
- Efficient incremental calculation
- No unnecessary complexity

## Related

- [[wiki/entities/ind-bulls|Ind Bulls]] — Entity page for this indicator
- [[wiki/concepts/bulls-power|Bulls Power]] — Trading concept explanation
