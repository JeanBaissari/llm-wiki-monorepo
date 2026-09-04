---
type: review
status: open
severity: warning
entity: ew-auto-tp
created: 2026-08-17
related:
  - "ew-auto-tp"
  - "extern-inputs-in-include"
---

# EWAutoTP — Section 8 Function Collision

## Issue

Section 8 of EWAutoTP redefines `PipFactor()`, `LogInfo()`, and `LogError()` inline. These COLLIDE with `core/Logger` and `ew/EWHelpers` when included together.

## Impact

Compilation error or linker conflict when EWAutoTP is included alongside modules that already define these functions.

## Recommendation

Drop one copy at integration time. Prefer the `core/Logger` and `ew/EWHelpers` versions. Remove or `#ifdef`-guard the inline redefinitions in Section 8.
