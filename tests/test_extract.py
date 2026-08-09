"""Tests for the pluggable entity extractor (LWM_026).

Covers import-safety without the [ner] extra, the regex default being
byte-identical to the current extract_entities, and get_extractor() always
degrading to the regex path.
"""

import pytest

from llm_wiki.graph.extract import (
    EntitySpan,
    GLiNERExtractor,
    RegexExtractor,
    detect_default_extractor,
    get_extractor,
    is_ner_available,
)
from llm_wiki.graph.suggest import extract_entities

SAMPLE = """---
title: Transformers
type: concept
---

## Attention Is All You Need

The **Transformer** architecture replaced recurrence with **self-attention**.
"""


def test_import_without_ner_is_safe():
    # Importing the module and probing availability must never raise, even with
    # no [ner] extra installed.
    assert isinstance(is_ner_available(), bool)
    assert RegexExtractor.is_available() is True


def test_get_extractor_defaults_to_regex():
    ex = get_extractor()
    # Base install: default is regex (unless the [ner] extra is present + selected).
    assert ex.name in ("regex", "gliner")
    assert detect_default_extractor() in ("regex", "gliner")


def test_unknown_backend_falls_back_to_regex():
    ex = get_extractor("does-not-exist")
    assert isinstance(ex, RegexExtractor)


def test_regex_matches_baseline():
    ex = RegexExtractor()
    surfaces = ex.extract_surfaces(SAMPLE)
    # Byte-identical to today's heuristic.
    assert surfaces == extract_entities(SAMPLE)
    spans = ex.extract(SAMPLE)
    assert all(isinstance(s, EntitySpan) for s in spans)
    assert all(s.label == "" for s in spans)  # regex path is untyped


def test_gliner_availability_probe_matches_import():
    # is_available() must reflect real importability without importing gliner
    # into the caller when it is absent.
    try:
        import gliner  # noqa: F401
        expected = True
    except ImportError:
        expected = False
    assert GLiNERExtractor.is_available() is expected


# ── AD-10: load/inference failures degrade, never raise ─────────────────────

def _inject_fake_gliner(monkeypatch, load_error=None, predict_error=None):
    """Install a fake `gliner` module so is_available() is True and the backend
    can be forced to fail at load or at inference time."""
    import sys
    import types

    if load_error is not None:
        class _GLiNER:
            @classmethod
            def from_pretrained(cls, model_id):
                raise load_error
        predict_raises = None
    else:
        class _Model:
            def predict_entities(self, text, wanted):
                if predict_error is not None:
                    raise predict_error
                return [
                    {"text": "Transformer", "label": "model",
                     "start": 0, "end": 11, "score": 0.99},
                ]

        class _GLiNER:
            @classmethod
            def from_pretrained(cls, model_id):
                return _Model()

    fake = types.ModuleType("gliner")
    fake.GLiNER = _GLiNER
    monkeypatch.setitem(sys.modules, "gliner", fake)


def test_gliner_load_failure_falls_back(monkeypatch, capsys):
    _inject_fake_gliner(monkeypatch, load_error=RuntimeError("model download failed"))
    assert GLiNERExtractor.is_available() is True
    ex = get_extractor("gliner")
    assert isinstance(ex, GLiNERExtractor)
    # extraction must degrade (empty spans) without raising
    assert ex.extract(SAMPLE) == []
    assert ex.extract_surfaces(SAMPLE) == []


def test_gliner_inference_failure_falls_back(monkeypatch):
    _inject_fake_gliner(
        monkeypatch, predict_error=RuntimeError("onnxruntime inference failed")
    )
    ex = get_extractor("gliner")
    assert isinstance(ex, GLiNERExtractor)
    # a failing predict_entities() degrades to [] instead of crashing
    assert ex.extract(SAMPLE) == []


def test_gliner_failure_logged_once(monkeypatch, capsys):
    _inject_fake_gliner(monkeypatch, load_error=RuntimeError("offline"))
    ex = get_extractor("gliner")
    for _ in range(3):
        assert ex.extract(SAMPLE) == []
    out, err = capsys.readouterr()
    # structured log (core/logging.py → stderr) fires exactly once per instance
    assert err.count("GLiNER") == 1


def test_no_download_base_path(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def blocking_import(name, *args, **kwargs):
        if name == "gliner" or name.startswith("gliner."):
            raise ImportError("No module named 'gliner' (base path must not import it)")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocking_import)
    monkeypatch.delenv("LLM_WIKI_NER", raising=False)
    # base path: no [ner] extra → get_extractor() is the regex default and the
    # blocked import proves GLiNER is never even imported (so no model download).
    ex = get_extractor()
    assert isinstance(ex, RegexExtractor)
    assert ex.extract_surfaces(SAMPLE) == extract_entities(SAMPLE)
    # a requested gliner backend also degrades to regex when [ner] is absent
    ex2 = get_extractor("gliner")
    assert isinstance(ex2, RegexExtractor)
    assert GLiNERExtractor.is_available() is False


# ── LWM_026 success path (real [ner] extra — CI `ner-verification` lane) ────

def test_gliner_typed_spans_success_path():
    """Real GLiNER over the [ner] extra returns typed EntitySpan instances.

    Deferred in B10 because no success-path test existed: skips locally (gliner
    absent) and runs for real in the CI `ner-verification` lane — a model
    download failure there fails the lane visibly. Asserts typed spans with
    label/text/start/end/score — the LWM_026 contract.
    """
    pytest.importorskip("gliner")
    text = ("Ashish Vaswani introduced the Transformer architecture in the "
            "paper Attention Is All You Need.")
    ex = get_extractor("gliner")
    assert isinstance(ex, GLiNERExtractor)
    spans = ex.extract(text, labels=["person", "model"])
    assert spans, "GLiNER should find at least one typed span in the sample"
    for s in spans:
        assert isinstance(s, EntitySpan)
        assert s.text and s.text in text
        assert s.label in ("person", "model")
        assert 0 <= s.start < s.end <= len(text)
        assert text[s.start:s.end] == s.text
        assert 0.0 <= s.score <= 1.0
    assert any(s.label == "person" for s in spans)  # Vaswani → person


def test_get_extractor_honors_ner_env():
    """LLM_WIKI_NER=gliner selects the GLiNER backend when [ner] is present."""
    pytest.importorskip("gliner")
    import os

    os.environ["LLM_WIKI_NER"] = "gliner"
    try:
        ex = get_extractor()
        assert isinstance(ex, GLiNERExtractor)
    finally:
        del os.environ["LLM_WIKI_NER"]
