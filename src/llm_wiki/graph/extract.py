#!/usr/bin/env python3
"""extract.py — Pluggable entity extractor for the graph/link layer (LWM_026).

Mirrors ``semantic/embedder.py`` 1:1: an ``EntityExtractor`` ABC with a
class-level ``is_available()`` probe, a lazy ``_load()``, a small registry, and
``get_extractor()`` that returns the always-available ``RegexExtractor`` default
when the requested backend's deps are absent — so a caller never has to know
whether the optional ``[ner]`` extra is installed.

Importing this module is always safe: the base path is stdlib + the existing
``re`` heuristic (``RegexExtractor`` delegates to ``suggest.extract_entities`` so
the base graph/link output is byte-identical). The GLiNER backend
(``gliner`` + ``onnxruntime``, Apache-2.0, CPU/ONNX/INT8) is gated behind
``[ner]`` and its heavy imports + model download are deferred to the first
``extract()`` call — never at module import, never on the base path.

GLiNER output is *advisory* to LWM_025: a cleaner, typed candidate set still
subject to the two-signal auto-merge rule. Zero-shot extraction is never the sole
basis for a merge (ADR-0021 / ADR-0024).

LWM_037: ``LLM_WIKI_GLINER_MODEL`` points the gliner backend at a cached model
directory (no re-download); when that env is set and torch is NOT importable, the
``gliner`` / ``gliner-onnx`` backends route through the torch-free ONNX runner
(``semantic/ner_onnx.py``) instead — base installs keep the regex path.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Sequence

from llm_wiki.core.logging import warn

# Default entity types for zero-shot extraction; operator-overridable later
# (LWM_026 open question — per-template type lists).
DEFAULT_ENTITY_LABELS = ("person", "organization", "location", "concept", "model", "method")

# Pinned GLiNER model id. Overridable via LLM_WIKI_GLINER_MODEL (a cached model
# directory) so local runs and CI use identical weights without re-downloading.
DEFAULT_GLINER_MODEL_ID = "urchade/gliner_small-v2.1"


@dataclass(frozen=True)
class EntitySpan:
    """A typed entity mention. ``label``/``start``/``end`` are best-effort:

    the regex path has no span positions or types, so it emits ``label=""`` and
    ``start=end=-1``; ``score`` defaults to ``1.0`` for the deterministic path.
    """

    text: str
    label: str = ""
    start: int = -1
    end: int = -1
    score: float = 1.0


class EntityExtractor(ABC):
    """Pluggable entity extractor.

    Implementations declare ``name`` and expose ``extract()``. ``is_available()``
    reports whether the implementation's dependencies are importable, without
    importing them into the caller.
    """

    name: str = ""

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """True iff this implementation's dependencies are importable."""

    @abstractmethod
    def extract(self, text: str, labels: Optional[Sequence[str]] = None) -> list[EntitySpan]:
        """Return typed entity spans for one page's markdown text."""

    def extract_surfaces(self, text: str) -> list[str]:
        """Convenience: just the surface strings (what LWM_025 blocking consumes)."""
        return [s.text for s in self.extract(text)]


class RegexExtractor(EntityExtractor):
    """Always-available default. Delegates to ``suggest.extract_entities`` so the

    base graph/link candidate set is byte-identical to v0.4.0 (untyped spans).
    """

    name = "regex"

    @classmethod
    def is_available(cls) -> bool:
        return True

    def extract(self, text: str, labels: Optional[Sequence[str]] = None) -> list[EntitySpan]:
        from llm_wiki.graph.suggest import extract_entities

        # Untyped, position-less: preserves today's behavior exactly.
        return [EntitySpan(text=s) for s in extract_entities(text)]


class GLiNERExtractor(EntityExtractor):
    """Optional zero-shot NER backend (``[ner]`` extra: gliner + onnxruntime).

    Heavy imports and the model download are deferred to the first ``extract()``
    (mirroring ``Model2VecEmbedder._load``). GLiNERExtractor methods never
    raise: a load failure marks this instance unavailable and ``extract()``
    returns an empty span set (the caller's per-call ``RegexExtractor`` fallback
    via ``get_extractor``/``entities``); an inference failure returns ``[]``
    too. Each failure is logged once per instance (LWM_026 error handling).
    """

    name = "gliner"

    def __init__(self, model_id: Optional[str] = None) -> None:
        # LLM_WIKI_GLINER_MODEL: point GLiNER.from_pretrained at a cached model
        # directory (LWM_037 model-cache convention) so a torch-present local
        # install avoids re-downloading the 582 MB checkpoint.
        self.model_id = model_id or os.environ.get("LLM_WIKI_GLINER_MODEL") or DEFAULT_GLINER_MODEL_ID
        self._model = None
        self._load_failed = False
        self._failure_logged = False

    @classmethod
    def is_available(cls) -> bool:
        try:
            import gliner  # noqa: F401
        except ImportError:
            return False
        return True

    def _log_failure_once(self, message: str) -> None:
        if not self._failure_logged:
            self._failure_logged = True
            warn("extract", f"GLiNER {message}", model_id=self.model_id)

    def _load(self):
        if self._model is None and not self._load_failed:
            try:
                from gliner import GLiNER

                self._model = GLiNER.from_pretrained(self.model_id)
            except Exception:
                self._load_failed = True
                self._log_failure_once(
                    "model load failed; falling back to regex extraction"
                )
                self._model = None
        return self._model

    def extract(self, text: str, labels: Optional[Sequence[str]] = None) -> list[EntitySpan]:
        model = self._load()
        if model is None:
            return []
        try:
            wanted = list(labels or DEFAULT_ENTITY_LABELS)
            raw = model.predict_entities(text, wanted)
            return [
                EntitySpan(
                    text=e["text"],
                    label=e.get("label", ""),
                    start=int(e.get("start", -1)),
                    end=int(e.get("end", -1)),
                    score=float(e.get("score", 1.0)),
                )
                for e in raw
            ]
        except Exception:
            self._log_failure_once(
                "inference failed; returning empty span set (regex fallback)"
            )
            return []


# Registry — keep the default path stdlib-only. GLiNER is opt-in via LLM_WIKI_NER.
EXTRACTOR_MAP: dict[str, type[EntityExtractor]] = {
    "regex": RegexExtractor,
    "gliner": GLiNERExtractor,
}


def detect_default_extractor() -> str:
    """Name of the default extractor backend (override: LLM_WIKI_NER)."""
    return os.environ.get("LLM_WIKI_NER", "regex")


def _onnx_runner() -> Optional[EntityExtractor]:
    """Torch-free GLiNER twin (LWM_037): onnxruntime-direct, never gliner/torch.

    Imported lazily so the base path's import surface stays minimal. Returns
    ``None`` when the runner's deps or a prepared ONNX artifact are absent —
    the caller then degrades to the regex path byte-identically.
    """
    from llm_wiki.semantic.ner_onnx import NEROnnxRunner

    if not NEROnnxRunner.is_available():
        return None
    return NEROnnxRunner()


def get_extractor(name: Optional[str] = None) -> EntityExtractor:
    """Return an extractor instance, always falling back to ``RegexExtractor``.

    Unlike ``get_embedder`` (which returns ``None`` when unavailable), extraction
    always has a working default, so this never returns ``None``: an unknown
    backend or an absent ``[ner]`` extra degrades silently to the regex path.

    LWM_037 routing: when ``LLM_WIKI_GLINER_MODEL`` is set and torch is NOT
    importable (base install + onnxruntime), the ``gliner`` backend — and the
    explicit ``gliner-onnx`` backend — route through the torch-free ONNX runner.
    A torch-present install (the CI ``ner-verification`` lane) keeps the real
    ``import gliner`` path untouched.
    """
    name = name or detect_default_extractor()
    if name == "gliner-onnx":
        runner = _onnx_runner()
        if runner is not None:
            return runner
        return RegexExtractor()
    cls = EXTRACTOR_MAP.get(name)
    if cls is None or not cls.is_available():
        if name == "gliner":
            runner = _onnx_runner()
            if runner is not None:
                return runner
        return RegexExtractor()
    return cls()


def is_ner_available() -> bool:
    """True iff the optional GLiNER backend's dependencies are importable."""
    return GLiNERExtractor.is_available()
