"""semantic — optional semantic layer (embeddings + vector search + linking).

Gated behind the ``[semantic]`` optional extra (model2vec, numpy, sqlite-vec).
Importing this package is always safe: with the extra absent,
``is_semantic_available()`` returns ``False`` and ``get_embedder()`` returns
``None``, so every caller falls back to the existing lexical/keyword path with
no behavior change (LWM_013 invariant #3, "additive / opt-in").

Boundary owner: LWM_013. Interface: LWM_015 (ADR-0019).
"""

from llm_wiki.semantic.embedder import (
    DEFAULT_MODEL_ID,
    EMBEDDER_MAP,
    EmbedMeta,
    Embedder,
    Model2VecEmbedder,
    detect_default_embedder,
    get_embedder,
    is_semantic_available,
)

__all__ = [
    "DEFAULT_MODEL_ID",
    "EMBEDDER_MAP",
    "EmbedMeta",
    "Embedder",
    "Model2VecEmbedder",
    "detect_default_embedder",
    "get_embedder",
    "is_semantic_available",
]
