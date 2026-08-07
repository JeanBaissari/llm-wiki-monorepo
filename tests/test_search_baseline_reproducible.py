"""Search baseline reproducibility + fail-on-drop (LWM_032 / ADR-0020).

Re-derives the committed ``tests/eval/baseline/search_eval_baseline.json`` from
the frozen gold set + the deterministic concept embedder. The gate's numbers
must match the committed artifact exactly (reproducibility) and hybrid must not
regress keyword (fail-on-drop). CI additionally re-certifies with the real
[semantic] embedder (see tests/eval/test_real_wiki_gate.py).
"""

import json
from pathlib import Path

from llm_wiki.eval.search_baseline import (
    ConceptEmbedder,
    build_search_gold_wiki,
    compute_search_baseline,
    load_search_goldset,
    run_search_baseline,
    search_eval_gate,
    split_items,
)

REPO_ROOT = Path(__file__).resolve().parent
GOLDSET = REPO_ROOT / "eval" / "gold" / "search_goldset.json"
BASELINE = REPO_ROOT / "eval" / "baseline" / "search_eval_baseline.json"
_TOL = 1e-6


def _as_json(obj):
    """JSON artifact form (int dict keys serialize to strings)."""
    return json.loads(json.dumps(obj))


def test_baseline_artifact_is_committed_and_wellformed():
    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    for key in ("task", "split", "tolerance", "keyword", "hybrid",
                "allow_hybrid_default", "generated_by", "note"):
        assert key in data, f"search baseline missing {key}"
    assert data["task"] == "search-retrieval"
    assert data["split"] == "gate"  # gate the release on the held-out split
    assert data["tolerance"] == _TOL
    for mode in ("keyword", "hybrid"):
        assert set(data[mode]["precision_at_k"]) == {"1", "3", "5", "10"}
        assert 0.0 <= data[mode]["recall"] <= 1.0
        assert 0.0 <= data[mode]["negative_pass_rate"] <= 1.0


def test_search_baseline_reproducible(tmp_path):
    """Re-derive the baseline; committed numbers must match exactly."""
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    root = build_search_gold_wiki(tmp_path, embedder=ConceptEmbedder())
    gate_items = split_items(load_search_goldset(GOLDSET), "gate")

    kw = run_search_baseline(root, gate_items, "keyword")
    hy = run_search_baseline(root, gate_items, "hybrid",
                             embedder=ConceptEmbedder())
    allow, report = search_eval_gate(kw, hy)

    assert allow is True, report["reason"]
    # Compare as the JSON artifact (int dict keys serialize to strings).
    assert _as_json(kw) == baseline["keyword"], (
        f"keyword numbers drifted: {_as_json(kw)} != {baseline['keyword']}"
    )
    assert _as_json(hy) == baseline["hybrid"], (
        f"hybrid numbers drifted: {_as_json(hy)} != {baseline['hybrid']}"
    )
    assert allow == baseline["allow_hybrid_default"]


def test_fail_on_drop_vs_committed_baseline(tmp_path):
    """No drop below the committed baseline (fail-on-drop, ADR-0022)."""
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    root = build_search_gold_wiki(tmp_path, embedder=ConceptEmbedder())
    gate_items = split_items(load_search_goldset(GOLDSET), "gate")

    kw = run_search_baseline(root, gate_items, "keyword")
    hy = run_search_baseline(root, gate_items, "hybrid",
                             embedder=ConceptEmbedder())

    for mode, committed in (("keyword", baseline["keyword"]),
                            ("hybrid", baseline["hybrid"])):
        got = kw if mode == "keyword" else hy
        got_json = _as_json(got)
        assert got["recall"] >= committed["recall"] - _TOL, (
            f"{mode} recall dropped below committed baseline"
        )
        for kk in ("1", "3", "5", "10"):
            assert got_json["precision_at_k"][kk] >= committed["precision_at_k"][kk] - _TOL, (
                f"{mode} precision@{kk} dropped below committed baseline"
            )
        assert got["negative_pass_rate"] >= committed["negative_pass_rate"] - _TOL


def test_compute_search_baseline_matches_artifact(tmp_path):
    """The module-level artifact builder reproduces the committed file."""
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    root = build_search_gold_wiki(tmp_path, embedder=ConceptEmbedder())
    recomputed = compute_search_baseline(root, GOLDSET, embedder=ConceptEmbedder())
    assert _as_json(recomputed["keyword"]) == baseline["keyword"]
    assert _as_json(recomputed["hybrid"]) == baseline["hybrid"]
    assert recomputed["allow_hybrid_default"] == baseline["allow_hybrid_default"]
    assert recomputed["tolerance"] == baseline["tolerance"]


def test_gibberish_negative_empty_under_both_modes(tmp_path):
    """AC#6: the negative query stays empty under keyword AND hybrid."""
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    root = build_search_gold_wiki(tmp_path, embedder=ConceptEmbedder())
    negatives = [i for i in split_items(load_search_goldset(GOLDSET), "gate")
                 if i.get("kind") == "negative"]
    assert negatives
    for mode in ("keyword", "hybrid"):
        res = run_search_baseline(root, negatives, mode,
                                  embedder=ConceptEmbedder() if mode == "hybrid" else None)
        assert res["negative_pass_rate"] == 1.0, (
            f"gibberish leaked under {mode}: {res}"
        )
