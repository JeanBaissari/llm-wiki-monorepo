"""Tests for lightweight entity resolution (LWM_025).

Covers normalization, the two-signal merge safety rule, the reversible JSONL +
derived-cache store, apply/unmerge round-trips, and the ER-F1 gate metric.
"""

from llm_wiki.eval.er_metrics import er_f1, merges_to_clusters
from llm_wiki.graph import alias_store
from llm_wiki.graph.resolve import apply_resolution, normalize, resolve_entities, unmerge
from llm_wiki.semantic.embedder import Embedder
from llm_wiki.semantic.vector_schema import open_index_db


# ── normalization ────────────────────────────────────────────────────────────

def test_normalize_collapses_variants():
    assert normalize("GPT-4") == normalize("GPT 4") == normalize("gpt-4") == "gpt 4"
    assert normalize("Neural_Network") == "neural network"


# ── two-signal merge safety ──────────────────────────────────────────────────

class _ConceptEmbedder(Embedder):
    """Maps known surfaces to concept vectors so we can control embedding cosine."""
    model_id = "concept"
    revision = "r"
    normalization = "l2"
    quantization = "float32"
    _concepts = {
        "gpt 4": [1.0, 0.0, 0.0],
        "neural network": [0.0, 1.0, 0.0],
        "neural networks": [0.0, 1.0, 0.0],
        "neural net": [0.0, 1.0, 0.0],  # same concept as neural network(s)
        "graph neural net": [0.0, 1.0, 0.0],
        "graph neural networks": [0.0, 1.0, 0.0],
        "kubernetes": [0.0, 0.0, 1.0],
        "k8s": [0.0, 0.0, 1.0],  # same concept as kubernetes
    }

    @classmethod
    def is_available(cls):
        return True

    @property
    def dimension(self):
        return 3

    def embed(self, texts):
        return [self._concepts.get(normalize(t), [0.5, 0.5, 0.5]) for t in texts]


def test_identical_normalized_forms_always_merge():
    merges = resolve_entities(["GPT-4", "GPT 4", "gpt-4"])
    clusters = merges_to_clusters(merges)
    assert len(clusters) == 1
    assert clusters[0] == {"GPT-4", "GPT 4", "gpt-4"}


def test_no_embedder_is_conservative():
    # "K8s"/"Kubernetes" have low string similarity → must NOT merge without a
    # second signal.
    merges = resolve_entities(["Kubernetes", "K8s"])
    assert merges_to_clusters(merges) == []
    # Same for a same-block pair: string-only path runs at the RAISED bar
    # (≥0.92), so "Neural Net"/"Neural Networks" (ss ≈ 0.80) must not merge.
    merges = resolve_entities(["Neural Net", "Neural Networks"])
    assert merges_to_clusters(merges) == []


def test_two_signal_rule_requires_both():
    emb = _ConceptEmbedder()
    # Graph Neural Net / Graph Neural Networks: same block, ss ≈ 0.865 (below
    # the 0.92 string-only bar) AND cos = 1.0 → only the two-signal path can
    # merge them. If the resolver ever regressed to string-only (≥0.92) or to
    # embedding-alone, this positive control would fail.
    m1 = merges_to_clusters(resolve_entities(
        ["Graph Neural Net", "Graph Neural Networks"], embedder=emb))
    assert any({"Graph Neural Net", "Graph Neural Networks"} <= c for c in m1)

    # Neural Net / Neural Networks: same block (shared token "neural"),
    # ss ≈ 0.80 < str_threshold, cos = 1.0. Both signals are present but the
    # string signal is below threshold → the two-signal union path evaluates
    # the pair and REJECTS it (resolve.py: ss >= str_threshold and cos >=
    # cos_threshold). This is the non-vacuous rejection: if the resolver ever
    # merged on embedding alone, this pair would merge and the test would fail.
    m2 = merges_to_clusters(resolve_entities(
        ["Neural Net", "Neural Networks"], embedder=emb))
    assert m2 == []

    # K8s / Kubernetes: high embedding but LOW string → must stay unmerged
    # (embedding alone can never justify a merge — ADR-0021/0024). The pair
    # shares no block (no common token/3-char prefix), so it is never even
    # scored — the union path is not reached, making this an additional
    # (blocking-level) case, not the primary rejection proof above.
    m3 = merges_to_clusters(resolve_entities(["Kubernetes", "K8s"], embedder=emb))
    assert m3 == []


# ── reversible store round-trip ──────────────────────────────────────────────

def test_apply_resolution_and_reversibility(tmp_path):
    stats = apply_resolution(tmp_path, ["GPT-4", "GPT 4", "gpt-4", "Rust", "Golang"])
    assert stats["merged"] == 2  # two aliases fold into one canonical
    assert stats["canonicals"] == 1

    # JSONL is the source of truth and is append-only / diffable.
    events = alias_store.read_events(tmp_path)
    assert [e["event"] for e in events] == ["merge", "merge"]

    conn = open_index_db(tmp_path / ".index" / "wiki.db")
    try:
        # derived cache maps the two aliases → the same canonical id
        cid = alias_store.canonical_for(conn, "GPT-4")
        assert cid is not None
        assert alias_store.canonical_for(conn, "gpt-4") == cid
        assert alias_store.alias_meta_matches(conn, "lightweight-v1", 0.85) is True
    finally:
        conn.close()

    # Reverse one merge → that alias no longer resolves; the other stays.
    assert unmerge(tmp_path, "GPT-4") is True
    conn = open_index_db(tmp_path / ".index" / "wiki.db")
    try:
        assert alias_store.canonical_for(conn, "GPT-4") is None
        assert alias_store.canonical_for(conn, "gpt-4") is not None  # other alias intact
    finally:
        conn.close()
    # unmerge of an unknown alias is a no-op
    assert unmerge(tmp_path, "does-not-exist") is False


def test_derived_cache_rebuilds_from_jsonl(tmp_path):
    apply_resolution(tmp_path, ["GPT-4", "gpt-4"])
    # Wipe the derived tables; a reader rebuild from the JSONL restores them.
    conn = open_index_db(tmp_path / ".index" / "wiki.db")
    try:
        conn.execute("DROP TABLE IF EXISTS entity_aliases")
        conn.execute("DROP TABLE IF EXISTS alias_meta")
        conn.commit()
        n = alias_store.rebuild_derived(conn, tmp_path, "lightweight-v1", 0.85)
        assert n >= 1
        assert alias_store.canonical_for(conn, "gpt-4") is not None
    finally:
        conn.close()


# ── ER-F1 gate metric ────────────────────────────────────────────────────────

def test_er_f1():
    gold = [{"GPT-4", "GPT 4", "gpt-4"}, {"Rust"}]
    perfect = er_f1(gold, [{"GPT-4", "GPT 4", "gpt-4"}])
    assert perfect["f1"] == 1.0
    # A false merge (Rust+Go) drops precision; a missed pair drops recall.
    over = er_f1(gold, [{"GPT-4", "GPT 4", "gpt-4"}, {"Rust", "Go"}])
    assert over["fp"] == 1 and over["precision"] < 1.0
    under = er_f1(gold, [{"GPT-4", "GPT 4"}])  # missed gpt-4 pairs
    assert under["fn"] == 2 and under["recall"] < 1.0
