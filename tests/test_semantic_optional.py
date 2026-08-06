"""Tests for the optional semantic layer boundary (LWM_013 / LWM_015).

These assert the "additive / opt-in" invariant: the package imports cleanly and
degrades to ``None``/``False`` when the ``[semantic]`` extra is not installed,
so nothing in the base install changes behavior.
"""

import importlib


def test_import_semantic_is_safe_without_extra():
    # Must never raise, even when model2vec/numpy/sqlite-vec are absent.
    mod = importlib.import_module("llm_wiki.semantic")
    assert hasattr(mod, "is_semantic_available")
    assert hasattr(mod, "get_embedder")


def test_probe_returns_bool():
    from llm_wiki.semantic import is_semantic_available

    assert isinstance(is_semantic_available(), bool)


def test_get_embedder_matches_availability():
    from llm_wiki.semantic import get_embedder, is_semantic_available

    emb = get_embedder()
    if is_semantic_available():
        assert emb is not None
        # Interface surface is present without forcing a model download.
        assert hasattr(emb, "embed")
        assert hasattr(emb, "dimension")
        assert callable(emb.embed_meta)
    else:
        # No extra installed → callers fall back to the lexical path.
        assert emb is None


def test_get_embedder_unknown_backend_is_none():
    from llm_wiki.semantic import get_embedder

    assert get_embedder("does-not-exist") is None


def test_embed_meta_is_a_stable_record():
    from llm_wiki.semantic import EmbedMeta

    m = EmbedMeta(
        model_id="minishlab/potion-retrieval-32M",
        revision="",
        dimension=8,
        normalization="l2",
        quantization="float32",
        build_id="b1",
    )
    assert m.dimension == 8
    assert m.normalization == "l2"
    assert m.quantization == "float32"
    # frozen dataclass → hashable / immutable identity
    assert m == EmbedMeta(
        "minishlab/potion-retrieval-32M", "", 8, "l2", "float32", "b1"
    )
