#!/usr/bin/env python3
"""embedder.py — Pluggable embedding interface for the semantic layer.

Mirrors the LLM provider registry pattern (``providers/registry.py``): a
dimension-agnostic ``Embedder`` interface plus a small registry that selects a
default implementation. The default is **model2vec / potion-retrieval-32M** —
a *static* embedding whose inference dependency is just numpy (no torch, no
network at inference), ideal for a file-first, cross-platform install.

This module is part of the optional ``[semantic]`` extra. Importing it is always
safe: when the extra is not installed, ``is_semantic_available()`` returns
``False`` and ``get_embedder()`` returns ``None`` so callers fall back to the
existing lexical/keyword paths (LWM_013 invariant #3). Heavy imports
(``model2vec``, ``numpy``) are deferred to call sites, never at module import.

See: LWM_015 (embedder interface), ADR-0019 (default model + pluggable
interface). Static embeddings must never be the *sole* basis for auto-applying
entity merges or links (ADR-0021, enforced downstream in LWM_021).
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Sequence

# Numpy-only static default (ADR-0019). Overridable via LLM_WIKI_EMBEDDER.
DEFAULT_MODEL_ID = "minishlab/potion-retrieval-32M"


@dataclass(frozen=True)
class EmbedMeta:
    """Identity of an embedding space.

    Persisted alongside the vectors (LWM_014 / ADR-0018) and asserted by every
    vector reader; a mismatch forces a keyword fallback rather than a corrupt
    KNN result (LWM_013 invariant #5).
    """

    model_id: str
    revision: str
    dimension: int
    normalization: str  # "l2" | "none"
    quantization: str  # "float32" | "int8" | "bit"
    build_id: str = ""


class Embedder(ABC):
    """Dimension-agnostic embedding provider.

    Implementations declare ``model_id``/``revision``/``normalization``/
    ``quantization`` and expose ``dimension`` + ``embed()``. ``is_available()``
    reports whether the implementation's dependencies are importable, without
    importing them into the caller.
    """

    model_id: str = ""
    revision: str = ""
    normalization: str = "l2"
    quantization: str = "float32"

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """True iff this implementation's dependencies are importable."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Embedding dimension (may lazily load the model to discover it)."""

    @abstractmethod
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one vector per input text as plain Python floats."""

    def embed_meta(self, build_id: str = "") -> EmbedMeta:
        return EmbedMeta(
            model_id=self.model_id,
            revision=self.revision,
            dimension=self.dimension,
            normalization=self.normalization,
            quantization=self.quantization,
            build_id=build_id,
        )


class Model2VecEmbedder(Embedder):
    """Static, numpy-only default embedder (model2vec / potion-retrieval-32M)."""

    normalization = "l2"
    quantization = "float32"

    def __init__(self, model_id: str = DEFAULT_MODEL_ID) -> None:
        self.model_id = model_id
        self.revision = ""
        self._model = None
        self._dim: Optional[int] = None

    @classmethod
    def is_available(cls) -> bool:
        try:
            import model2vec  # noqa: F401
            import numpy  # noqa: F401
        except ImportError:
            return False
        return True

    def _load(self):
        if self._model is None:
            try:
                import numpy as np
                from model2vec import StaticModel

                # StaticModel.from_pretrained downloads from HuggingFace on
                # first use. A download failure (offline CI runner, HF outage)
                # must NOT crash the caller — the semantic layer degrades to
                # unavailable, exactly like the extra being absent (LWM_013
                # invariant #3: optional extras degrade gracefully).
                self._model = StaticModel.from_pretrained(self.model_id)
                probe = np.asarray(self._model.encode(["_"]))
                self._dim = int(probe.shape[-1])
            except Exception:
                self._model = None
                self._dim = None
        return self._model

    @property
    def dimension(self) -> int:
        if self._dim is None:
            self._load()
        return self._dim or 0

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        import numpy as np

        model = self._load()
        if model is None:
            # Model unavailable (download failed) — degrade to no vectors;
            # callers fall back to the keyword path byte-identically.
            return []
        vecs = np.asarray(model.encode(list(texts)), dtype=np.float32)
        if vecs.ndim == 1:
            vecs = vecs.reshape(1, -1)
        if self.normalization == "l2":
            norms = np.linalg.norm(vecs, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            vecs = vecs / norms
        return vecs.astype(np.float32).tolist()


# Registry. Optional precision-upgrade backends (bge-small, api) are added in
# later LWM_015 lanes; keeping the map small keeps the default path numpy-only.
EMBEDDER_MAP: dict[str, type[Embedder]] = {
    "model2vec": Model2VecEmbedder,
}


def detect_default_embedder() -> str:
    """Name of the default embedder backend (override: LLM_WIKI_EMBEDDER)."""
    return os.environ.get("LLM_WIKI_EMBEDDER", "model2vec")


def get_embedder(name: Optional[str] = None) -> Optional[Embedder]:
    """Return an embedder instance, or ``None`` when unavailable.

    Returning ``None`` (rather than raising) is the contract that lets callers
    degrade to the lexical/keyword path with no behavior change when the
    ``[semantic]`` extra is absent.
    """
    name = name or detect_default_embedder()
    cls = EMBEDDER_MAP.get(name)
    if cls is None or not cls.is_available():
        return None
    return cls()


def is_semantic_available() -> bool:
    """True iff at least one registered embedder's dependencies are importable."""
    return any(cls.is_available() for cls in EMBEDDER_MAP.values())
