"""Eval-regression gate (LWM_023 / ADR-0022).

Future changes must not drop link-suggestion quality below the committed
baseline on the held-out GATE split. This is the enforceable "no keyword-recall
regression" guarantee that must pass before hybrid search is promoted to the
default in v0.5.0 (ADR-0020). Runs deterministically in CI.

Also gates the derived-edge NMI+modularity gate metric (LWM_029 AC#6) and the
community-summary faithfulness metric (LWM_030 AC#7): a change that would make
the derived layer degrade communities or summaries fails here.
"""

import json
from pathlib import Path

import pytest

from llm_wiki.eval.baseline import run_link_suggest_baseline
from llm_wiki.eval.goldset import load_goldset
from tests.eval.test_derived_edge_nmi_gate import (
    compute_derived_gate_metrics,
    compute_faithfulness_metric,
)

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


def test_derived_edge_gate_committed():
    """LWM_029 AC#6: the NMI-vs-baseline gate metric is committed and enforced.

    Recompute the gate on the deterministic synthetic wiki and fail if any half
    of the committed gate (NMI or modularity) would drop. Mirrors
    test_lexical_baseline_does_not_regress: committed values are the floor.
    """
    data = json.loads(_BASELINE.read_text())
    committed = data["derived_edge_gate"]
    for key in ("nmi_with_vs_baseline", "baseline_modularity",
                "with_derived_modularity", "tol", "included"):
        assert key in committed, f"derived_edge_gate baseline missing {key}"

    recomputed = compute_derived_gate_metrics()
    tol = committed["tol"]
    assert recomputed["nmi_with_vs_baseline"] >= committed["nmi_with_vs_baseline"] - tol, (
        f"NMI-with-vs-baseline regressed: {recomputed['nmi_with_vs_baseline']} "
        f"< {committed['nmi_with_vs_baseline']}"
    )
    assert recomputed["with_derived_modularity"] >= committed["with_derived_modularity"] - tol, (
        f"with-derived modularity regressed: {recomputed['with_derived_modularity']} "
        f"< {committed['with_derived_modularity']}"
    )
    assert recomputed["baseline_modularity"] >= committed["baseline_modularity"] - tol, (
        f"baseline modularity regressed: {recomputed['baseline_modularity']} "
        f"< {committed['baseline_modularity']}"
    )
    # The gate must still ALLOW a structure-preserving layer (and the committed
    # value itself must be the allow outcome — a silently-refusing gate would
    # have no teeth as a committed metric).
    assert recomputed["included"] is True
    assert committed["included"] is True


def test_summary_faithfulness_gate_committed():
    """LWM_030 AC#7: community-summary faithfulness is committed and enforced.

    Recompute the faithfulness rate over the deterministic fake summary set;
    a drop below the committed rate fails the release.
    """
    data = json.loads(_BASELINE.read_text())
    committed = data["community_summary_faithfulness"]
    for key in ("faithfulness", "n_summaries"):
        assert key in committed, f"community_summary_faithfulness baseline missing {key}"

    recomputed = compute_faithfulness_metric()
    assert recomputed["n_summaries"] == committed["n_summaries"]
    assert recomputed["faithfulness"] >= committed["faithfulness"] - _TOL, (
        f"summary faithfulness regressed: {recomputed['faithfulness']} "
        f"< {committed['faithfulness']}"
    )
