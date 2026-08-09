"""Derived-edge NMI+modularity gate eval (LWM_029 AC#5 / ADR-0027 §gate).

Positive + negative + fail-closed probes for ``should_include_derived``, and the
deterministic metric fixtures that back the committed eval-baseline keys
(``derived_edge_gate``, ``community_summary_faithfulness`` in
``tests/eval/baseline/eval_baseline.json`` — recomputed by
``tests/test_eval_regression.py``).

Deterministic by construction: fixed synthetic graphs, fixed Louvain seed (42),
and a fake summary set — no LLM, no randomness.
"""

import json

from llm_wiki.eval.cluster_metrics import nmi
from llm_wiki.graph import derived_edges as de

TOL = 1e-6  # mirrors the search-gate epsilon (test_eval_regression._TOL)


# ── Deterministic fixtures (shared with the regression baseline) ────────────

def derived_gate_fixture():
    """Two 3-node path clusters with no cross edges.

    Derived = intra-cluster completion edges (a-c, d-f): the derived layer must
    NOT destroy the wikilink community structure, so the gate allows inclusion.
    """
    nodes = [{"id": n} for n in "abcdef"]
    wikilink = [
        {"source": "a", "target": "b", "weight": 1},
        {"source": "b", "target": "c", "weight": 1},
        {"source": "d", "target": "e", "weight": 1},
        {"source": "e", "target": "f", "weight": 1},
    ]
    derived = [
        {"source": "a", "target": "c", "weight": 1, "relType": de.REL_SIMILAR,
         "layer": "derived", "provenance": {"cosine": 0.9}},
        {"source": "d", "target": "f", "weight": 1, "relType": de.REL_SIMILAR,
         "layer": "derived", "provenance": {"cosine": 0.9}},
    ]
    return nodes, wikilink, derived


def _bridging_derived_fixture():
    """Dense cross-cluster derived edges — the classic community-blobbing case."""
    nodes, wikilink, _ = derived_gate_fixture()
    derived = [
        {"source": s, "target": t, "weight": 5, "relType": de.REL_SIMILAR,
         "layer": "derived"}
        for s in "abc" for t in "def"
    ]
    return nodes, wikilink, derived


def compute_derived_gate_metrics() -> dict:
    """Recompute the committed ``derived_edge_gate`` baseline values."""
    nodes, wikilink, derived = derived_gate_fixture()
    include, report = de.should_include_derived(nodes, wikilink, derived, tol=TOL)
    return {
        "nmi_with_vs_baseline": report["nmi_with_vs_baseline"],
        "baseline_modularity": report["baseline_modularity"],
        "with_derived_modularity": report["with_derived_modularity"],
        "tol": TOL,
        "included": include,
    }


def compute_faithfulness_metric() -> dict:
    """Recompute the committed ``community_summary_faithfulness`` baseline."""
    from llm_wiki.graph.summarize import summary_faithfulness

    summaries = [
        {"community": 0, "key_entities": ["Alpha", "Beta"]},   # all members
        {"community": 1, "key_entities": ["Gamma", "Delta"]},  # Delta hallucinated
        {"community": 2, "key_entities": []},                  # vacuous → faithful
    ]
    members = {0: {"Alpha", "Beta"}, 1: {"Gamma"}, 2: set()}
    return {
        "faithfulness": round(summary_faithfulness(summaries, members), 6),
        "n_summaries": len(summaries),
    }


# ── Wiki scaffolding for the consumer-level probes ──────────────────────────

def _make_path_wiki(tmp_path):
    """Flat wiki: two path clusters (a-b-c, d-e-f) with no cross wikilinks."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    links = {"a": "b", "b": "c", "d": "e", "e": "f"}
    for name in "abcdef":
        target = links.get(name)
        body = f"---\ntitle: {name.upper()}\ntype: concept\n---\n\n# {name.upper()}\n\n"
        body += f"See [[{target.upper()}]]." if target else f"Page {name.upper()}."
        (wiki / f"{name}.md").write_text(body, encoding="utf-8")
    return tmp_path, wiki


def _write_layer(root, edges: list[dict]) -> None:
    p = de.derived_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"version": 1, "edges": edges}), encoding="utf-8")


# ── Gate probes ─────────────────────────────────────────────────────────────

def test_inclusion_requires_nmi_ge_baseline():
    nodes, wikilink, derived = derived_gate_fixture()
    include, report = de.should_include_derived(nodes, wikilink, derived, tol=TOL)

    # NMI between the with-derived and wikilink-only partitions ~ 1 (structure
    # preserved), modularity not degraded → inclusion allowed.
    assert report["nmi_with_vs_baseline"] >= 1.0 - TOL
    assert report["with_derived_modularity"] >= report["baseline_modularity"]
    assert include is True

    # Explicit NMI cross-check on the partitions themselves (ADR-0012 machinery).
    from llm_wiki.graph.louvain import louvain
    ids = [n["id"] for n in nodes]
    baseline_part = louvain(wikilink, nodes=ids, seed=42)
    with_part = louvain(wikilink + derived, nodes=ids, seed=42)
    labels_b = [baseline_part[n] for n in ids]
    labels_w = [with_part[n] for n in ids]
    assert nmi(labels_b, labels_w) >= 1.0 - TOL


def test_inclusion_refused_when_degrades(tmp_path):
    # Gate level: dense cross-cluster derived edges destroy the structure.
    nodes, wikilink, bridging = _bridging_derived_fixture()
    include, report = de.should_include_derived(nodes, wikilink, bridging, tol=TOL)
    assert include is False
    assert report["nmi_with_vs_baseline"] < 1.0 - TOL
    assert report["with_derived_modularity"] < report["baseline_modularity"]
    assert "fail-closed" in report["reason"]

    # Consumer level: the on-disk layer is refused and the wikilink-only result
    # is returned — no crash, no partial inclusion.
    root, _wiki = _make_path_wiki(tmp_path)
    _write_layer(root, bridging)
    from llm_wiki.graph.insights import compute_insights

    plain = compute_insights(root, fmt="json")
    requested = compute_insights(root, fmt="json", include_derived=True)
    assert requested["derivedGate"]["included"] is False
    assert requested["summary"]["edgeCount"] == plain["summary"]["edgeCount"] == 4
    assert requested["surprisingConnections"] == plain["surprisingConnections"]


def test_inclusion_allowed_via_consumer(tmp_path):
    # Positive consumer probe: benign intra-cluster layer is included on demand.
    root, _wiki = _make_path_wiki(tmp_path)
    nodes, wikilink, derived = derived_gate_fixture()
    _write_layer(root, derived)
    from llm_wiki.graph.insights import compute_insights

    plain = compute_insights(root, fmt="json")
    requested = compute_insights(root, fmt="json", include_derived=True)
    assert requested["derivedGate"]["included"] is True
    assert requested["summary"]["edgeCount"] == plain["summary"]["edgeCount"] + 2
    assert "derivedGate" not in plain  # default runs carry no gate key


def test_fail_closed_without_layer(tmp_path):
    root, _wiki = _make_path_wiki(tmp_path)

    # Gate level: no derived edges → refused, no crash.
    include, report = de.should_include_derived([{"id": "a"}, {"id": "b"}],
                                                [{"source": "a", "target": "b",
                                                  "weight": 1}], [], tol=TOL)
    assert include is False
    assert "no derived edges" in report["reason"]

    # Consumer level: --include-derived with no layer on disk → wikilink-only,
    # output identical to a default run.
    from llm_wiki.graph.insights import compute_insights

    plain = compute_insights(root, fmt="json")
    requested = compute_insights(root, fmt="json", include_derived=True)
    assert requested["derivedGate"]["included"] is False
    assert requested["derivedGate"]["reason"] == "no derived edges"
    assert requested["summary"] == plain["summary"]
    assert requested["surprisingConnections"] == plain["surprisingConnections"]


def test_wikilink_dupes_dropped_before_gate(tmp_path):
    # A derived edge duplicating a wikilink must not double-count: it is dropped
    # by the generator, and the gate runs over the deduped layer.
    root, wiki = _make_path_wiki(tmp_path)
    (wiki / "a.md").write_text(
        "---\ntitle: A\ntype: concept\n---\n\n# A\n\nSee [[B]].\n",
        encoding="utf-8",
    )
    (wiki / "b.md").write_text(
        "---\ntitle: B\ntype: concept\nsources: [paper-a]\n---\n\n# B\n\n",
        encoding="utf-8",
    )
    (wiki / "c.md").write_text(
        "---\ntitle: C\ntype: concept\nsources: [paper-a]\n---\n\n# C\n\n",
        encoding="utf-8",
    )
    de.generate_derived_edges(root, min_shared_sources=1)
    edges = de.load_derived_edges(root)
    keys = {de._undirected_key(e["source"], e["target"]) for e in edges}
    assert de._undirected_key("a", "b") not in keys  # a<->b is a wikilink


def test_nested_wiki_consumer_gate_in_id_space(tmp_path):
    # Pages live in a SUBDIRECTORY, so insights ids are "concepts/a" while the
    # derived layer uses page stems. The consumer must remap the layer into its
    # id space BEFORE gating — a disjoint (unmapped) edge set would make the
    # gate spuriously pass a blobbing layer (regression guard).
    root = tmp_path / "root"
    wiki = root / "wiki" / "concepts"
    wiki.mkdir(parents=True)
    links = {"a": "b", "b": "c", "d": "e", "e": "f"}
    for name in "abcdef":
        target = links.get(name)
        body = f"---\ntitle: {name}\ntype: concept\n---\n\n# {name}\n\n"
        body += f"See [[{target}]]." if target else f"Page {name}."
        (wiki / f"{name}.md").write_text(body, encoding="utf-8")

    # Blobbing layer: dense cross-cluster derived edges (stem space on disk).
    nodes, wikilink, bridging = _bridging_derived_fixture()
    _write_layer(root, bridging)

    from llm_wiki.graph.insights import compute_insights

    plain = compute_insights(root, fmt="json")
    requested = compute_insights(root, fmt="json", include_derived=True)
    assert requested["derivedGate"]["included"] is False
    assert requested["derivedGate"]["nmi_with_vs_baseline"] < 1.0 - TOL
    # Fail-closed: wikilink-only result, no blobbed edges leaked in.
    assert requested["summary"]["edgeCount"] == plain["summary"]["edgeCount"] == 4
