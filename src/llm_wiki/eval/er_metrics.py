#!/usr/bin/env python3
"""er_metrics.py — Entity-resolution quality metrics (LWM_025 gate).

Pairwise precision / recall / F1 over merge clusters — the gate metric that keeps
entity resolution from over- or under-merging. A gold set is a list of clusters
(each a set of surface forms that refer to one entity); predictions come from
``resolve.resolve_entities`` via ``merges_to_clusters``.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Iterable


def _pairs(clusters: "Iterable[set[str]]") -> "set[tuple[str, str]]":
    out: "set[tuple[str, str]]" = set()
    for c in clusters:
        for a, b in combinations(sorted(c), 2):
            out.add((a, b))
    return out


def merges_to_clusters(merges: "list[dict]") -> "list[set[str]]":
    """Group merge dicts (alias + canonical_label) into predicted clusters."""
    by_canon: "dict[str, set[str]]" = defaultdict(set)
    for m in merges:
        cid = m["canonical_id"]
        by_canon[cid].add(m["alias"])
        by_canon[cid].add(m.get("canonical_label", cid))
    return [s for s in by_canon.values() if len(s) > 1]


def er_f1(gold_clusters: "list[set[str]]", pred_clusters: "list[set[str]]") -> dict:
    """Pairwise ER precision/recall/F1. Empty gold+pred → perfect (nothing to merge)."""
    gold = _pairs(gold_clusters)
    pred = _pairs(pred_clusters)
    tp = len(gold & pred)
    fp = len(pred - gold)
    fn = len(gold - pred)
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }
