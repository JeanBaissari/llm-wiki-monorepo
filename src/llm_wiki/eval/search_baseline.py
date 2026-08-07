#!/usr/bin/env python3
"""search_baseline.py — Keyword-vs-hybrid search eval runner + gate (LWM_032).

Scores ``keyword`` and ``hybrid`` retrieval on a committed search gold set
(``query → relevant page-ids``, distinct from the link-suggestion set) and
provides the **fail-closed** promotion gate that certifies the v0.5.0 default
flip: hybrid may become the default only when, on the held-out GATE split,
``hybrid.recall ≥ keyword.recall - tol`` AND ``hybrid.precision@k ≥
keyword.precision@k - tol`` for every k, with gibberish negatives still empty.
See ADR-0020.
"""

from __future__ import annotations

from pathlib import Path

from llm_wiki.eval.metrics import mean, negative_pass, precision_at_k, recall_at_k

PRECISION_KS = (1, 3, 5, 10)
RECALL_K = 10
DEFAULT_TOL = 1e-6


def _page_id(path: str) -> str:
    return Path(path).stem


def run_search_baseline(wiki_root, items, mode: str, k: int = 10, embedder=None) -> dict:
    """Score one mode over gold ``items`` ([{query, relevant[], kind}]).

    Returns ``{mode, precision_at_k:{k:v}, recall, negative_pass_rate, n}``.
    """
    from llm_wiki.search.query import hybrid_search, keyword_search

    prec = {kk: [] for kk in PRECISION_KS}
    rec = []
    neg = []
    for item in items:
        query = item["query"]
        relevant = item.get("relevant", [])
        if mode == "keyword":
            res = keyword_search(wiki_root, query, max(k, RECALL_K))
        else:
            res = hybrid_search(wiki_root, query, max(k, RECALL_K), embedder=embedder)
        predicted = []
        for r in res:
            pid = _page_id(r["path"])
            if pid not in predicted:
                predicted.append(pid)

        if item.get("kind") == "negative" or not relevant:
            neg.append(negative_pass(predicted))
        else:
            for kk in PRECISION_KS:
                prec[kk].append(precision_at_k(predicted, relevant, kk))
            rec.append(recall_at_k(predicted, relevant, RECALL_K))

    return {
        "mode": mode,
        "precision_at_k": {kk: round(mean(prec[kk]), 6) for kk in PRECISION_KS},
        "recall": round(mean(rec), 6),
        "negative_pass_rate": round(mean(neg), 6) if neg else 1.0,
        "n": len(items),
    }


def search_eval_gate(keyword: dict, hybrid: dict, tol: float = DEFAULT_TOL) -> "tuple[bool, dict]":
    """Fail-closed promotion gate. Returns (allow_flip, report)."""
    recall_ok = hybrid["recall"] >= keyword["recall"] - tol
    prec_ok = all(
        hybrid["precision_at_k"][kk] >= keyword["precision_at_k"][kk] - tol
        for kk in PRECISION_KS
    )
    neg_ok = hybrid["negative_pass_rate"] >= 1.0 - tol
    allow = recall_ok and prec_ok and neg_ok
    report = {
        "recall_parity": recall_ok,
        "precision_no_regress": prec_ok,
        "negatives_empty": neg_ok,
        "allow_flip": allow,
        "keyword": keyword,
        "hybrid": hybrid,
        "reason": "hybrid >= keyword on GATE" if allow
                  else "fail-closed: hybrid regresses keyword on GATE",
    }
    return allow, report


def load_search_goldset(path) -> dict:
    """Load + validate the search gold set (asserts tune ∩ gate = ∅)."""
    import json

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("items", [])
    tune = {i["query"] for i in items if i.get("split") == "tune"}
    gate = {i["query"] for i in items if i.get("split") == "gate"}
    overlap = tune & gate
    if overlap:
        raise ValueError(f"search gold set tune∩gate must be empty; leaked: {sorted(overlap)}")
    return data


def split_items(data: dict, split: str) -> "list[dict]":
    return [i for i in data.get("items", []) if i.get("split") == split]
