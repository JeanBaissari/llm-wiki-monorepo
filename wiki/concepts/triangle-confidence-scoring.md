---
type: concept
title: Triangle Confidence Scoring
confidence: high
contested: false
tags: [elliott-wave, triangle, confidence, scoring]
related:
  - "triangle-classification"
  - "ind-ew-triangledetector"
  - "ew-confidence-scoring"
implemented_by:
  - "ind-ew-triangledetector"
created: 2026-08-17
updated: 2026-08-17
---

# Triangle Confidence Scoring

Additive scoring system (0-100) evaluating triangle pattern quality across geometric, Fibonacci, and temporal dimensions.

## Contracting Triangle (base 40)

| Signal | Points | Condition |
|--------|--------|-----------|
| Good contraction | +15 | waveB < 0.9×waveA AND waveC < 0.9×waveB AND waveD < 0.9×waveC |
| B retracement (tight) | +15 | B/A ∈ [0.50, 0.80) |
| B retracement (loose) | +8 | B/A ∈ (0.40, 0.85) — exclusive of tight range |
| D retracement (tight) | +15 | D/C ∈ [0.50, 0.80) |
| D retracement (loose) | +8 | D/C ∈ (0.40, 0.85) — exclusive of tight range |
| Time symmetry | +10 | All wave spans > 0 |
| Slope balance | +5 | slopeRatio ∈ (0.3, 3.0) |

**Maximum possible**: 40 + 15 + 15 + 8 + 15 + 8 + 10 + 5 = 116, clamped to 100.

## Running Triangle (base 45)

| Signal | Points | Condition |
|--------|--------|-----------|
| Good contraction | +15 | waveC < 0.9×waveB AND waveD < 0.9×waveC |
| B retracement (tight) | +15 | B/A ∈ [1.00, 1.382] (Fibonacci extension) |
| B retracement (loose) | +8 | B/A ∈ (0.90, 1.618] — exclusive of tight range |
| D retracement (tight) | +15 | D/C ∈ [0.50, 0.80) |
| D retracement (loose) | +8 | D/C ∈ (0.40, 0.85) — exclusive of tight range |
| Time symmetry | +10 | All wave spans > 0 |
| Slope balance | +5 | slopeRatio ∈ (0.3, 1.0) |

**Maximum possible**: 45 + 15 + 15 + 8 + 15 + 8 + 10 + 5 = 121, clamped to 100.

## Design Notes

- Running triangles have a higher base (45 vs 40) because they represent stronger trend continuation
- Running B-wave targets the Fibonacci extension zone (100-138.2%) rather than retracement zone
- Score is clamped to [0, 100] via `MathMax(0, MathMin(100, confidence))`
- Detection requires confidence ≥ `inp_MinConfidence` (default 40)
