"""Community-engine parity gate tests (BKD-003 / ADR-0025).

The default-flip actuator: Leiden becomes default only when the parity gate
proves (a) Leiden modularity >= Louvain and (b) the partitions essentially
agree (mean NMI >= margin) on the structured fixture graphs. The flip itself
is a separate evidence-linked change — these tests only measure and fail
closed, never flip.
"""

import json
from pathlib import Path

import pytest

from llm_wiki.eval.community_parity import compute_parity

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "graphs"
BASELINE = REPO_ROOT / "tests" / "eval" / "baseline" / "community_engine_parity.json"

pytestmark = pytest.mark.skipif(
    not __import__("llm_wiki.graph.leiden", fromlist=["is_leiden_available"]).is_leiden_available(),
    reason="[leiden] extra not installed — parity gate runs in the leiden-verification CI lane",
)


def test_flip_gate_verdict():
    """The parity gate certifies (or fails closed) the flip decision."""
    report = compute_parity(FIXTURES)
    assert report["status"] == "measured"
    g = report["gate"]
    assert g["modularity_non_degradation"]["pass"] is True, (
        "Leiden modularity regressed vs Louvain on the gate set — do NOT flip"
    )
    assert g["nmi_agreement_structured"]["pass"] is True, (
        "Leiden/Louvain partitions disagree on structured graphs — do NOT flip"
    )
    assert report["flip_allowed"] is True
    # The gate never flips on its own: the report documents the verdict and
    # the default engine stays Louvain until a separate reviewed change.
    assert g["nmi_agreement_structured"]["n_graphs"] >= 3


def test_committed_baseline_fail_on_drop():
    """Re-measured parity must not regress the committed margin baseline."""
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert baseline["status"] == "measured"
    report = compute_parity(FIXTURES)
    b = baseline["gate"]
    r = report["gate"]
    tol = 1e-6
    assert r["modularity_non_degradation"]["leiden"] >= (
        b["modularity_non_degradation"]["leiden"] - tol
    ), "Leiden modularity dropped below the committed baseline"
    assert r["nmi_agreement_structured"]["mean_nmi"] >= (
        b["nmi_agreement_structured"]["mean_nmi"] - tol
    ), "Leiden/Louvain agreement dropped below the committed baseline"
    assert report["flip_allowed"] == baseline["flip_allowed"], (
        "flip verdict changed vs the committed baseline — re-review under ADR-0025"
    )


def test_report_artifact_shape(tmp_path):
    """The report carries per-graph rows + the documented gate fields."""
    report = compute_parity(FIXTURES)
    assert "per_graph" in report and report["per_graph"]
    for row in report["per_graph"]:
        assert "graph" in row
    assert set(report["gate"]) == {"modularity_non_degradation", "nmi_agreement_structured"}
