"""LWM_033 ask eval gate — gold-set integrity + baseline reproducibility + fail-on-drop.

Re-derives the committed ``tests/eval/baseline/ask_baseline.json`` from the
frozen ask gold set + the deterministic AskConceptEmbedder. Citation
precision@k on the GATE split must match the committed artifact exactly
(reproducibility) and must not regress it (fail-on-drop, ADR-0022). The gate
scores the DETERMINISTIC retrieval context — never the LLM call (AC#2).
"""

import json
from pathlib import Path

from llm_wiki.eval.ask_baseline import (
    ASK_GOLD_SUMMARIES,
    AskConceptEmbedder,
    build_ask_gold_wiki,
    compute_ask_baseline,
    load_ask_goldset,
    run_ask_baseline,
    split_items,
)

REPO_ROOT = Path(__file__).resolve().parent
GOLDSET = REPO_ROOT / "eval" / "gold" / "ask_goldset.json"
BASELINE = REPO_ROOT / "eval" / "baseline" / "ask_baseline.json"
_TOL = 1e-6


def _as_json(obj):
    """JSON artifact form (int dict keys serialize to strings)."""
    return json.loads(json.dumps(obj))


def _wiki(tmp_path):
    return build_ask_gold_wiki(tmp_path, embedder=AskConceptEmbedder())


# ── gold-set integrity ───────────────────────────────────────────────────────

def test_ask_goldset_committed_and_wellformed():
    data = json.loads(GOLDSET.read_text(encoding="utf-8"))
    assert data["task"] == "ask-qa"
    assert data.get("items"), "ask gold set must have items"
    for item in data["items"]:
        assert "question" in item and "relevant" in item and "split" in item
        assert item["split"] in ("tune", "gate")
        assert item.get("kind") in ("positive", "negative")


def test_ask_goldset_tune_gate_disjoint():
    data = load_ask_goldset(GOLDSET)  # raises ValueError on overlap
    tune = {i["question"] for i in data["items"] if i["split"] == "tune"}
    gate = {i["question"] for i in data["items"] if i["split"] == "gate"}
    assert tune and gate
    assert tune.isdisjoint(gate)


def test_ask_goldset_negatives_are_gate_only():
    data = load_ask_goldset(GOLDSET)
    negatives = [i for i in data["items"] if i.get("kind") == "negative"]
    assert negatives, "ask gold set must contain gibberish negatives"
    for item in negatives:
        assert item["relevant"] == []
        assert item["split"] == "gate"


def test_ask_goldset_positives_grounded_in_gold_wiki():
    """Positive relevant stems must resolve to ask gold wiki pages: the search
    gold pages OR the community-summary pages in ASK_GOLD_SUMMARIES."""
    known = set(ASK_GOLD_SUMMARIES) | {
        "neural_network", "deep_learning", "backpropagation", "layers",
        "gradient_descent", "transformer", "self_attention", "encoder",
        "positional_encoding", "coffee", "espresso", "latte", "caffeine",
        "memory_management", "caching",
    }
    data = load_ask_goldset(GOLDSET)
    for item in data["items"]:
        if item.get("kind") == "positive":
            assert item["relevant"], f"positive question needs >=1 relevant page"
            for stem in item["relevant"]:
                assert stem in known, f"unlabelable relevant stem: {stem}"


# ── baseline reproducibility + fail-on-drop ──────────────────────────────────

def test_ask_baseline_artifact_committed_and_wellformed():
    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    for key in ("task", "split", "tolerance", "k", "hybrid", "keyword",
                "generated_by", "note"):
        assert key in data, f"ask baseline missing {key}"
    assert data["task"] == "ask-qa"
    assert data["split"] == "gate"
    for mode in ("hybrid", "keyword"):
        assert set(data[mode]["precision_at_k"]) == {"1", "3", "5"}
        assert 0.0 <= data[mode]["negative_pass_rate"] <= 1.0


def test_ask_baseline_reproducible(tmp_path):
    """Re-derive the committed baseline; numbers must match exactly."""
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    root = _wiki(tmp_path)
    gate_items = split_items(load_ask_goldset(GOLDSET), "gate")
    hy = run_ask_baseline(root, gate_items, "hybrid",
                          embedder=AskConceptEmbedder())
    assert _as_json(hy) == baseline["hybrid"], (
        f"hybrid ask numbers drifted: {_as_json(hy)} != {baseline['hybrid']}"
    )


def test_ask_baseline_meets_committed(tmp_path):
    """Fail-on-drop: citation precision@k >= the committed baseline (AC#5)."""
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    root = _wiki(tmp_path)
    gate_items = split_items(load_ask_goldset(GOLDSET), "gate")
    hy = run_ask_baseline(root, gate_items, "hybrid",
                          embedder=AskConceptEmbedder())
    committed = baseline["hybrid"]
    got = _as_json(hy)
    assert hy["negative_pass_rate"] >= committed["negative_pass_rate"] - _TOL
    for kk in ("1", "3", "5"):
        assert got["precision_at_k"][kk] >= committed["precision_at_k"][kk] - _TOL, (
            f"hybrid citation precision@{kk} dropped below committed baseline"
        )


def test_compute_ask_baseline_matches_artifact(tmp_path):
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    root = _wiki(tmp_path)
    recomputed = compute_ask_baseline(root, GOLDSET,
                                      embedder=AskConceptEmbedder())
    assert _as_json(recomputed["hybrid"]) == baseline["hybrid"]
    assert _as_json(recomputed["keyword"]) == baseline["keyword"]
    assert recomputed["tolerance"] == baseline["tolerance"]


def test_gibberish_negative_empty(tmp_path):
    """Gibberish questions return no citations under hybrid AND keyword."""
    root = _wiki(tmp_path)
    negatives = [i for i in split_items(load_ask_goldset(GOLDSET), "gate")
                 if i.get("kind") == "negative"]
    assert negatives
    for mode in ("keyword", "hybrid"):
        res = run_ask_baseline(root, negatives, mode,
                               embedder=AskConceptEmbedder() if mode == "hybrid" else None)
        assert res["negative_pass_rate"] == 1.0, (
            f"gibberish leaked under {mode}: {res}"
        )


def test_hybrid_ge_keyword_on_gate(tmp_path):
    """The ask default (hybrid + summary rerank) does not regress keyword."""
    root = _wiki(tmp_path)
    gate_items = split_items(load_ask_goldset(GOLDSET), "gate")
    hy = _as_json(run_ask_baseline(root, gate_items, "hybrid",
                                   embedder=AskConceptEmbedder()))
    kw = _as_json(run_ask_baseline(root, gate_items, "keyword"))
    for kk in ("1", "3", "5"):
        assert hy["precision_at_k"][kk] >= kw["precision_at_k"][kk] - _TOL
