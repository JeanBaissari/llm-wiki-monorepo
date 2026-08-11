#!/usr/bin/env python3
"""ner_onnx.py — Torch-free GLiNER ONNX inference path (LWM_037).

The ``[ner]`` extra's ``gliner`` package imports torch at package import time
(``gliner/__init__.py`` does ``from .model import GLiNER`` and ``gliner/model.py``
does ``import torch`` at module top — verified against the gliner 0.2.13 wheel
source), so the typed ``EntitySpan`` success path cannot run torch-free through
``import gliner``. This module is the torch-free twin: it runs an **exported
end-to-end ONNX artifact** directly via ``onnxruntime`` — never importing
``gliner`` or ``torch`` — so a dev machine needs only ``onnxruntime`` (+ its
``numpy`` transitive) plus the cached artifact, never a torch install.

Purity contract: importing this module is always safe. Module-top imports are
stdlib-only; ``onnxruntime`` / ``numpy`` are imported lazily inside
``is_available()`` / ``_load()`` and degrade to "unavailable" when absent. Base
install and ``[recommended]`` installs never import the ``[ner]`` stack.

Routing (see ``llm_wiki.graph.extract``): ``get_extractor("gliner")`` falls
through to this runner when (a) ``LLM_WIKI_GLINER_MODEL`` is set AND (b) torch is
NOT importable AND (c) a prepared ``model.onnx`` artifact is present at the
resolved model directory. A torch-present install always keeps the real gliner
path (the CI ``ner-verification`` lane behavior is unchanged) and uses
``LLM_WIKI_GLINER_MODEL`` only to point ``GLiNER.from_pretrained`` at a cached
model directory (no re-download).

Model-cache convention: ``~/.cache/llm-wiki/models/<pinned-key>/`` (user-global),
overridable per-run via the ``LLM_WIKI_GLINER_MODEL`` env var (a local
path/directory). The pinned key MUST match the model id the CI lane uses so CI
and local runs use identical weights: ``urchade/gliner_small-v2.1``.

ONNX artifact contract (documented; produced ONCE by a one-time export command
run under the full ``[ner]`` extra, where torch exists — see AGENTS.md §GLiNER
`[ner]` local path): ``<model-dir>/model.onnx``, an end-to-end graph that
encapsulates gliner's whole inference pipeline (WordsSplitter tokenization is
reproduced here; BERT subword tokenization, span bi-encoder forward, and span
decoding are inside the graph so local output parity is by construction).
Inputs (``int64`` unless noted): ``words``/``word_start``/``word_end``
(``[1, max_words]`` — whitespace-split words + their char offsets in the text),
``word_count`` (``[1]``), ``labels`` (string ``[1, max_labels]``), ``label_count``
(``[1]``). Outputs: ``entity_start``/``entity_end`` (``int64`` char offsets into
the input text), ``entity_label`` (string), ``entity_score`` (float32), and
``entity_count`` (``int64 [1]``). Without a prepared artifact the runner reports
unavailable and extraction falls back to the regex path byte-identically.

This module is the *local-path half* of LWM_037: the runner + routing + numpy
decode are implemented and tested here; the one-time ONNX export command is the
documented ``[ner]``-side follow-up (the artifact cannot be produced without a
torch run, and no ONNX artifact ships upstream — ``urchade/gliner_small-v2.1``
holds only ``pytorch_model.bin``). BKD-007 is therefore *partially* closed by
this lane (torch-free *inference*; torch required once for *preparation*).
"""

from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path
from typing import Optional, Sequence

# Mirrors gliner's WordsSplitter.WhitespaceTokenSplitter exactly, so word
# boundaries + char offsets match what the exporting pipeline saw.
_WHITESPACE_TOKEN_RE = re.compile(r"\w+(?:[-_]\w+)*|\S")

# Pinned model key — the same model id the CI `ner-verification` lane runs, so
# the cached artifact and CI weights are identical.
DEFAULT_MODEL_ID = "urchade/gliner_small-v2.1"
PINNED_MODEL_KEY = "gliner_small-v2.1"

# Default label set for zero-shot extraction (same as graph.extract).
DEFAULT_ENTITY_LABELS = ("person", "organization", "location", "concept", "model", "method")

# ONNX artifact input/output names (see module docstring for the contract).
_INPUT_NAMES = (
    "words",
    "word_start",
    "word_end",
    "word_count",
    "labels",
    "label_count",
)
_OUTPUT_NAMES = (
    "entity_start",
    "entity_end",
    "entity_label",
    "entity_score",
    "entity_count",
)

# Padding caps for the numpy encode step (a prepared artifact may bake stricter
# caps; these are the documented defaults).
MAX_WORDS = 512
MAX_LABELS = 64


def _model_cache_dir() -> Path:
    """Resolve the model directory: env override, else the user-global cache.

    ``LLM_WIKI_GLINER_MODEL`` points at a local path/directory (a cached HF model
    dir for the torch path, or a prepared ONNX artifact dir for this runner).
    Default convention: ``~/.cache/llm-wiki/models/<pinned-key>/``.
    """
    env = os.environ.get("LLM_WIKI_GLINER_MODEL")
    if env:
        return Path(env)
    return Path.home() / ".cache" / "llm-wiki" / "models" / PINNED_MODEL_KEY


class NEROnnxRunner:
    """Torch-free GLiNER backend: onnxruntime-direct over an exported artifact.

    Same interface shape as ``graph.extract.EntityExtractor`` (``name``,
    ``is_available``, ``extract``) but only importable/torch-free. It never
    imports ``gliner`` or ``torch``; all heavy imports are lazy and degrade to
    unavailable when the deps or the prepared artifact are absent.
    """

    name = "gliner-onnx"

    def __init__(self) -> None:
        self.model_dir = _model_cache_dir()
        self._session = None
        self._load_failed = False
        self._failure_logged = False

    @classmethod
    def is_available(cls) -> bool:
        """True iff the torch-free path can run for real.

        Requires: torch absent (torch-present installs keep the real gliner
        path), ``onnxruntime`` + ``numpy`` importable, and a prepared
        ``model.onnx`` artifact at the resolved model directory. Absent anything
        → ``False`` (extraction falls back to regex unchanged).
        """
        # find_spec probes without importing — the base path must never import
        # torch even to ask "is torch installed?".
        if importlib.util.find_spec("torch") is not None:
            return False
        if importlib.util.find_spec("onnxruntime") is None:
            return False
        if importlib.util.find_spec("numpy") is None:
            return False
        return cls._artifact_path().is_file()

    @classmethod
    def _artifact_path(cls) -> Path:
        return _model_cache_dir() / "model.onnx"

    def _log_failure_once(self, message: str) -> None:
        if not self._failure_logged:
            self._failure_logged = True
            from llm_wiki.core.logging import warn

            warn("extract", f"GLiNER-ONNX {message}", model_id=DEFAULT_MODEL_ID)

    def _load(self):
        """Lazily open the ONNX session (onnxruntime + numpy imported here)."""
        if self._session is None and not self._load_failed:
            try:
                import numpy as np  # noqa: F401
                import onnxruntime as ort

                artifact = self._artifact_path()
                if not artifact.is_file():
                    raise FileNotFoundError(f"ONNX artifact missing: {artifact}")
                self._session = ort.InferenceSession(str(artifact))
            except Exception:
                self._load_failed = True
                self._log_failure_once("model load failed; falling back to regex extraction")
                self._session = None
        return self._session

    def extract(self, text: str, labels: Optional[Sequence[str]] = None) -> list:
        """Run the exported ONNX pipeline and decode typed entity spans.

        Returns a list of ``EntitySpan`` (imported lazily from ``graph.extract``
        to avoid a module-import cycle); ``[]`` on any failure — the caller's
        per-call regex fallback handles the degrade, exactly like the gliner path.
        """
        session = self._load()
        if session is None:
            return []
        try:
            import numpy as np

            words = list(self._split_words(text))
            wanted = list(labels or DEFAULT_ENTITY_LABELS)
            feeds = self._encode(np, words, wanted)
            outs = session.run(list(_OUTPUT_NAMES), feeds)
            return self._decode(text, outs)
        except Exception:
            self._log_failure_once(
                "inference failed; returning empty span set (regex fallback)"
            )
            return []

    @staticmethod
    def _split_words(text: str) -> list[tuple[str, int, int]]:
        """Whitespace tokenization mirroring gliner (word, start, end) triples."""
        return [(m.group(), m.start(), m.end()) for m in _WHITESPACE_TOKEN_RE.finditer(text)]

    def _encode(self, np, words, labels):
        """Pack words + labels into the ONNX artifact's numpy feed dict."""
        max_words = min(len(words), MAX_WORDS)
        max_labels = min(len(labels), MAX_LABELS)

        pad_words = max_words or 1
        word_arrays = words[:max_words]
        start_arrays = [w[1] for w in word_arrays]
        end_arrays = [w[2] for w in word_arrays]

        feeds = {
            "words": np.asarray(
                [list(w for w, _, _ in word_arrays) + [""] * (pad_words - len(word_arrays))],
                dtype=np.str_,
            ),
            "word_start": np.asarray(
                [start_arrays + [0] * (pad_words - len(start_arrays))], dtype=np.int64
            ),
            "word_end": np.asarray(
                [end_arrays + [0] * (pad_words - len(end_arrays))], dtype=np.int64
            ),
            "word_count": np.asarray([len(word_arrays)], dtype=np.int64),
            "labels": np.asarray(
                [labels[:max_labels] + [""] * (max_labels - len(labels[:max_labels]))],
                dtype=np.str_,
            ),
            "label_count": np.asarray([max_labels], dtype=np.int64),
        }
        return feeds

    def _decode(self, text: str, outs) -> list:
        """Decode the artifact's char-offset rows into typed ``EntitySpan``."""
        from llm_wiki.graph.extract import EntitySpan

        count = int(outs["entity_count"][0])
        spans = []
        for i in range(count):
            start = int(outs["entity_start"][i])
            end = int(outs["entity_end"][i])
            spans.append(
                EntitySpan(
                    text=text[start:end],
                    label=str(outs["entity_label"][i]),
                    start=start,
                    end=end,
                    score=float(outs["entity_score"][i]),
                )
            )
        return spans


def is_onnx_runner_available() -> bool:
    """Convenience probe (mirrors ``is_ner_available``)."""
    return NEROnnxRunner.is_available()
