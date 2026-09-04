---
type: concept
confidence: high
contested: false
implemented_by:
  - "order-persistence"
related:
  - "order-persistence"
  - "grid-level-reconstruction"
  - "corderops"
sources:
  - "raw/src5/trading/OrderPersistence.mqh"
created: 2026-08-17
updated: 2026-08-17
---

# Grid Level Reconstruction

Rebuilds grid state from open orders after an EA restart by collecting and sorting open prices.

## Definition

Grid EAs maintain a set of price levels at which orders are placed. When the EA restarts, this grid must be reconstructed from the currently open orders. Grid level reconstruction collects all open prices, sorts them, and computes average spacing.

## Algorithm

```
1. Scan all open orders for this EA (magic + symbol)
2. Collect openPrice for each order into g_gridLevels[]
3. Sort g_gridLevels ascending
4. Compute average spacing:
     totalSpacing = sum(g_gridLevels[j] - g_gridLevels[j-1]) for j=1..count-1
     g_gridSpacing = totalSpacing / (count - 1)  // in price
     g_gridSpacing = ToPips(g_gridSpacing)        // convert to pips
```

## Next Grid Level

`GetNextGridLevel(isBuy)` uses the reconstructed grid to compute the next entry:

- **Buy**: `g_gridLevels[0] - spacing` (below lowest level)
- **Sell**: `g_gridLevels[g_gridCount - 1] + spacing` (above highest level)

Spacing is computed from `inp_GridSpacingPips * pipValue` (not the reconstructed spacing).

## State Variables Set

| Variable | Type | Description |
|----------|------|-------------|
| `g_gridLevels[]` | double[] | Sorted array of grid price levels |
| `g_gridCount` | int | Number of grid levels |
| `g_gridSpacing` | double | Average spacing in pips |

## Limitations

- **Uneven grids**: If grid levels were placed with different spacing, the average may not represent actual spacing accurately
- **No direction tracking**: The reconstructed grid does not distinguish buy vs sell levels
- **Spacing mismatch**: `GetNextGridLevel` uses `inp_GridSpacingPips` (input) rather than the reconstructed `g_gridSpacing`, so the next level may not align with existing grid geometry

## Cross-References

- [[wiki/entities/order-persistence|OrderPersistence]] — Implementation
- [[wiki/entities/corderops|COrderOps]] — Order access wrapper
- [[wiki/concepts/gv-state-persistence|GV State Persistence]] — Alternative persistence for grid state
