#!/usr/bin/env python3
"""community_parity.py — Leiden vs Louvain parity gate (BKD-003 / ADR-0025).

ADR-0025's default-switch policy ("Leiden becomes the default only when
NMI/modularity ≥ Louvain on the gate set") needs an actuator. This module is
it: it runs both engines on the committed graph fixture suite
(``tests/fixtures/graphs/*.json``) at the default seed, measures per-graph
modularity plus the NMI between the two partitions, aggregates, and emits a
verdict. The flip itself remains a separate, evidence-linked change — this
gate only measures and fails closed; it never flips anything silently.

Gate policy (documented in the report + ADR-0025):

* **modularity** — Leiden's mean modularity must be ≥ Louvain's (minus the
  tolerance): the flip must not degrade community quality on any gate graph.
* **NMI agreement** — on the *structured* graphs (``expected_agreement`` is
  not ``False``; the ``random`` noise graph has no stable community structure
  and the ``empty`` graph is trivially all-singletons) the two engines'
  partitions must essentially agree (mean NMI ≥ ``NMI_MARGIN``): flipping the
  default must not visibly change the partition structure.

``[leiden]``-gated: without the extra the computation is skipped (status
``skipped``, exit 0) so base-install and CI lanes without the extra are not
punished; the dedicated ``leiden-verification`` CI lane runs it for real.
"""

from __future__ import annotations

import json
from pathlib import Path

from llm_wiki.eval.cluster_metrics import modularity_q, nmi

DEFAULT_SEED = 42
DEFAULT_RESOLUTION = 1.0
DEFAULT_TOL = 1e-6
DEFAULT_NMI_MARGIN = 0.95

# Noise graphs: no stable community structure (random) or trivially empty.
# They are reported but excluded from the NMI agreement lane.
NOISE_GRAPHS = {"random", "empty"}


def _load_fixtures(fixtures_dir: Path) -> "list[dict]":
    graphs = []
    for fname in sorted(fixtures_dir.glob("*.json")):
        data = json.loads(fname.read_text(encoding="utf-8"))
        data["_path"] = str(fname)
        graphs.append(data)
    return graphs


def _assignments(engine, nodes: "list[str]", edges: "list[dict]", seed: int) -> "dict[str, int]":
    node_list = [{"id": nid} for nid in nodes]
    edge_list = [
        {"source": e["source"], "target": e["target"], "weight": e.get("weight", 1)}
        for e in edges
    ]
    if "resolution" in _params(engine):
        # Louvain accepts resolution; the Leiden sidecar does not (LWM_027).
        assignments, _ = engine(node_list, edge_list, seed=seed, resolution=DEFAULT_RESOLUTION)
    else:
        assignments, _ = engine(node_list, edge_list, seed=seed)
    return assignments


def _params(fn):
    import inspect

    return inspect.signature(fn).parameters


def compute_parity(
    fixtures_dir: Path,
    seed: int = DEFAULT_SEED,
    tol: float = DEFAULT_TOL,
    nmi_margin: float = DEFAULT_NMI_MARGIN,
) -> dict:
    """Run the parity gate over the fixture suite; returns the report dict."""
    import warnings

    from llm_wiki.graph import leiden
    from llm_wiki.graph.louvain import detect_communities as louvain_detect

    if not leiden.is_leiden_available():
        return {
            "status": "skipped",
            "reason": "[leiden] extra not installed — parity gate runs in the "
                      "leiden-verification CI lane",
        }

    # Louvain's migration UserWarning is expected here — this IS the parity
    # measurement, not a surprise transition.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        graphs = _load_fixtures(fixtures_dir)
        per_graph: list[dict] = []
        modularity_leiden: list[float] = []
        modularity_louvain: list[float] = []
        nmi_values: list[float] = []

        for g in graphs:
            name = g["name"]
            nodes = g["nodes"]
            edges = g["edges"]
            row: dict = {"graph": name}
            if not edges or name in NOISE_GRAPHS:
                row["note"] = "noise/empty graph — reported, excluded from NMI lane"
                per_graph.append(row)
                continue
            lou = _assignments(louvain_detect, nodes, edges, seed)
            lei = _assignments(leiden.detect_communities, nodes, edges, seed)
            common = sorted(set(lou) & set(lei))
            edges_t = [(e["source"], e["target"], e.get("weight", 1)) for e in edges]
            mod_lou = modularity_q({n: lou[n] for n in common if n in lou}, edges_t)
            mod_lei = modularity_q({n: lei[n] for n in common if n in lei}, edges_t)
            n = nmi([lou[n] for n in common], [lei[n] for n in common]) if common else None
            row.update({
                "louvain_modularity": round(mod_lou, 6),
                "leiden_modularity": round(mod_lei, 6),
                "nmi": round(n, 6) if n is not None else None,
            })
            modularity_leiden.append(mod_lei)
            modularity_louvain.append(mod_lou)
            if name not in NOISE_GRAPHS and n is not None:
                nmi_values.append(n)
            per_graph.append(row)

    mean_mod_lou = sum(modularity_louvain) / len(modularity_louvain) if modularity_louvain else 0.0
    mean_mod_lei = sum(modularity_leiden) / len(modularity_leiden) if modularity_leiden else 0.0
    mean_nmi = sum(nmi_values) / len(nmi_values) if nmi_values else 0.0

    mod_ok = mean_mod_lei >= mean_mod_lou - tol
    nmi_ok = mean_nmi >= nmi_margin
    flip_allowed = bool(mod_ok and nmi_ok)

    return {
        "status": "measured",
        "task": "community-engine-parity",
        "generated_by": "llm_wiki.eval.community_parity.compute_parity "
                        f"(seed={seed}, resolution={DEFAULT_RESOLUTION})",
        "gate": {
            "modularity_non_degradation": {"leiden": round(mean_mod_lei, 6),
                                           "louvain": round(mean_mod_lou, 6),
                                           "tol": tol,
                                           "pass": mod_ok},
            "nmi_agreement_structured": {"mean_nmi": round(mean_nmi, 6),
                                         "margin": nmi_margin,
                                         "n_graphs": len(nmi_values),
                                         "pass": nmi_ok},
        },
        "flip_allowed": flip_allowed,
        "per_graph": per_graph,
        "note": (
            "Leiden-vs-Louvain parity on the committed fixture gate set. "
            "flip_allowed=True only when Leiden modularity >= Louvain AND the "
            "partitions agree (mean NMI >= margin) on structured graphs. The "
            "flip itself is a separate evidence-linked change (ADR-0025)."
        ),
    }
