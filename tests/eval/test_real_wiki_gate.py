"""Real-wiki search gate lane (LWM_032 / ADR-0020, AD-3/AD-11).

The local gate (tests/test_search_eval_gate.py) certifies the hybrid-default
flip with the deterministic concept embedder so it is reproducible offline. This
lane re-certifies with the **real** [semantic] embedder (model2vec) on a real
wiki built from the populated fixture — labels here are GATE-only and never
tuned, per the LWM_032 split policy.

Runs in CI's `semantic` job (which installs the [semantic] extra); skips
locally when the extra is absent so the default install stays lexical-only.
"""

import shutil

import pytest

from llm_wiki.eval.search_baseline import (
    run_search_baseline,
    search_eval_gate,
)
from llm_wiki.search.index import index_wiki
from llm_wiki.semantic import is_semantic_available
from llm_wiki.semantic.embed import embed_wiki

pytestmark = pytest.mark.skipif(
    not is_semantic_available(),
    reason="[semantic] extra not installed — real-embedder lane runs in CI semantic job",
)

FIXTURE = (
    __import__("pathlib").Path(__file__).resolve().parents[1]
    / "fixtures" / "wikis" / "populated"
)

# Held-out, never-tuned labels against the populated fixture wiki. Every
# positive query's relevant pages contain its terms (keyword recall is
# anchored), and hybrid fusion may only add vector-relevant results.
REAL_WIKI_GATE_LABELS = [
    {"query": "attention mechanism", "relevant": ["attention_mechanism"],
     "split": "gate", "kind": "positive"},
    {"query": "gradient descent optimization", "relevant": ["gradient_descent"],
     "split": "gate", "kind": "positive"},
    {"query": "large language model", "relevant": ["llm"],
     "split": "gate", "kind": "positive"},
    {"query": "deep learning neural network", "relevant": ["deep_learning", "neural_network"],
     "split": "gate", "kind": "positive"},
    {"query": "splitting text into tokens", "relevant": ["tokenization"],
     "split": "gate", "kind": "positive"},
    {"query": "zzzznonexistentqqq wut", "relevant": [],
     "split": "gate", "kind": "negative"},
]


def test_real_wiki_labels_are_gate_only():
    for item in REAL_WIKI_GATE_LABELS:
        assert item["split"] == "gate", "real-wiki labels must be gate-only"
    assert any(i["kind"] == "negative" for i in REAL_WIKI_GATE_LABELS)


def test_real_wiki_labels_target_existing_pages(tmp_path):
    """The labels must reference real fixture pages (page-id = file stem)."""
    pages = set()
    for p in (FIXTURE / "wiki").rglob("*.md"):
        pages.add(p.stem)
    for item in REAL_WIKI_GATE_LABELS:
        for pid in item["relevant"]:
            assert pid in pages, f"label references missing page: {pid}"


def test_real_wiki_gate_with_real_embedder(tmp_path):
    """The full search-eval gate on a real wiki with the real embedder."""
    root = tmp_path / "wiki"
    shutil.copytree(FIXTURE, root)
    index_wiki(root, rebuild=True)
    stats = embed_wiki(root)  # real embedder via get_embedder()
    assert stats["available"] is True and stats["total"] > 0

    kw = run_search_baseline(root, REAL_WIKI_GATE_LABELS, "keyword")
    hy = run_search_baseline(root, REAL_WIKI_GATE_LABELS, "hybrid")
    allow, report = search_eval_gate(kw, hy)

    assert allow is True, report["reason"]
    assert hy["recall"] >= kw["recall"]
    assert hy["negative_pass_rate"] == 1.0  # gibberish stayed empty


def test_real_wiki_hybrid_recall_ge_keyword(tmp_path):
    """Hybrid must never regress keyword recall on the real wiki."""
    root = tmp_path / "wiki"
    shutil.copytree(FIXTURE, root)
    index_wiki(root, rebuild=True)
    embed_wiki(root)

    kw = run_search_baseline(root, REAL_WIKI_GATE_LABELS, "keyword")
    hy = run_search_baseline(root, REAL_WIKI_GATE_LABELS, "hybrid")
    assert hy["recall"] >= kw["recall"] - 1e-6
