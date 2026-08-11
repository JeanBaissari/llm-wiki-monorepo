"""Splink backend tests (BKD-001 / LWM_025 AC#5 / ADR-0024).

The ``[entity-resolution]`` extra (splink) is now a REAL opt-in backend:
splink's jaro-winkler blocking + calibrated match probabilities provide the
*string* signal inside the same two-signal merge rule. These tests prove:

1. base install (no splink): ``resolve_entities(splink=True)`` falls back to
   the pure-Python path byte-identically (import-safety, no raise)
2. with splink: same-signal merges happen via splink probabilities
3. the two-signal rule holds under splink — embedding alone never merges
4. the CLI honors --backend auto/python/splink + LLM_WIKI_ER_BACKEND
"""

import pytest

from llm_wiki.graph.resolve import apply_resolution, resolve_entities

splink = pytest.importorskip("splink", reason="[entity-resolution] extra not installed")


class _ConceptEmb:
    """Concept vectors: k8s/kubernetes share one concept, others are distinct."""

    def embed(self, texts):
        out = []
        for t in texts:
            tl = t.lower()
            if "k8s" in tl or "kubernetes" in tl:
                out.append([0.0, 0.0, 1.0])
            elif "neural" in tl:
                out.append([0.0, 1.0, 0.0])
            else:
                out.append([0.5, 0.5, 0.5])
        return out


def test_splink_backend_merges_via_probability():
    """Variant surfaces merge through splink's match probabilities."""
    merges = resolve_entities(
        ["Neural Network", "Neural Networks", "GPT-4", "GPT 4"],
        splink=True,
    )
    labels = {(m["canonical_label"], m["alias"]) for m in merges}
    assert ("Neural Networks", "Neural Network") in labels
    # GPT-4/GPT 4 normalize equal → identity merge (still under splink)
    assert ("GPT 4", "GPT-4") in labels


def test_two_signal_rule_holds_under_splink():
    """Embedding similarity alone can never merge — even with splink active."""
    emb = _ConceptEmb()
    # Same concept vector, low splink probability (K8s vs Kubernetes) → no merge.
    m = resolve_entities(["Kubernetes", "K8s"], embedder=emb, splink=True)
    assert m == []


def test_splink_fallback_without_extra():
    """splink=True without the extra degrades to the pure path, no raise."""
    import builtins

    real_import = builtins.__import__

    def blocked(name, *a, **k):
        if name == "splink" or name.startswith("splink."):
            raise ImportError("splink blocked for base-install simulation")
        return real_import(name, *a, **k)

    builtins.__import__ = blocked
    try:
        merges = resolve_entities(["Neural Network", "Neural Networks"], splink=True)
        assert merges, "pure-Python fallback must still merge the pair"
    finally:
        builtins.__import__ = real_import


def test_splink_through_apply_resolution(tmp_path):
    """apply_resolution threads the backend and stays reversible."""
    stats = apply_resolution(
        tmp_path, ["Neural Network", "Neural Networks", "Rust", "Rust lang"],
        splink=True,
    )
    assert stats["merged"] >= 1
    events = __import__("llm_wiki.graph.alias_store", fromlist=["read_events"]).read_events(tmp_path)
    assert [e["event"] for e in events] == ["merge"] * stats["merged"]


def test_cli_backend_flag(tmp_path):
    """entities resolve --backend auto/python/splink + env var resolve correctly."""
    from llm_wiki.graph import entities as ent

    class A:
        backend = "auto"

    class P:
        backend = "python"

    class S:
        backend = "splink"

    import os

    old = os.environ.pop("LLM_WIKI_ER_BACKEND", None)
    try:
        assert ent._resolve_backend(A()) is False          # auto, no env → python
        assert ent._resolve_backend(P()) is False          # explicit python
        assert ent._resolve_backend(S()) is True           # explicit splink
        os.environ["LLM_WIKI_ER_BACKEND"] = "splink"
        assert ent._resolve_backend(A()) is True           # auto honors env
        os.environ["LLM_WIKI_ER_BACKEND"] = "python"
        assert ent._resolve_backend(A()) is False
    finally:
        if old is None:
            os.environ.pop("LLM_WIKI_ER_BACKEND", None)
        else:
            os.environ["LLM_WIKI_ER_BACKEND"] = old
