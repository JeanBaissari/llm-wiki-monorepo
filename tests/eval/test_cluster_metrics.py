"""Cluster-metric semantics — lane independence for the ADR-0012/0017 gates.

``pure_nmi``/``pure_ari`` must agree with sklearn on degenerate partitions
(single-cluster labelings) so gate results do not flip depending on whether
sklearn is installed (the ``python``/``verify-communities`` lanes run without
it). Exactly one single-cluster partition carries no information about a
non-constant one: NMI/ARI = 0.0 (sklearn semantics).
"""

import pytest

from llm_wiki.eval.cluster_metrics import (
    HAVE_SKLEARN,
    ari,
    nmi,
    pure_ari,
    pure_nmi,
)


# ── pure_nmi degenerate semantics (sklearn-compatible) ──────────────────────

def test_pure_nmi_degenerate_single_cluster_is_zero():
    assert pure_nmi([0, 0, 0], [0, 1, 1]) == 0.0
    assert pure_nmi([0, 1, 1], [0, 0, 0]) == 0.0
    assert pure_nmi([0, 0, 0], [0, 1, 1], average_method="max") == 0.0


def test_pure_nmi_degenerate_both_single_cluster_is_one():
    assert pure_nmi([0, 0, 0], [0, 0, 0]) == 1.0
    # Same constant partition, different label value → still identical.
    assert pure_nmi([5, 5, 5], [0, 0, 0]) == 1.0


def test_pure_nmi_empty_and_identical_are_one():
    assert pure_nmi([], []) == 1.0
    a = [0, 0, 1, 1, 2, 2]
    assert pure_nmi(a, list(a)) == 1.0


def test_pure_nmi_general_partition():
    # Label permutation is irrelevant → identical partition → 1.0.
    assert pure_nmi([0, 0, 1, 1, 2, 2], [2, 2, 1, 1, 0, 0]) == pytest.approx(1.0)
    # Disagreeing partitions score below 1.0.
    assert pure_nmi([0, 0, 1, 1], [0, 1, 0, 1]) < 1.0


# ── pure_ari degenerate semantics (sklearn-compatible) ──────────────────────

def test_pure_ari_degenerate_single_cluster_is_zero():
    assert pure_ari([0, 0, 0], [0, 1, 1]) == 0.0
    assert pure_ari([0, 1, 1], [0, 0, 0]) == 0.0


def test_pure_ari_degenerate_both_single_cluster_is_one():
    assert pure_ari([0, 0, 0], [0, 0, 0]) == 1.0
    assert pure_ari([5, 5, 5], [0, 0, 0]) == 1.0


def test_pure_ari_empty_and_general():
    assert pure_ari([], []) == 1.0
    a = [0, 0, 1, 1, 2, 2]
    assert pure_ari(a, list(a)) == 1.0
    assert pure_ari([0, 0, 1, 1], [0, 1, 0, 1]) < 1.0


# ── the gate surface must not depend on sklearn presence ────────────────────

def test_gate_nmi_lane_independent_for_degenerate_partitions():
    assert nmi([0, 0, 0], [0, 1, 1]) == 0.0
    assert ari([0, 0, 0], [0, 1, 1]) == 0.0
    assert nmi([0, 0, 0], [0, 0, 0]) == 1.0


@pytest.mark.skipif(not HAVE_SKLEARN, reason="sklearn not installed")
def test_pure_matches_sklearn_across_partitions():
    cases = [
        ([0, 0, 0], [0, 1, 1]),
        ([0, 0, 0], [0, 0, 0]),
        ([5, 5, 5], [0, 0, 0]),
        ([0, 0, 1, 1], [0, 1, 0, 1]),
        ([0, 0, 1, 1, 2, 2], [2, 2, 1, 1, 0, 0]),
        ([0, 1, 2, 3], [0, 1, 2, 3]),
        ([0, 0, 1, 2, 2], [1, 1, 0, 2, 2]),
    ]
    for labels_true, labels_pred in cases:
        assert pure_nmi(labels_true, labels_pred) == pytest.approx(
            nmi(labels_true, labels_pred), abs=1e-12
        )
        assert pure_ari(labels_true, labels_pred) == pytest.approx(
            ari(labels_true, labels_pred), abs=1e-12
        )
