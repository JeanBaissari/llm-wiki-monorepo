---
type: review
status: open
severity: info
entity: order-persistence
created: 2026-08-17
related:
  - "order-persistence"
  - "partial-close-ticket-tracking"
---

# OrderPersistence — Linear Partial Close Scan Without Deduplication

## Issue

`IsPartialClosedTicket()` performs O(n) linear scan of `g_partialClosedTickets[]` array. `AddPartialClosedTicket()` appends without checking for duplicates, and the array never shrinks.

## Impact

- Performance degrades linearly with number of partially closed tickets per session
- Duplicate tickets can accumulate if `AddPartialClosedTicket` is called multiple times for the same ticket (defensive coding issue)
- Memory usage grows unbounded over long sessions (though practically limited by number of orders)

## Recommendation

1. Add deduplication check in `AddPartialClosedTicket`:
```mql5
void AddPartialClosedTicket(int ticket)
{
    if(IsPartialClosedTicket(ticket)) return; // already tracked
    g_partialClosedCount++;
    ArrayResize(g_partialClosedTickets, g_partialClosedCount);
    g_partialClosedTickets[g_partialClosedCount - 1] = ticket;
}
```

2. Consider using a bitmap or hash set for O(1) lookup if ticket counts are high
