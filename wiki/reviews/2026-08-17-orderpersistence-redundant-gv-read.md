---
type: review
status: open
severity: info
entity: order-persistence
created: 2026-08-17
related:
  - "order-persistence"
  - "gv-state-persistence-pattern"
---

# OrderPersistence — Redundant Read in LoadStateFromGlobal

## Issue

`LoadStateFromGlobal()` reads each GV field twice: first with `ReadPersisted()` to check existence, then again with `ReadPersisted()` + `ParseDouble()` to extract the value. Each field incurs two I/O operations instead of one.

## Impact

- Double the GlobalVariable I/O calls per EA restart (10 calls for 5 fields instead of 5)
- Performance impact is negligible for 5 fields, but the pattern is wasteful
- More importantly, the first read's result (`_gvDummy`) is discarded — the value is re-read in the second call

## Recommendation

Use a single read and check:

```mql5
string frame;
if(CGlobalEventBus::GetInstance().ReadPersisted("GV." + prefix + "RecoveryLevel", frame))
{
    double tmp = 0;
    CGlobalEventBus::GetInstance().ParseDouble(frame, "value", tmp);
    g_recoveryLevel = (int)tmp;
}
```

This was partially done — the existence check uses `_gvDummy` but the parse re-reads. The variable `_gvFrame` in the second read is the correct one to use, but the pattern should be simplified to a single read.
