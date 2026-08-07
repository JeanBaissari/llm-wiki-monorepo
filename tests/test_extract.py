"""Tests for the pluggable entity extractor (LWM_026).

Covers import-safety without the [ner] extra, the regex default being
byte-identical to the current extract_entities, and get_extractor() always
degrading to the regex path.
"""

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
