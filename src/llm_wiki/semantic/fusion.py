#!/usr/bin/env python3
"""fusion.py — Reciprocal Rank Fusion (RRF) for hybrid retrieval (LWM_019).

Fuses several ranked lists (e.g. FTS5/BM25 + vector KNN) by rank position only:

    score(item) = Σ_lists  1 / (k + rank)     (rank 1-based; k≈60)

Using ranks — not raw scores — means BM25 magnitudes and cosine similarities
never have to be normalized against each other, which is the whole reason RRF is
the low-risk default for hybrid search (ADR-0020). Deterministic tie-break by
``(-score, item)``. Pure stdlib.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Sequence

DEFAULT_K = 60


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[str]], k: int = DEFAULT_K
) -> "list[tuple[str, float]]":
    """Fuse ranked id lists via RRF → ``[(id, fused_score)]`` descending."""
    scores: dict[str, float] = defaultdict(float)
    for ranked in ranked_lists:
        for rank, item in enumerate(ranked, start=1):
            scores[item] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda t: (-t[1], t[0]))


def rrf_order(ranked_lists: Sequence[Sequence[str]], k: int = DEFAULT_K) -> "list[str]":
    """RRF-fused ids only (order), dropping the scores."""
    return [item for item, _ in reciprocal_rank_fusion(ranked_lists, k)]
