"""Eval-regression gate (LWM_023 / ADR-0022).

Future changes must not drop link-suggestion quality below the committed
baseline on the held-out GATE split. This is the enforceable "no keyword-recall
regression" guarantee that must pass before hybrid search is promoted to the
default in v0.5.0 (ADR-0020). Runs deterministically in CI.
"""

import json
from pathlib import Path

import pytest

from llm_wiki.eval.baseline import run_link_suggest_baseline
from llm_wiki.eval.goldset import load_goldset

_BASELINE = Path("tests/eval/baseline/eval_baseline.json")
_GOLDSET = Path("tests/eval/fixtures/goldset_seed.json")
_FIXTURE = Path("tests/fixtures/wikis/populated")
_TOL = 1e-6


def test_lexical_baseline_does_not_regress():
    if not _FIXTURE.is_dir():
        pytest.skip("populated fixture not present")
    baseline = json.loads(_BASELINE.read_text())
    goldset = load_goldset(_GOLDSET)
    rep = run_link_suggest_baseline(_FIXTURE, goldset, k=baseline["k"], split="gate")

    assert rep.precision_at_k >= baseline["precision_at_k"] - _TOL, (
        f"precision@{baseline['k']} regressed: "
        f"{rep.precision_at_k} < {baseline['precision_at_k']}"
    )
    assert rep.recall_at_k >= baseline["recall_at_k"] - _TOL, (
        f"recall regressed: {rep.recall_at_k} < {baseline['recall_at_k']}"
    )
    # Gibberish/negative handling must never regress: negatives stay empty.
    assert rep.negative_pass_rate >= baseline["negative_pass_rate"] - _TOL, (
        f"negative_pass_rate regressed: "
        f"{rep.negative_pass_rate} < {baseline['negative_pass_rate']}"
    )


def test_baseline_artifact_is_committed_and_wellformed():
    data = json.loads(_BASELINE.read_text())
    for key in ("precision_at_k", "recall_at_k", "f1", "k", "split"):
        assert key in data, f"baseline missing {key}"
    assert data["split"] == "gate"  # gate the release on the held-out split
    assert 0.0 <= data["precision_at_k"] <= 1.0
