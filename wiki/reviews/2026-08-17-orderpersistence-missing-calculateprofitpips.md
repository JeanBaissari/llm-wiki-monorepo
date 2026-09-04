---
type: review
status: open
severity: warning
entity: order-persistence
created: 2026-08-17
related:
  - "order-persistence"
  - "partial-close-ticket-tracking"
---

# OrderPersistence — Missing CalculateProfitPips Dependency

## Issue

`ApplyPartialClose()` calls `CalculateProfitPips(ticket)` which is declared nowhere in OrderPersistence.mqh or its included dependencies. The function is expected to be defined by the consuming EA.

## Impact

- Module will not compile standalone — requires EA-level function definition
- No type signature or contract documented for what `CalculateProfitPips` must return
- Different EAs may implement different profit calculation logic (including/excluding swaps, commissions)
- Silent behavioral differences if EA provides incompatible implementation

## Recommendation

Either:
1. Provide a default implementation in OrderPersistence that the EA can override, or
2. Accept a function pointer/delegate parameter, or
3. Document the required signature and contract explicitly in the header comment

At minimum, the expected signature should be documented:
```mql5
// EA must provide: double CalculateProfitPips(int ticket)
// Returns: profit in pips (positive = profit, negative = loss)
```
