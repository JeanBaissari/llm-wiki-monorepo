"""Tests for the semantic eval harness core (LWM_022 / ADR-0022).

Deterministic, stdlib-only. Covers ranking metrics, the fail-closed disjoint
tune/gate invariant, the gibberish->empty negative case, and end-to-end
evaluate() with split filtering.
"""

import pytest

from llm_wiki.eval import (
    EvalReport,
    GoldSet,
    GoldSetError,
    evaluate,
    f1,
    negative_pass,
    parse_goldset,
    precision_at_k,
    recall_at_k,
)


# ── metrics ────────────────────────────────────────────────────────────────

def test_precision_at_k():
    pred = ["a", "b", "c", "d"]
    assert precision_at_k(pred, {"a", "c"}, 4) == 0.5
    assert precision_at_k(pred, {"a"}, 1) == 1.0
    assert precision_at_k(pred, {"z"}, 3) == 0.0
    assert precision_at_k([], {"a"}, 5) == 0.0
    assert precision_at_k(pred, {"a"}, 0) == 0.0


def test_recall_at_k():
    pred = ["a", "b", "c"]
    assert recall_at_k(pred, {"a", "c"}, 3) == 1.0
    assert recall_at_k(pred, {"a", "z"}, 3) == 0.5
    # empty gold set → recall undefined, treated as 1.0 (scored via negative_pass)
    assert recall_at_k(pred, set(), 3) == 1.0


def test_f1():
    assert f1(1.0, 1.0) == 1.0
    assert f1(0.0, 0.0) == 0.0
    assert f1(0.5, 0.5) == 0.5


def test_negative_pass_is_gibberish_empty_rule():
    assert negative_pass([]) == 1.0
    assert negative_pass(["anything"]) == 0.0


# ── gold set: disjoint tune/gate invariant (fail closed) ────────────────────

def test_goldset_rejects_overlapping_tune_and_gate():
    data = {
        "version": 1,
        "items": [
            {"query": "shared", "relevant": ["p1"], "split": "tune"},
            {"query": "shared", "relevant": ["p1"], "split": "gate"},
        ],
    }
    with pytest.raises(GoldSetError):
        parse_goldset(data)


def test_goldset_rejects_bad_split():
    data = {"items": [{"query": "q", "relevant": [], "split": "holdout"}]}
    with pytest.raises(GoldSetError):
        parse_goldset(data)


def test_goldset_splits_are_separable():
    data = {
        "items": [
            {"query": "t1", "relevant": ["a"], "split": "tune"},
            {"query": "g1", "relevant": ["b"], "split": "gate"},
            {"query": "gneg", "relevant": [], "split": "gate", "kind": "negative"},
        ],
    }
    gs = parse_goldset(data)
    assert {i.query for i in gs.tune} == {"t1"}
    assert {i.query for i in gs.gate} == {"g1", "gneg"}
    assert any(i.is_negative for i in gs.gate)


# ── end-to-end evaluate() ───────────────────────────────────────────────────

def _sample_goldset() -> GoldSet:
    return parse_goldset(
        {
            "items": [
                {"query": "karpathy", "relevant": ["entities/andrej-karpathy"], "split": "gate"},
                {"query": "neural net", "relevant": ["concepts/neural-network"], "split": "gate"},
                {"query": "zzzznonexistent", "relevant": [], "split": "gate", "kind": "negative"},
                {"query": "tuning-only", "relevant": ["concepts/x"], "split": "tune"},
            ]
        }
    )


def test_evaluate_perfect_predictions_on_gate_split():
    gs = _sample_goldset()
    preds = {
        "karpathy": ["entities/andrej-karpathy"],
        "neural net": ["concepts/neural-network"],
        "zzzznonexistent": [],  # correctly empty
    }
    rep = evaluate(preds, gs, k=5, split="gate")
    assert isinstance(rep, EvalReport)
    assert rep.n_positive == 2 and rep.n_negative == 1
    assert rep.precision_at_k == 1.0
    assert rep.recall_at_k == 1.0
    assert rep.f1 == 1.0
    assert rep.negative_pass_rate == 1.0


def test_evaluate_penalizes_gibberish_hit_and_misses():
    gs = _sample_goldset()
    preds = {
        "karpathy": ["wrong/page"],          # miss
        "neural net": ["concepts/neural-network"],  # hit
        "zzzznonexistent": ["some/page"],    # should have been empty
    }
    rep = evaluate(preds, gs, k=5, split="gate")
    assert rep.precision_at_k == 0.5   # 1 of 2 positives correct @k
    assert rep.negative_pass_rate == 0.0
    assert rep.to_dict()["split"] == "gate"


def test_evaluate_split_filter_excludes_tune_items():
    gs = _sample_goldset()
    rep_gate = evaluate({}, gs, split="gate")
    rep_all = evaluate({}, gs, split=None)
    assert rep_gate.n_positive == 2
    assert rep_all.n_positive == 3  # includes the tune item
