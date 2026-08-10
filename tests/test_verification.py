"""
test_verification.py — Pytest entry point for the community detection
verification suite.

Usage:
    pytest tests/test_verification.py -v

Skips (rather than fails) when the TS toolchain is absent — the
cross-implementation suite needs the workspace node deps (tsx, graphology),
which only the verify-communities workflow and the leiden-verification CI job
install. See run_verification.ts_louvain_available().
"""

import pytest

from tests.verification.run_verification import SEEDS, run_verification, ts_louvain_available

pytestmark = pytest.mark.skipif(
    not ts_louvain_available(),
    reason="TS Louvain toolchain not installed (tsx/graphology) — covered by "
    "verify-communities workflow + leiden-verification CI job",
)


def test_community_verification():
    """Run full multi-graph, multi-seed verification suite.

    This single test wraps the comprehensive verification harness that:
    - Runs TS and Python Louvain on 7 graph fixtures with 5 seeds each
    - Computes NMI (cross-impl, within-impl)
    - Computes ARI (cross-impl, within-impl)
    - Checks modularity Q consistency
    - Reports pass/fail per graph

    If this test fails, inspect the output for specific graph failures.
    """
    results = run_verification()

    # Fail if any graph had verification failures
    failed = [r for r in results if not r["all_pass"]]
    assert len(failed) == 0, (
        f"{len(failed)} graph(s) failed verification:\n"
        + "\n".join(
            f"  - {r['graph']}: {'; '.join(r['failures'])}" for r in failed
        )
    )

    # ADR-0012 gate data (AD-5): every graph report carries the
    # Leiden-vs-Louvain NMI/modularity section.
    assert results, "no graph results reported"
    for r in results:
        assert "leiden_vs_louvain" in r, (
            f"{r['graph']}: missing leiden_vs_louvain report section"
        )
        lvl = r["leiden_vs_louvain"]
        assert lvl["graph"] == r["graph"]
        assert len(lvl["seeds"]) == len(SEEDS)
        if lvl["available"]:
            # Metrics computed (not necessarily a Leiden win — the flip is a
            # separate gated decision, ADR-0025).
            assert len(lvl["nmi_values"]) == len(SEEDS)
            assert len(lvl["modularity_leiden"]) == len(SEEDS)
            assert lvl["connectivity_pass"] is True
