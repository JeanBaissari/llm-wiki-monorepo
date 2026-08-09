"""ER-F1 eval gate (LWM_025 AC#7 / LWM_026 AC#5 / ADR-0024).

Enforces the committed entity-resolution quality floor: on the held-out GATE
split of ``tests/eval/gold/er_goldset.json``, pairwise merge F1 / precision /
recall must never drop below the committed ``tests/eval/baseline/er_baseline.json``
(fail-on-drop), and every must-not-merge negative pair must stay in separate
predicted clusters. LWM_026 AC#5 additionally proves that a richer extractor
(GLiNER-style, perfect candidate recall) holds or improves ER-F1 over the
regex default — never regresses it. Runs deterministically in CI.
"""

import json
from pathlib import Path

import pytest

from llm_wiki.eval.er_metrics import er_f1, merges_to_clusters
from llm_wiki.graph.extract import get_extractor
from llm_wiki.graph.resolve import normalize, resolve_entities

_BASELINE = Path("tests/eval/baseline/er_baseline.json")
_GOLDSET = Path("tests/eval/gold/er_goldset.json")
_TOL = 1e-6


def _splits():
    """(gate items, tune items) — each item is a dict from the goldset."""
    items = json.loads(_GOLDSET.read_text())["items"]
    return [i for i in items if i["split"] == "gate"], [
        i for i in items if i["split"] == "tune"
    ]


def _surfaces(items) -> list[str]:
    return [s for i in items for s in i["surfaces"]]


def _gold_clusters(items) -> list[set[str]]:
    return [set(i["surfaces"]) for i in items if i["kind"] == "positive"]


def _negatives(items) -> list[list[str]]:
    return [i["surfaces"] for i in items if i["kind"] == "negative"]


def _predicted(candidates: list[str]) -> list[set[str]]:
    return merges_to_clusters(resolve_entities(candidates))


def _er_report(candidates: list[str], gate_items: list[dict]) -> dict:
    return er_f1(_gold_clusters(gate_items), _predicted(candidates))


def test_er_f1_meets_baseline():
    """Fail-on-drop gate: string-only resolution on the GATE split never regresses."""
    baseline = json.loads(_BASELINE.read_text())
    for key in ("f1", "precision", "recall", "n_gate_pairs", "split", "must_not_merge_pass"):
        assert key in baseline, f"baseline missing {key}"
    assert baseline["split"] == "gate"
    assert baseline["must_not_merge_pass"] is True

    gate, _ = _splits()
    rep = _er_report(_surfaces(gate), gate)

    assert rep["f1"] >= baseline["f1"] - _TOL, (
        f"ER-F1 regressed on gate split: {rep['f1']} < {baseline['f1']}"
    )
    assert rep["precision"] >= baseline["precision"] - _TOL, (
        f"ER precision regressed: {rep['precision']} < {baseline['precision']}"
    )
    assert rep["recall"] >= baseline["recall"] - _TOL, (
        f"ER recall regressed: {rep['recall']} < {baseline['recall']}"
    )


def test_must_not_merge_negatives():
    """LWM_025 AC#7: every must-not-merge pair on the GATE split stays separate."""
    gate, _ = _splits()
    predicted = _predicted(_surfaces(gate))
    for pair in _negatives(gate):
        a, b = pair
        assert not any(a in cl and b in cl for cl in predicted), (
            f"must-not-merge pair merged into one cluster: {a!r} ↔ {b!r}"
        )


def test_goldset_integrity():
    """Goldset shape: disjoint tune/gate, non-trivial normalization, negatives
    never coincide with a positive cluster."""
    gate, tune = _splits()
    gate_items = {tuple(sorted(i["surfaces"])) for i in gate}
    tune_items = {tuple(sorted(i["surfaces"])) for i in tune}
    assert not (gate_items & tune_items), "tune and gate splits must be disjoint"

    all_items = gate + tune
    for item in all_items:
        assert len(item["surfaces"]) >= 2
        for s in item["surfaces"]:
            assert normalize(s), f"surface normalizes to empty: {s!r}"

    positives = _gold_clusters(all_items)
    seen_negatives = set()
    for item in all_items:
        if item["kind"] != "negative":
            continue
        pair = tuple(sorted(item["surfaces"]))
        assert len(pair) == 2
        assert pair not in seen_negatives, f"duplicate negative pair: {pair}"
        seen_negatives.add(pair)
        a, b = pair
        for cluster in positives:
            assert not ({a, b} <= cluster), (
                f"negative pair also listed inside a positive cluster: {a!r} ↔ {b!r}"
            )


# --- LWM_026 AC#5: richer (GLiNER-style) candidates hold or improve ER-F1 ---
#
# Synthetic doc for the deterministic regex path: only a subset of each gate
# cluster's variants appear as bold/heading spans (what RegexExtractor sees);
# the rest appear in plain prose, so the regex candidate set has partial recall.
# The "rich" candidate set is exactly the goldset gate surfaces — perfect
# candidate recall, as a GLiNER-fed pipeline would aim for. All surfaces used
# here come verbatim from the gate split of er_goldset.json.
_GLINER_DOC = """## Model families

The flagship is **GPT-4**; the older **GPT 4** release is documented, and gpt-4 is the API name.

## Learning approaches

**Deep Learning** and **deep-learning** dominate the field; deep_learning is an alias.

## Architectures

**Neural Network** and **Neural Networks** are common spellings; neural-networks also appears.

## Orchestration

**Kubernetes** orchestrates clusters; **K8s** is the shorthand, and k8s appears in configs.

## Languages

**JavaScript** powers the frontend; Javascript is an old spelling.
"""


class _PerfectRecallExtractor:
    """Deterministic stand-in for a GLiNER-style rich extractor: returns the
    goldset gate surfaces exactly (perfect candidate recall on the gate split)."""

    def __init__(self, surfaces: list[str]) -> None:
        self._surfaces = list(surfaces)

    def extract_surfaces(self, text: str) -> list[str]:
        return list(self._surfaces)


def test_gliner_improves_or_holds_er_f1():
    """LWM_026 AC#5: ER-F1 with richer candidates never drops below the regex path."""
    gate, _ = _splits()
    regex_candidates = get_extractor().extract_surfaces(_GLINER_DOC)
    rich_candidates = _PerfectRecallExtractor(_surfaces(gate)).extract_surfaces(_GLINER_DOC)

    f1_regex = _er_report(regex_candidates, gate)
    f1_rich = _er_report(rich_candidates, gate)

    assert f1_rich["f1"] >= f1_regex["f1"] - _TOL, (
        f"rich extractor regressed ER-F1: {f1_rich['f1']} < {f1_regex['f1']}"
    )
    # Perfect candidate recall must reproduce the committed gate baseline exactly.
    baseline = json.loads(_BASELINE.read_text())
    assert f1_rich["f1"] == pytest.approx(baseline["f1"], abs=_TOL), (
        f"rich candidate run diverges from committed baseline: "
        f"{f1_rich['f1']} != {baseline['f1']}"
    )


def test_real_gliner_extractor_holds_er_f1():
    """LWM_026 AC#5 with the real GLiNER backend — skipped when [ner] is absent."""
    pytest.importorskip("gliner")
    from llm_wiki.graph.extract import GLiNERExtractor

    if not GLiNERExtractor.is_available():
        pytest.skip("GLiNER backend unavailable")
    gate, _ = _splits()
    regex_candidates = get_extractor("regex").extract_surfaces(_GLINER_DOC)
    gliner_candidates = GLiNERExtractor().extract_surfaces(_GLINER_DOC)

    f1_regex = _er_report(regex_candidates, gate)
    f1_gliner = _er_report(gliner_candidates, gate)
    assert f1_gliner["f1"] >= f1_regex["f1"] - _TOL, (
        f"GLiNER candidates regressed ER-F1: {f1_gliner['f1']} < {f1_regex['f1']}"
    )
