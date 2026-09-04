---
type: concept
title: EW Confidence Scoring
confidence: high
contested: false
tags: [elliott-wave, confidence, scoring, quality]
related:
  - "ind-ew-triangledetector"
  - "triangle-confidence-scoring"
  - "ind-ew-confidencescorer"
implemented_by:
  - "ind-ew-triangledetector"
  - "ind-ew-confidencescorer"
created: 2026-08-17
updated: 2026-08-17
---

# EW Confidence Scoring

Shared confidence scoring framework across Elliott Wave Suite indicators.

## Overview

Each EW indicator computes its own confidence score (0-100) based on pattern-specific quality signals. The framework is additive: a base score plus bonuses for geometric quality, Fibonacci alignment, and temporal symmetry.

## Indicator-Specific Implementations

| Indicator | Base | Max Signals | Key Dimensions |
|-----------|------|-------------|----------------|
| TriangleDetector (contracting) | 40 | 116 | Contraction quality, retracement, time symmetry, slope balance |
| TriangleDetector (running) | 45 | 121 | Same but with Fibonacci extension for B-wave |
| DiagonalDetector | varies | varies | Trendline convergence, wave overlap |
| FlatDetector | varies | varies | Retracement depth, B-wave extension |

## Common Patterns

- Base score accounts for pattern existence
- Tighter quality bands earn more points (e.g., 50-80% retracement > 40-85%)
- Time symmetry (non-zero spans) adds a consistent +10 bonus
- Score always clamped to [0, 100]
- Detection gated by configurable minimum threshold
