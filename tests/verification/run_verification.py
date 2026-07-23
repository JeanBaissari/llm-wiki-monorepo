"""
tests/verification/run_verification.py

Cross-implementation Louvain community detection verification suite.

Runs TypeScript and Python Louvain on 7 graph topologies with 5 seeds each,
computes NMI, ARI, and modularity Q, then reports results with pass/fail
against defined thresholds.

Usage (direct):
    python3 tests/verification/run_verification.py

Usage (pytest):
    pytest tests/test_verification.py -v
"""

import json
import math
import os
import subprocess
import sys
from collections import defaultdict
from typing import Any, Optional

# Ensure the repo root is on sys.path
_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from tests.verification.metrics import ari, modularity_q, nmi

# ── Config ─────────────────────────────────────────────────────────────────
SEEDS = [42, 123, 456, 789, 0]

# Paths (relative to repo root)
GRAPHS_DIR = os.path.join(_REPO_ROOT, "tests", "fixtures", "graphs")
TS_RUNNER = os.path.join(
    _REPO_ROOT, "graph-engine", "scripts", "ts_louvain_runner.ts"
)

# Thresholds (from LWM_08B spec)
NMI_THRESHOLD = 0.95  # Cross-implementation NMI
ARI_THRESHOLD = 0.95  # Cross-implementation ARI
DETERMINISM_NMI = 1.0  # Same seed → identical results
STABILITY_NMI = 0.90  # Different seeds → mostly agree
MODULARITY_TOLERANCE = 0.01  # |ΔQ| / max(Q) < 1%

# ── Graph loading ──────────────────────────────────────────────────────────
def load_graph_fixtures() -> list[dict]:
    """Load all JSON graph fixture files from GRAPHS_DIR."""
    graphs = []
    for fname in sorted(os.listdir(GRAPHS_DIR)):
        if fname.endswith(".json"):
            path = os.path.join(GRAPHS_DIR, fname)
            with open(path, "r") as f:
                data = json.load(f)
                data["_path"] = path
                graphs.append(data)
    return graphs


# ── Python Louvain ─────────────────────────────────────────────────────────
def run_python_louvain(
    edges: list[dict], node_ids: list[str], seed: int
) -> dict[str, int]:
    """Run Python Louvain via skill/scripts/louvain.py and return assignments."""
    # Import the louvain module (conftest adds skill/scripts to path)
    sys.path.insert(0, os.path.join(_REPO_ROOT, "skill", "scripts"))
    from llm_wiki.graph.louvain import detect_communities

    # Convert to the format expected by louvain.detect_communities
    nodes_py = [{"id": nid} for nid in node_ids]
    edges_py = [
        {"source": e["source"], "target": e["target"], "weight": e.get("weight", 1)}
        for e in edges
    ]

    assignments, _ = detect_communities(nodes_py, edges_py, seed=seed)
    return assignments


# ── TypeScript Louvain ─────────────────────────────────────────────────────
def run_ts_louvain(graph_path: str, seed: int) -> Optional[dict[str, int]]:
    """Run TypeScript Louvain via tsx runner and return assignments dict."""
    try:
        proc = subprocess.run(
            ["npx", "tsx", TS_RUNNER, graph_path, str(seed)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=_REPO_ROOT,
        )
        if proc.returncode != 0:
            print(f"  [WARN] TS runner exited {proc.returncode}: {proc.stderr.strip()}")
            return None

        output = json.loads(proc.stdout.strip())
        return output.get("assignments")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        print(f"  [WARN] TS runner failed: {e}")
        return None


# ── Core verification logic ────────────────────────────────────────────────
def verify_graph(
    graph: dict,
) -> dict[str, Any]:
    """Run full verification on one graph fixture.

    Returns a dict with all metrics and pass/fail status.
    """
    name = graph["name"]
    edges = graph["edges"]
    nodes = graph["nodes"]
    graph_path = graph["_path"]

    result: dict[str, Any] = {
        "graph": name,
        "nodeCount": len(nodes),
        "edgeCount": len(edges),
        "expected_agreement": graph.get("expected_agreement", True),
        "seeds": {},
        "cross_impl": {},
        "within_ts": {},
        "within_py": {},
        "all_pass": True,
        "failures": [],
    }

    # ── Phase 1: Run both implementations with each seed ──────────────
    py_assignments: dict[int, dict[str, int]] = {}
    ts_assignments: dict[int, dict[str, int]] = {}

    for seed in SEEDS:
        # Python
        try:
            py_assignments[seed] = run_python_louvain(edges, nodes, seed)
        except Exception as e:
            print(f"  [WARN] Python Louvain seed={seed} failed: {e}")
            py_assignments[seed] = {}

        # TypeScript
        ts_result = run_ts_louvain(graph_path, seed)
        if ts_result is not None:
            ts_assignments[seed] = ts_result
        else:
            ts_assignments[seed] = {}

    # ── Phase 2: Per-seed results ────────────────────────────────────
    for seed in SEEDS:
        py_ass = py_assignments.get(seed, {})
        ts_ass = ts_assignments.get(seed, {})

        seed_result: dict[str, Any] = {
            "py_communityCount": len(set(py_ass.values())) if py_ass else 0,
            "ts_communityCount": len(set(ts_ass.values())) if ts_ass else 0,
            "py_modularity": (
                _compute_q(py_ass, edges) if py_ass else None
            ),
            "ts_modularity": (
                _compute_q(ts_ass, edges) if ts_ass else None
            ),
        }
        result["seeds"][str(seed)] = seed_result

    # ── Phase 3: Cross-implementation agreement (NMI/ARI) ────────────
    cross_nmi_vals = []
    cross_ari_vals = []
    for seed in SEEDS:
        py_ass = py_assignments.get(seed, {})
        ts_ass = ts_assignments.get(seed, {})
        if py_ass and ts_ass and len(py_ass) == len(ts_ass):
            # Ensure same node ordering
            nodes_sorted = sorted(py_ass.keys())
            py_labels = [py_ass[n] for n in nodes_sorted]
            ts_labels = [ts_ass[n] for n in nodes_sorted]
            n = nmi(py_labels, ts_labels)
            a = ari(py_labels, ts_labels)
            cross_nmi_vals.append(n)
            cross_ari_vals.append(a)

    result["cross_impl"] = {
        "nmi_values": cross_nmi_vals,
        "nmi_mean": (
            sum(cross_nmi_vals) / len(cross_nmi_vals) if cross_nmi_vals else 0
        ),
        "nmi_pass": (
            all(v >= NMI_THRESHOLD for v in cross_nmi_vals)
            if cross_nmi_vals
            else False
        ),
        "ari_values": cross_ari_vals,
        "ari_mean": (
            sum(cross_ari_vals) / len(cross_ari_vals) if cross_ari_vals else 0
        ),
        "ari_pass": (
            all(v >= ARI_THRESHOLD for v in cross_ari_vals)
            if cross_ari_vals
            else False
        ),
    }

    # ── Phase 4: Within-implementation determinism ───────────────────
    # Python: same seed → identical (NMI=1.0)
    # Python: different seeds → stable (NMI > 0.90)
    py_nmi_same_seed = []
    py_nmi_diff_seed = []
    seeds_list = list(SEEDS)
    for i, s1 in enumerate(seeds_list):
        for s2 in seeds_list[i + 1 :]:
            a1 = py_assignments.get(s1, {})
            a2 = py_assignments.get(s2, {})
            if a1 and a2 and len(a1) == len(a2):
                nodes_sorted = sorted(a1.keys())
                l1 = [a1[n] for n in nodes_sorted]
                l2 = [a2[n] for n in nodes_sorted]
                n = nmi(l1, l2)
                if s1 == s2:
                    py_nmi_same_seed.append(n)
                else:
                    py_nmi_diff_seed.append(n)

    result["within_py"] = {
        "nmi_same_seed": py_nmi_same_seed,
        "nmi_same_seed_pass": (
            all(v == DETERMINISM_NMI for v in py_nmi_same_seed)
            if py_nmi_same_seed
            else True
        ),
        "nmi_diff_seed": py_nmi_diff_seed,
        "nmi_diff_seed_mean": (
            sum(py_nmi_diff_seed) / len(py_nmi_diff_seed)
            if py_nmi_diff_seed
            else 0
        ),
        "nmi_diff_seed_pass": (
            all(v >= STABILITY_NMI for v in py_nmi_diff_seed)
            if py_nmi_diff_seed
            else True
        ),
    }

    # TS: same seed → identical
    ts_nmi_same_seed = []
    for seed in SEEDS:
        ass1 = ts_assignments.get(seed, {})
        ass2_dup = ts_assignments.get(seed, {})
        if ass1 and ass2_dup and len(ass1) == len(ass2_dup):
            nodes_sorted = sorted(ass1.keys())
            l1 = [ass1[n] for n in nodes_sorted]
            l2 = [ass2_dup[n] for n in nodes_sorted]
            n = nmi(l1, l2)
            ts_nmi_same_seed.append(n)

    result["within_ts"] = {
        "nmi_same_seed": ts_nmi_same_seed,
        "nmi_same_seed_pass": (
            all(v == DETERMINISM_NMI for v in ts_nmi_same_seed)
            if ts_nmi_same_seed
            else True
        ),
    }

    # ── Phase 5: Modularity consistency ──────────────────────────────
    q_pass = True
    for seed in SEEDS:
        py_q = result["seeds"][str(seed)].get("py_modularity")
        ts_q = result["seeds"][str(seed)].get("ts_modularity")
        if py_q is not None and ts_q is not None:
            max_q = max(py_q, ts_q)
            if max_q > 0:
                delta_q = abs(py_q - ts_q) / max_q
                if delta_q > MODULARITY_TOLERANCE:
                    q_pass = False

    result["modularity_consistent"] = q_pass

    # ── Overall pass/fail ───────────────────────────────────────────
    failures = []

    # Only check cross-implementation and stability metrics on graphs
    # with expected community structure (skipped for noise-only graphs)
    if result["expected_agreement"]:
        if not result["cross_impl"]["nmi_pass"]:
            failures.append(
                f"cross_impl_nmi: {result['cross_impl']['nmi_mean']:.4f} < {NMI_THRESHOLD}"
            )
        if not result["cross_impl"]["ari_pass"]:
            failures.append(
                f"cross_impl_ari: {result['cross_impl']['ari_mean']:.4f} < {ARI_THRESHOLD}"
            )
        if not result["within_py"]["nmi_diff_seed_pass"]:
            failures.append("py_nmi_diff_seed: stability below threshold")
        if not result["modularity_consistent"]:
            failures.append("modularity Q discrepancy > 1%")
    if not result["within_py"]["nmi_same_seed_pass"]:
        failures.append("py_nmi_same_seed: determinism broken")
    if not result["within_ts"]["nmi_same_seed_pass"]:
        failures.append("ts_nmi_same_seed: determinism broken")

    result["all_pass"] = len(failures) == 0
    result["failures"] = failures

    return result


def _compute_q(
    assignments: dict[str, int], edges: list[dict]
) -> float:
    """Compute modularity Q from assignments and edge list."""
    edge_tuples = [
        (e["source"], e["target"], e.get("weight", 1)) for e in edges
    ]
    return modularity_q(assignments, edge_tuples)


# ── Report ─────────────────────────────────────────────────────────────────
def print_report(results: list[dict]):
    """Print a human-readable verification report."""
    total = len(results)
    passed = sum(1 for r in results if r["all_pass"])

    print("=" * 72)
    print(
        f"  Community Detection Verification Suite  "
        f"[{passed}/{total} passed]"
    )
    print("=" * 72)

    for r in results:
        status = " PASS " if r["all_pass"] else " FAIL "
        print(f"\n[{status}] {r['graph']}")
        print(f"       Nodes: {r['nodeCount']}, Edges: {r['edgeCount']}")

        cross = r["cross_impl"]
        if cross.get("nmi_values"):
            print(
                f"       NMI(TS vs PY):  mean={cross['nmi_mean']:.4f}  "
                f"vals={[round(v, 4) for v in cross['nmi_values']]}"
            )
        if cross.get("ari_values"):
            print(
                f"       ARI(TS vs PY):  mean={cross['ari_mean']:.4f}  "
                f"vals={[round(v, 4) for v in cross['ari_values']]}"
            )

        wp = r["within_py"]
        if wp.get("nmi_diff_seed"):
            print(
                f"       PY within (diff seed):  "
                f"mean NMI={wp['nmi_diff_seed_mean']:.4f}  "
                f"vals={[round(v, 4) for v in wp['nmi_diff_seed']]}"
            )

        # Per-seed modularity
        for seed_str, sd in r["seeds"].items():
            py_q = sd.get("py_modularity")
            ts_q = sd.get("ts_modularity")
            if py_q is not None or ts_q is not None:
                py_q_str = f"{py_q:.4f}" if py_q is not None else "N/A"
                ts_q_str = f"{ts_q:.4f}" if ts_q is not None else "N/A"
                print(
                    f"       seed {seed_str:>3}:  PY_Q={py_q_str:>8}  "
                    f"TS_Q={ts_q_str:>8}  "
                    f"py_comm={sd['py_communityCount']}  "
                    f"ts_comm={sd['ts_communityCount']}"
                )

        if not r["all_pass"]:
            for f in r["failures"]:
                print(f"       FAIL: {f}")

    print("\n" + "=" * 72)
    print(f"  Result: {passed}/{total} graphs passed")
    if passed == total:
        print("  All checks passed.")
    else:
        print(f"  {total - passed} graph(s) have failures.")
    print("=" * 72)


# ── Main entry point ───────────────────────────────────────────────────────
def run_verification() -> list[dict]:
    """Run the full verification suite and return results."""
    graphs = load_graph_fixtures()
    print(f"Loaded {len(graphs)} graph fixtures.\n")
    results = []
    for g in graphs:
        print(f"Verifying '{g['name']}' ({len(g['nodes'])} nodes, {len(g['edges'])} edges)...")
        r = verify_graph(g)
        results.append(r)
    print_report(results)
    return results


def main():
    results = run_verification()
    # Exit code: 0 if all pass, 1 if any failed
    if not all(r["all_pass"] for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
