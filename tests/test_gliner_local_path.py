"""Tests for the torch-free local GLiNER path (LWM_037 / BKD-007).

Mirrors the CI ``ner-verification`` lane's success-path test
(``tests/test_extract.py::test_gliner_typed_spans_success_path``): the SAME
fixture text and the SAME typed-``EntitySpan`` assertions, but driven through the
torch-free ONNX runner (``semantic/ner_onnx.py``) instead of ``import gliner``.

Skip-gating is unchanged from the CI lane's contract: absent model/runner →
skip, never fail. On the base install no ONNX artifact can exist yet (the one-time
export needs a torch run under the full ``[ner]`` extra), so
``test_local_onnx_success_path_typed_spans`` skips here; the non-gated unit test
below proves the torch-free encode/decode path produces typed ``EntitySpan``
output with a fake ONNX session and no gliner/torch import.
"""

import os
import sys

import pytest

from llm_wiki.graph.extract import EntitySpan, get_extractor
from llm_wiki.graph.suggest import extract_entities
from llm_wiki.semantic.ner_onnx import NEROnnxRunner, is_onnx_runner_available

# The exact fixture the CI `ner-verification` lane runs (test_gliner_typed_spans_success_path).
CI_FIXTURE_TEXT = (
    "Ashish Vaswani introduced the Transformer architecture in the "
    "paper Attention Is All You Need."
)
CI_FIXTURE_LABELS = ["person", "model"]

ONNX_RUNNER_AVAILABLE = NEROnnxRunner.is_available()


def test_onnx_runner_unavailable_on_base_install():
    # No torch, no onnxruntime, no prepared artifact → the runner reports
    # unavailable (bool, never raises) and get_extractor degrades to regex.
    assert isinstance(is_onnx_runner_available(), bool)
    ex = get_extractor("gliner-onnx")
    if not ONNX_RUNNER_AVAILABLE:
        assert not is_onnx_runner_available()
        assert ex.name == "regex"
        # regex fallback is byte-identical on the base path
        assert ex.extract_surfaces(CI_FIXTURE_TEXT) == extract_entities(CI_FIXTURE_TEXT)


def test_onnx_runner_honors_llm_wiki_nier_env(tmp_path, monkeypatch):
    # Explicit backend selection surface (same get_extractor / LLM_WIKI_NER
    # surface as gliner): with the env set but no artifact, still regex.
    monkeypatch.setenv("LLM_WIKI_NER", "gliner-onnx")
    ex = get_extractor()
    if ONNX_RUNNER_AVAILABLE:
        assert ex.name == "gliner-onnx"
    else:
        assert ex.name == "regex"
    monkeypatch.delenv("LLM_WIKI_NER", raising=False)


def test_onnx_runner_respects_model_env_override(tmp_path, monkeypatch):
    # LLM_WIKI_GLINER_MODEL pointing at a dir WITHOUT an artifact → unavailable.
    d = tmp_path / "models" / "gliner_small-v2.1"
    d.mkdir(parents=True)
    monkeypatch.setenv("LLM_WIKI_GLINER_MODEL", str(d))
    assert NEROnnxRunner.is_available() is False
    ex = get_extractor("gliner")
    assert ex.name == "regex"  # torch absent + no artifact → regex, never raise


class FakeSession:
    """Stand-in for an onnxruntime InferenceSession over the prepared artifact."""

    def __init__(self, outputs):
        self._outputs = outputs
        self.last_feed = None

    def run(self, output_names, feed):
        self.last_feed = feed
        return self._outputs


def test_onnx_runner_decode_is_torch_free_typed_spans():
    """The numpy encode/decode path produces typed EntitySpan without importing
    gliner or torch (proven by sys.modules inspection after the run)."""
    pytest.importorskip("numpy")  # runner needs numpy; absent on base install → skip, never fail
    text = CI_FIXTURE_TEXT
    # Char offsets of "Ashish Vaswani" and "Transformer" (computed, not hardcoded).
    vaswani_start = text.find("Ashish Vaswani")
    vaswani_end = vaswani_start + len("Ashish Vaswani")
    trans_start = text.find("Transformer")
    trans_end = trans_start + len("Transformer")
    assert text[vaswani_start:vaswani_end] == "Ashish Vaswani"
    assert text[trans_start:trans_end] == "Transformer"
    fake = FakeSession(
        {
            "entity_start": [vaswani_start, trans_start],
            "entity_end": [vaswani_end, trans_end],
            "entity_label": ["person", "model"],
            "entity_score": [0.99, 0.87],
            "entity_count": [2],
        }
    )
    runner = NEROnnxRunner()
    runner._session = fake  # bypass the real (artifact) session load

    spans = runner.extract(text, labels=CI_FIXTURE_LABELS)

    assert len(spans) == 2
    for s in spans:
        assert isinstance(s, EntitySpan)
        assert s.text and s.text in text
        assert s.label in ("person", "model")
        assert 0 <= s.start < s.end <= len(text)
        assert text[s.start:s.end] == s.text
        assert 0.0 <= s.score <= 1.0
    assert spans[0].label == "person"  # Vaswani → person (mirrors CI assertion)
    assert any(s.label == "model" for s in spans)

    # torch-free contract: the runner's own decode must not import the stack.
    assert "gliner" not in sys.modules
    assert "torch" not in sys.modules

    # numpy encode fed the artifact contract exactly (word count via the
    # gliner-mirroring WordsSplitter regex, which splits "Need." → "Need" + ".").
    assert fake.last_feed is not None
    assert fake.last_feed["word_count"][0] == len(NEROnnxRunner._split_words(text))
    assert fake.last_feed["label_count"][0] == len(CI_FIXTURE_LABELS)
    assert fake.last_feed["word_start"][0][0] == vaswani_start
    assert fake.last_feed["word_end"][0][0] == vaswani_start + len("Ashish")


def test_onnx_runner_extract_fails_closed():
    # A broken session must degrade to [] (never raise) — mirrors the gliner
    # backend's fail-closed contract.
    class BrokenSession:
        def run(self, output_names, feed):
            raise RuntimeError("inference failed")

    runner = NEROnnxRunner()
    runner._session = BrokenSession()
    assert runner.extract(CI_FIXTURE_TEXT, labels=CI_FIXTURE_LABELS) == []


# ── LWM_037 local success path (same test + fixture as the CI lane) ─────────

@pytest.mark.skipif(
    not ONNX_RUNNER_AVAILABLE,
    reason="torch-free GLiNER requires a prepared ONNX artifact + onnxruntime (LWM_037)",
)
def test_local_onnx_success_path_typed_spans():
    """Runs the EXACT CI success-path fixture through the torch-free runner.

    Mirrors ``tests/test_extract.py::test_gliner_typed_spans_success_path``
    (same text, same labels, same typed-EntitySpan assertions). Runs only when
    the cached ONNX artifact + onnxruntime are present on a torch-free machine;
    skips otherwise (BKD-007 local-gap contract: absent → skip, never fail).
    """
    ex = get_extractor("gliner")
    assert ex.name == "gliner-onnx", "LLM_WIKI_GLINER_MODEL + no torch must route to the ONNX runner"
    spans = ex.extract(CI_FIXTURE_TEXT, labels=CI_FIXTURE_LABELS)
    assert spans, "the torch-free runner should find at least one typed span"
    for s in spans:
        assert isinstance(s, EntitySpan)
        assert s.text and s.text in CI_FIXTURE_TEXT
        assert s.label in ("person", "model")
        assert 0 <= s.start < s.end <= len(CI_FIXTURE_TEXT)
        assert CI_FIXTURE_TEXT[s.start:s.end] == s.text
        assert 0.0 <= s.score <= 1.0
    assert any(s.label == "person" for s in spans)  # Vaswani → person
    assert "gliner" not in sys.modules and "torch" not in sys.modules
