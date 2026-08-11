"""LWM_034 contradiction eval gate — gold-set integrity + baseline + fail-on-drop.

Re-derives the committed ``tests/eval/baseline/contradiction_baseline.json``
from the frozen contradiction gold set + the deterministic gold wiki.
Precision/recall (full labeled set) and the held-out GATE split's
``gate_precision``/``gate_recall`` must match the committed artifact exactly
(reproducibility) and must not regress it (fail-on-drop, ADR-0022). Gold
negatives encode the near-miss families (unit-normalized equality,
consistency, distinct subjects, single claim) that must never be flagged.
"""

import json
from pathlib import Path

from llm_wiki.eval.contradiction_baseline import (
    build_contradiction_gold_wiki,
    compute_contradiction_baseline,
    load_contradiction_goldset,
    run_contradiction_baseline,
    split_items,
)

REPO_ROOT = Path(__file__).resolve().parent
GOLDSET = REPO_ROOT / "eval" / "gold" / "contradiction_goldset.json"
BASELINE = REPO_ROOT / "eval" / "baseline" / "contradiction_baseline.json"
_TOL = 1e-6


def _wiki(tmp_path):
    return build_contradiction_gold_wiki(tmp_path)


# ── gold-set integrity ─────────────────────────────────────────────────────

def test_contradiction_goldset_committed_and_wellformed():
    data = json.loads(GOLDSET.read_text(encoding="utf-8"))
    assert data["task"] == "contradiction-detection"
    assert data.get("items"), "contradiction gold set must have items"
    for item in data["items"]:
        assert "pair" in item and "expected" in item and "split" in item
        assert item["split"] in ("tune", "gate")
        assert item.get("kind") in ("positive", "negative")
        assert (item["expected"]) == (item["kind"] == "positive")
        for claim in item["pair"]:
            for field in ("page", "subject", "predicate", "object", "polarity"):
                assert field in claim


def test_contradiction_goldset_tune_gate_disjoint():
    data = load_contradiction_goldset(GOLDSET)  # raises ValueError on overlap
    tune = {i["family"] for i in data["items"] if i["split"] == "tune"}
    gate = {i["family"] for i in data["items"] if i["split"] == "gate"}
    assert tune and gate
    assert tune.isdisjoint(gate)


def test_contradiction_goldset_has_both_kinds_on_gate():
    data = load_contradiction_goldset(GOLDSET)
    gate = split_items(data, "gate")
    positives = [i for i in gate if i["expected"]]
    negatives = [i for i in gate if not i["expected"]]
    assert positives, "gate split needs known-contradictory positives"
    assert negatives, "gate split needs near-miss negatives"


# ── baseline reproducibility + fail-on-drop ────────────────────────────────

def test_contradiction_baseline_artifact_committed_and_wellformed():
    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    for key in ("task", "split", "tolerance", "precision", "recall",
                "gate_precision", "gate_recall", "n_positive", "n_negative",
                "n_detected", "negative_pass_rate"):
        assert key in data, f"contradiction baseline missing {key}"
    assert data["task"] == "contradiction-detection"
    assert data["split"] == "gate"


def test_contradiction_baseline_reproducible(tmp_path):
    """Re-derive the committed baseline; numbers must match exactly."""
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    root = _wiki(tmp_path)
    recomputed = compute_contradiction_baseline(root, GOLDSET)
    for key in ("precision", "recall", "gate_precision", "gate_recall",
                "negative_pass_rate", "n_positive", "n_negative", "n_detected"):
        got = recomputed[key]
        committed = baseline[key]
        assert abs(got - committed) <= _TOL or got == committed, (
            f"{key} drifted: {got} != {committed}"
        )


def test_contradiction_baseline_meets_committed(tmp_path):
    """Fail-on-drop: precision/recall/gate metrics >= the committed baseline."""
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    root = _wiki(tmp_path)
    result = compute_contradiction_baseline(root, GOLDSET)
    for key in ("precision", "recall", "gate_precision", "gate_recall",
                "negative_pass_rate"):
        assert result[key] >= baseline[key] - _TOL, (
            f"{key} dropped below committed baseline: "
            f"{result[key]} < {baseline[key]}"
        )


def test_negative_pass_rate_clean(tmp_path):
    """No gold negative is ever flagged (near-miss families stay clean)."""
    root = _wiki(tmp_path)
    data = load_contradiction_goldset(GOLDSET)
    result = run_contradiction_baseline(root, data["items"])
    assert result["negative_pass_rate"] == 1.0
    assert result["false_positives"] == 0


def test_every_detection_is_labeled(tmp_path):
    """The gold wiki produces no unlabeled detections (precision well-defined)."""
    from llm_wiki.eval.contradiction_baseline import _detected_pair_matches
    from llm_wiki.quality.contradictions import _analyze
    root = _wiki(tmp_path)
    _l, _p, _c, detections = _analyze(str(root))
    data = load_contradiction_goldset(GOLDSET)
    positives = [i for i in data["items"] if i["expected"]]
    assert detections, "gold wiki must produce detections"
    assert all(any(_detected_pair_matches(d, p) for p in positives)
               for d in detections), \
        "every detection must match a labeled gold positive (precision well-defined)"
