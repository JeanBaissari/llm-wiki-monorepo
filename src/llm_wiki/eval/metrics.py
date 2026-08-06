#!/usr/bin/env python3
"""metrics.py — Retrieval / link-suggestion evaluation metrics.

Pure, stdlib-only ranking metrics used by the semantic eval harness (LWM_022).
All functions take a ranked list of predicted item ids and a set of relevant
(gold) ids. Absolute numbers are reported — not just deltas — so a baseline is
interpretable on its own (ADR-0022).

Negative items (empty relevant set, e.g. gibberish queries) are scored by
``negative_pass``: a correct system returns nothing for them. This encodes the
"gibberish → empty" invariant the adversarial audit required.
"""

from __future__ import annotations

from typing import Iterable, Sequence


def precision_at_k(predicted: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Precision over the returned top-k: ``hits / len(top-k)``.

    Note this divides by the number of items actually returned (≤ k), not by k.
    That is intentional for variable-length suggestion lists — a source page with
    only two correct links that returns exactly those two scores 1.0, not 2/k.
    Callers must pass a de-duplicated ranked list (distinct ids); duplicates are
    removed upstream (e.g. ``eval.baseline.predictions_for``), not here.
    """
    if k <= 0:
        return 0.0
    rel = set(relevant)
    topk = list(predicted)[:k]
    if not topk:
        return 0.0
    hits = sum(1 for p in topk if p in rel)
    return hits / len(topk)


def recall_at_k(predicted: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Fraction of relevant items retrieved within the top-k."""
    rel = set(relevant)
    if not rel:
        # Undefined recall for an empty gold set; treat as perfect so negatives
        # are scored solely by negative_pass (below), not by recall.
        return 1.0
    topk = set(list(predicted)[:k])
    return len(topk & rel) / len(rel)


def f1(precision: float, recall: float) -> float:
    """Harmonic mean of precision and recall."""
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def negative_pass(predicted: Sequence[str]) -> float:
    """1.0 iff the system correctly returned nothing for a negative item."""
    return 1.0 if len(list(predicted)) == 0 else 0.0


def mean(values: Sequence[float]) -> float:
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0.0
