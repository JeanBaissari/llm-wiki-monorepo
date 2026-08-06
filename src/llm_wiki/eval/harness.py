#!/usr/bin/env python3
"""harness.py — Evaluate ranked predictions against a gold set.

Combines the pure metrics (``metrics.py``) with the gold-set contract
(``goldset.py``) to produce an absolute report: mean precision@k / recall / F1
over positive items, plus the negative-pass rate (gibberish → empty). The
report is what LWM_023 commits as a baseline and gates future changes against.

The evaluator is retrieval-source-agnostic: it takes a
``predictions: {query -> [ranked item ids]}`` mapping, so it works for the
current lexical link-suggester today and for hybrid/semantic suggesters later
without change.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping, Optional, Sequence

from llm_wiki.eval.goldset import GoldItem, GoldSet, Split
from llm_wiki.eval.metrics import (
    f1,
    mean,
    negative_pass,
    precision_at_k,
    recall_at_k,
)


@dataclass(frozen=True)
class EvalReport:
    k: int
    split: Optional[str]
    n_positive: int
    n_negative: int
    precision_at_k: float
    recall_at_k: float
    f1: float
    negative_pass_rate: float

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate(
    predictions: Mapping[str, Sequence[str]],
    goldset: GoldSet,
    k: int = 5,
    split: Optional[Split] = None,
) -> EvalReport:
    """Score ``predictions`` against ``goldset`` (optionally one split only)."""
    items: list[GoldItem] = (
        goldset.items if split is None else goldset.by_split(split)
    )

    p_scores: list[float] = []
    r_scores: list[float] = []
    f_scores: list[float] = []
    n_scores: list[float] = []

    for it in items:
        predicted = list(predictions.get(it.query, []))
        if it.is_negative:
            n_scores.append(negative_pass(predicted))
            continue
        p = precision_at_k(predicted, it.relevant, k)
        r = recall_at_k(predicted, it.relevant, k)
        p_scores.append(p)
        r_scores.append(r)
        f_scores.append(f1(p, r))

    return EvalReport(
        k=k,
        split=split,
        n_positive=len(p_scores),
        n_negative=len(n_scores),
        precision_at_k=round(mean(p_scores), 6),
        recall_at_k=round(mean(r_scores), 6),
        f1=round(mean(f_scores), 6),
        negative_pass_rate=round(mean(n_scores), 6),
    )
