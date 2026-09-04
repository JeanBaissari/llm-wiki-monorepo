---
type: concept
title: "Version Management"
confidence: high
contested: false
implemented_by:
  - "wiki/entities/mt5-algo-suite"
tags:
  - versioning
  - mql5
  - python
  - dll
related:
  - "wiki/concepts/mql5-coding-standards"
  - "wiki/sources/standards-md"
created: 2026-08-18
updated: 2026-08-18
---

# Version Management

Version consistency across languages prevents confusion when debugging issues across the MQL5 ↔ Python ↔ DLL stack. Each language uses its ecosystem's convention.

## Version Formats

### MQL5: `#property version "X.XX"`

MT5 uses two-decimal version strings. The format is `Major.Minor` where both are numeric and Minor is always padded to two digits:

```mql5
#property version "1.00"   // First release
#property version "1.05"   // Fifth minor patch
#property version "2.00"   // Major rewrite
```

Validators enforce the regex `^\d+\.\d{2}$`. The version in `#property` must match the `Version:` field in the file header block exactly.

### Python: Semantic Versioning

Python packages use `__version__ = "X.Y.Z"` following PEP 440:

```python
# src5/tools/__init__.py
__version__ = "1.2.3"  # Major.Minor.Patch
```

### DLL: FILEVERSION

DLLs declare version via `.rc` resource files:

```rc
VS_VERSION_INFO VERSIONINFO
 FILEVERSION 1,2,3,0
 PRODUCTVERSION 1,2,3,0
```

## Changelog Requirement

Every version bump — for an EA, indicator, module, Python package, or DLL — must include a corresponding entry in `CHANGELOG.md` in the same git commit. This is non-negotiable and enforced by CI.

## Contradiction Note

Three different versioning schemes (MQL5 "X.XX", Python "X.Y.Z", DLL "X,Y,Z") in one ecosystem may create confusion when correlating versions across the stack.
