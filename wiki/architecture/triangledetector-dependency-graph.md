---
type: architecture
title: TriangleDetector Dependency Graph
architecture_type: dependency_graph
language: mql5
tags: [elliott-wave, architecture, dependency-graph]
related:
  - "ind-ew-triangledetector"
  - "ew-indicator-dependency-graph"
created: 2026-08-17
updated: 2026-08-17
---

# TriangleDetector Dependency Graph

Include and sub-indicator dependency structure for Ind_EW_TriangleDetector.

## Graph

```
Ind_EW_TriangleDetector.mq5
├── EW_Common.mqh (include)
│   ├── EW_Profile struct
│   ├── AutoCalibrate()
│   ├── LogInfo()
│   └── LogWarn()
├── Ind_EW_SwingEngine.ex5 (iCustom sub-indicator)
│   ├── Buffer 0: Swing High
│   ├── Buffer 1: Swing Low
│   ├── Buffer 2: Significance
│   └── Buffer 3: Swing Type
└── Ind_EW_WaveLabeler.ex5 (iCustom sub-indicator)
    └── Buffer 0: Wave Number
```

## Data Flow

1. `OnCalculate` copies price arrays to cache
2. `CollectRecentSwings` reads SwingEngine buffers → `SwingPt[]` array
3. Swings fed to `CheckContractingTriangle` or `CheckRunningTriangle`
4. If detection fails, `IsInvalidTrianglePosition` reads WaveLabeler buffer 0
5. Breakout state checked against previous bar close
6. Results written to 10 indicator buffers + chart objects
