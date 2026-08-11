"""LWM_034 confidence eval gate — gold labels + baseline + fail-on-drop.

Re-derives the committed ``tests/eval/baseline/confidence_baseline.json`` from
the frozen confidence gold set + the deterministic gold wiki. Scorer accuracy
on the held-out GATE split must match the committed artifact exactly
(reproducibility) and must not regress it (fail-on-drop, ADR-0022). Also
asserts the hard AC#4 property: pages without `sources`/`updated` evidence
score `low` — never `high`.
"""

import json
from pathlib import Path

from llm_wiki.eval.contradiction_baseline import (
    build_contradiction_gold_wiki,
    compute_confidence_baseline,
    load_confidence_goldset,
    run_confidence_baseline,
    split_items,
)

REPO_ROOT = Path(__file__).resolve().parent
GOLDSET = REPO_ROOT / "eval" / "gold" / "confidence_goldset.json"
BASELINE = REPO_ROOT / "eval" / "baseline" / "confidence_baseline.json"
_TOL = 1e-6


def _wiki(tmp_path):
    return build_contradiction_gold_wiki(tmp_path)


# ── gold-set integrity ─────────────────────────────────────────────────────

def test_confidence_goldset_committed_and_wellformed():
    data = json.loads(GOLDSET.read_text(encoding="utf-8"))
    assert data["task"] == "confidence-scoring"
    assert data.get("items"), "confidence gold set must have items"
    for item in data["items"]:
        assert "page" in item and "gold" in item and "split" in item
        assert item["gold"] in ("high", "medium", "low")
        assert item["split"] in ("tune", "gate")


def test_confidence_goldset_tune_gate_disjoint():
    data = load_confidence_goldset(GOLDSET)  # raises ValueError on overlap
    tune = {i["page"] for i in data["items"] if i["split"] == "tune"}
    gate = {i["page"] for i in data["items"] if i["split"] == "gate"}
    assert tune and gate
    assert tune.isdisjoint(gate)


def test_confidence_goldset_labels_grounded_in_gold_wiki():
    """Every gold page resolves to a page in the deterministic gold wiki."""
    from llm_wiki.eval.contradiction_baseline import _CONTRA_GOLD_PAGES
    data = load_confidence_goldset(GOLDSET)
    for item in data["items"]:
        assert f"{item['page']}.md" in _CONTRA_GOLD_PAGES, \
            f"unlabelable gold page: {item['page']}"


# ── baseline reproducibility + fail-on-drop ────────────────────────────────

def test_confidence_baseline_artifact_committed_and_wellformed():
    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    for key in ("task", "split", "tolerance", "accuracy", "n", "per_page"):
        assert key in data, f"confidence baseline missing {key}"
    assert data["task"] == "confidence-scoring"
    assert data["split"] == "gate"
    assert 0.0 <= data["accuracy"] <= 1.0


def test_confidence_baseline_reproducible(tmp_path):
    """Re-derive the committed baseline; accuracy must match exactly."""
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    root = _wiki(tmp_path)
    recomputed = compute_confidence_baseline(root, GOLDSET)
    assert abs(recomputed["accuracy"] - baseline["accuracy"]) <= _TOL, (
        f"confidence accuracy drifted: {recomputed['accuracy']} != {baseline['accuracy']}"
    )
    assert recomputed["n"] == baseline["n"]


def test_confidence_baseline_meets_committed(tmp_path):
    """Fail-on-drop: scorer accuracy >= the committed baseline."""
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    root = _wiki(tmp_path)
    gate_items = split_items(load_confidence_goldset(GOLDSET), "gate")
    result = run_confidence_baseline(root, gate_items)
    assert result["accuracy"] >= baseline["accuracy"] - _TOL, (
        f"confidence accuracy dropped below committed baseline: "
        f"{result['accuracy']} < {baseline['accuracy']}"
    )


def test_no_evidence_scores_low_never_high(tmp_path):
    """AC#4 hard property: missing sources/updated -> low, never high."""
    from llm_wiki.quality.contradictions import score_confidence
    root = _wiki(tmp_path)
    scores = score_confidence(str(root))
    res = scores["no-evidence"]
    assert res["label"] == "low"
    assert res["evidence_score"] < 0.4, "no-evidence pages must stay below medium"

    # and the gold gate pages all land on their committed labels
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    for page, info in baseline["per_page"].items():
        assert scores[page]["label"] == info["predicted"], (
            f"gate page {page} label drifted"
        )


def test_confidence_gold_labels_fully_correct(tmp_path):
    """The gate split is 100% accurate (the committed artifact says so)."""
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    root = _wiki(tmp_path)
    gate_items = split_items(load_confidence_goldset(GOLDSET), "gate")
    result = run_confidence_baseline(root, gate_items)
    assert result["accuracy"] == 1.0
    assert baseline["accuracy"] == 1.0
    assert all(info["ok"] for info in result["per_page"].values())
