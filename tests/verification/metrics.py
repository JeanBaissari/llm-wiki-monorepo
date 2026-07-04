"""
tests/verification/metrics.py

Community detection verification metrics:
  - NMI (Normalized Mutual Information) — sklearn variant
  - ARI (Adjusted Rand Index)
  - Modularity Q

When sklearn is available, uses sklearn.metrics for NMI/ARI.
Falls back to pure-Python implementations if sklearn is not installed.
"""

import math
from collections import Counter, defaultdict
from typing import Optional

# Try to import sklearn for NMI/ARI; fall back to pure-Python implementations
try:
    from sklearn.metrics.cluster import (
        normalized_mutual_info_score as sklearn_nmi,
        adjusted_rand_score as sklearn_ari,
    )

    HAVE_SKLEARN = True
except ImportError:
    HAVE_SKLEARN = False


# ---------------------------------------------------------------------------
# Pure-Python NMI (Normalized Mutual Information)
# ---------------------------------------------------------------------------
def _entropy(counts: list, total: float) -> float:
    """Compute entropy H(X) = -sum(p_i * log(p_i))."""
    if total <= 0:
        return 0.0
    h = 0.0
    for c in counts:
        if c > 0:
            p = c / total
            h -= p * math.log(p)
    return h


def _mutual_info(
    labels_true: list[int], labels_pred: list[int], total: int
) -> float:
    """Compute mutual information I(X;Y)."""
    # Contingency matrix
    contingency: dict[tuple[int, int], int] = defaultdict(int)
    for t, p in zip(labels_true, labels_pred):
        contingency[(t, p)] += 1

    # Marginals
    row_sums: dict[int, int] = defaultdict(int)
    col_sums: dict[int, int] = defaultdict(int)
    for (t, p), count in contingency.items():
        row_sums[t] += count
        col_sums[p] += count

    mi = 0.0
    for (t, p), n_ij in contingency.items():
        if n_ij > 0:
            n_i = row_sums[t]
            n_j = col_sums[p]
            mi += n_ij / total * math.log(n_ij * total / (n_i * n_j))
    return mi


def pure_nmi(
    labels_true: list[int],
    labels_pred: list[int],
    average_method: str = "sqrt",
) -> float:
    """Pure-Python Normalized Mutual Information.

    Supports average_method: 'sqrt', 'max', 'min', 'arithmetic'.
    """
    total = len(labels_true)
    if total == 0:
        return 1.0

    # Short-circuit for identical labelings (avoids floating-point noise)
    if labels_true == labels_pred:
        return 1.0

    # Single cluster check
    if len(set(labels_true)) <= 1 or len(set(labels_pred)) <= 1:
        return 1.0

    mi = _mutual_info(labels_true, labels_pred, total)

    # Count per cluster
    true_counts_list: list = list(Counter(labels_true).values())
    pred_counts_list: list = list(Counter(labels_pred).values())

    h_true = _entropy(true_counts_list, total)
    h_pred = _entropy(pred_counts_list, total)

    if h_true == 0.0 and h_pred == 0.0:
        return 1.0
    if h_true == 0.0 or h_pred == 0.0:
        return 0.0

    if average_method == "sqrt":
        denom = math.sqrt(h_true * h_pred)
    elif average_method == "max":
        denom = max(h_true, h_pred)
    elif average_method == "min":
        denom = min(h_true, h_pred)
    elif average_method == "arithmetic":
        denom = (h_true + h_pred) / 2.0
    else:
        raise ValueError(f"Unknown average_method: {average_method}")

    if denom == 0:
        return 1.0
    return mi / denom


# ---------------------------------------------------------------------------
# Pure-Python ARI (Adjusted Rand Index)
# ---------------------------------------------------------------------------
def _comb2(n: int) -> int:
    """Compute n choose 2."""
    return n * (n - 1) // 2


def pure_ari(labels_true: list[int], labels_pred: list[int]) -> float:
    """Pure-Python Adjusted Rand Index."""
    total = len(labels_true)
    if total == 0:
        return 1.0

    # Short-circuit for identical labelings (avoids floating-point noise)
    if labels_true == labels_pred:
        return 1.0

    # Build contingency matrix
    classes = set(labels_true)
    clusters = set(labels_pred)

    # If either is trivial
    if len(classes) <= 1 or len(clusters) <= 1:
        return 1.0

    contingency: dict[tuple[int, int], int] = defaultdict(int)
    for t, p in zip(labels_true, labels_pred):
        contingency[(t, p)] += 1

    # Row sums (class sizes)
    row_sums: dict[int, int] = defaultdict(int)
    col_sums: dict[int, int] = defaultdict(int)
    for (t, p), count in contingency.items():
        row_sums[t] += count
        col_sums[p] += count

    # Sum of contingency pairs
    sum_c = sum(_comb2(n) for n in contingency.values())

    # Sum of row pairs
    sum_a = sum(_comb2(n) for n in row_sums.values())

    # Sum of column pairs
    sum_b = sum(_comb2(n) for n in col_sums.values())

    # Total pairs
    total_pairs = _comb2(total)

    # Expected index
    expected = sum_a * sum_b / total_pairs if total_pairs > 0 else 0

    # Max index
    max_index = (sum_a + sum_b) / 2

    # ARI
    if max_index == expected:
        return 1.0

    return (sum_c - expected) / (max_index - expected)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def nmi(
    labels_true: list[int],
    labels_pred: list[int],
    average_method: str = "sqrt",
) -> float:
    """Normalized Mutual Information.

    Uses sklearn if available; otherwise pure-Python fallback."""
    if HAVE_SKLEARN:
        return sklearn_nmi(labels_true, labels_pred, average_method=average_method)
    return pure_nmi(labels_true, labels_pred, average_method)


def ari(labels_true: list[int], labels_pred: list[int]) -> float:
    """Adjusted Rand Index.

    Uses sklearn if available; otherwise pure-Python fallback."""
    if HAVE_SKLEARN:
        return sklearn_ari(labels_true, labels_pred)
    return pure_ari(labels_true, labels_pred)


def modularity_q(
    assignments: dict[str, int],
    edges: list[tuple[str, str, float]],
) -> float:
    """Compute Newman modularity Q from assignments and edge list.

    Q = (1/2m) * sum_ij [ A_ij - (k_i * k_j) / 2m ] * delta(c_i, c_j)

    Where:
      A_ij = adjacency (1 if edge exists, 0 otherwise)
      k_i = degree of node i
      m = total edge weight
      delta(c_i, c_j) = 1 if same community, 0 otherwise
    """
    # Count degrees and total weight
    degree: dict[str, float] = defaultdict(float)
    total_weight = 0.0
    for u, v, w in edges:
        degree[u] += w
        degree[v] += w
        total_weight += w

    # Group nodes by community
    communities: dict[int, list[str]] = defaultdict(list)
    for node, comm in assignments.items():
        communities[comm].append(node)

    if total_weight <= 0:
        return 0.0

    # Compute Q
    q = 0.0
    for comm, members in communities.items():
        for i in members:
            for j in members:
                if i == j:
                    continue
                # A_ij: check if edge exists
                a_ij = 0.0
                for u, v, w in edges:
                    if (u == i and v == j) or (u == j and v == i):
                        a_ij = w
                        break
                q += a_ij - (degree[i] * degree[j]) / (2 * total_weight)

    q /= 2 * total_weight
    return q
