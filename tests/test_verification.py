"""
test_verification.py — Pytest entry point for the community detection
verification suite.

Usage:
    pytest tests/test_verification.py -v
"""

from tests.verification.run_verification import run_verification


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
