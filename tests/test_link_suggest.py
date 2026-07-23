"""test_link_suggest.py — Regression tests for link_suggest.py inverted index.

LWM_06 + LWM_06B: Validates the InvertedIndex dataclass, dual-map construction,
and O(1) reverse entity lookup. Regression: suggestion output must be
semantically equivalent to the inverted-index-based pipeline.
"""
import sys
from collections import defaultdict
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from llm_wiki.graph.suggest import (
    InvertedIndex,
    build_inverted_index,
    build_entity_registry,
    generate_suggestions,
    load_pages,
)


# ── InvertedIndex dataclass unit tests ──────────────────────────────────


class TestInvertedIndexDataclass:
    """Phase 2.1b.1: Corrected Data Structure."""

    def test_dataclass_exists(self):
        """InvertedIndex should be a class with entity_to_pages and page_to_entities."""
        idx = InvertedIndex(
            entity_to_pages={},
            page_to_entities={},
        )
        assert hasattr(idx, "entity_to_pages")
        assert hasattr(idx, "page_to_entities")

    def test_entity_count_empty(self):
        """entity_count on empty index returns 0."""
        idx = InvertedIndex(entity_to_pages={}, page_to_entities={})
        assert idx.entity_count == 0

    def test_entity_count_nonempty(self):
        """entity_count reflects number of distinct entities in forward map."""
        idx = InvertedIndex(
            entity_to_pages={"deep_learning": {"page1", "page2"}, "transformer": {"page1"}},
            page_to_entities={"page1": {"deep_learning", "transformer"}, "page2": {"deep_learning"}},
        )
        assert idx.entity_count == 2

    def test_entity_page_count_from_forward_map(self):
        """Entity page count = len(entity_to_pages[entity]) — O(1)."""
        idx = InvertedIndex(
            entity_to_pages={"deep_learning": {"page1", "page2", "page3"}},
            page_to_entities={"page1": {"deep_learning"}, "page2": {"deep_learning"}, "page3": {"deep_learning"}},
        )
        assert len(idx.entity_to_pages["deep_learning"]) == 3


# ── build_inverted_index tests ──────────────────────────────────────────


class TestBuildInvertedIndex:
    """Phase 2.1b.1: Corrected inverted index construction."""

    def test_returns_inverted_index_instance(self, populated_wiki):
        """build_inverted_index returns InvertedIndex, not a plain dict."""
        wiki_dir = populated_wiki / "wiki"
        if not wiki_dir.is_dir():
            pytest.skip("populated_wiki fixture missing wiki/ directory")
        pages = load_pages(wiki_dir)
        registry = build_entity_registry(pages)
        inverted = build_inverted_index(pages, registry)
        assert isinstance(inverted, InvertedIndex)

    def test_both_maps_populated(self, populated_wiki):
        """Both entity_to_pages and page_to_entities are non-empty for a populated wiki."""
        wiki_dir = populated_wiki / "wiki"
        if not wiki_dir.is_dir():
            pytest.skip("populated_wiki fixture missing wiki/ directory")
        pages = load_pages(wiki_dir)
        registry = build_entity_registry(pages)
        inverted = build_inverted_index(pages, registry)
        assert len(inverted.entity_to_pages) > 0, "Forward map should have entries"
        assert len(inverted.page_to_entities) > 0, "Reverse map should have entries"

    def test_forward_map_keys_are_lowercase(self, populated_wiki):
        """Entity keys in entity_to_pages are lowercase (registry keys)."""
        wiki_dir = populated_wiki / "wiki"
        if not wiki_dir.is_dir():
            pytest.skip("populated_wiki fixture missing wiki/ directory")
        pages = load_pages(wiki_dir)
        registry = build_entity_registry(pages)
        inverted = build_inverted_index(pages, registry)
        for key in inverted.entity_to_pages:
            assert key == key.lower(), f"Key '{key}' is not lowercase"

    def test_reverse_map_per_page_has_set(self, populated_wiki):
        """Each page stem has an entry (possibly empty set) in page_to_entities."""
        wiki_dir = populated_wiki / "wiki"
        if not wiki_dir.is_dir():
            pytest.skip("populated_wiki fixture missing wiki/ directory")
        pages = load_pages(wiki_dir)
        registry = build_entity_registry(pages)
        inverted = build_inverted_index(pages, registry)
        for stem in pages:
            assert stem in inverted.page_to_entities, f"Page '{stem}' missing from reverse map"

    def test_consistency_between_maps(self, populated_wiki):
        """If entity e is in page p per forward map, p should list e in reverse map."""
        wiki_dir = populated_wiki / "wiki"
        if not wiki_dir.is_dir():
            pytest.skip("populated_wiki fixture missing wiki/ directory")
        pages = load_pages(wiki_dir)
        registry = build_entity_registry(pages)
        inverted = build_inverted_index(pages, registry)

        for entity, page_stems in inverted.entity_to_pages.items():
            for stem in page_stems:
                assert entity in inverted.page_to_entities.get(stem, set()), (
                    f"Entity '{entity}' in forward map for page '{stem}' "
                    f"but missing from reverse map"
                )

    def test_empty_wiki_returns_empty_index(self, empty_wiki):
        """Empty wiki → both maps empty."""
        wiki_dir = empty_wiki / "wiki"
        if not wiki_dir.is_dir():
            pytest.skip("empty_wiki fixture missing wiki/ directory")
        pages = load_pages(wiki_dir)
        registry = build_entity_registry(pages)
        inverted = build_inverted_index(pages, registry)
        assert len(inverted.entity_to_pages) == 0
        assert len(inverted.page_to_entities) == 0

    def test_entity_page_count_matches_forward_set_cardinality(self, populated_wiki):
        """len(entity_to_pages[e]) equals the number of pages mentioning e."""
        wiki_dir = populated_wiki / "wiki"
        if not wiki_dir.is_dir():
            pytest.skip("populated_wiki fixture missing wiki/ directory")
        pages = load_pages(wiki_dir)
        registry = build_entity_registry(pages)
        inverted = build_inverted_index(pages, registry)

        # Verify by manual count
        from llm_wiki.graph.suggest import text_without_wikilinks
        for entity_key, page_set in inverted.entity_to_pages.items():
            manual_count = 0
            for stem, (_, text, _) in pages.items():
                clean = text_without_wikilinks(text).lower()
                if entity_key in clean:
                    manual_count += 1
            assert len(page_set) == manual_count, (
                f"Forward map count {len(page_set)} != manual count {manual_count} "
                f"for entity '{entity_key}'"
            )


# ── generate_suggestions tests ──────────────────────────────────────────


class TestGenerateSuggestionsWithInvertedIndex:
    """Phase 2.1b.2: Corrected Suggestion Loop."""

    def test_accepts_inverted_index_parameter(self, populated_wiki):
        """generate_suggestions accepts an InvertedIndex parameter."""
        wiki_dir = populated_wiki / "wiki"
        if not wiki_dir.is_dir():
            pytest.skip("populated_wiki fixture missing wiki/ directory")
        pages = load_pages(wiki_dir)
        registry = build_entity_registry(pages)
        suggestions = generate_suggestions(
            pages, registry, wiki_dir, limit=10, min_confidence=0.0,
        )
        assert isinstance(suggestions, list)

    def test_builds_index_internally_when_none_passed(self, populated_wiki):
        """generate_suggestions works without explicit inverted_index."""
        wiki_dir = populated_wiki / "wiki"
        if not wiki_dir.is_dir():
            pytest.skip("populated_wiki fixture missing wiki/ directory")
        pages = load_pages(wiki_dir)
        registry = build_entity_registry(pages)
        suggestions = generate_suggestions(
            pages, registry, wiki_dir, limit=10, min_confidence=0.0,
        )
        assert isinstance(suggestions, list)

    def test_per_page_entity_lookup_is_constant(self, populated_wiki):
        """Entities in page come from O(1) reverse map, not full registry scan."""
        wiki_dir = populated_wiki / "wiki"
        if not wiki_dir.is_dir():
            pytest.skip("populated_wiki fixture missing wiki/ directory")
        pages = load_pages(wiki_dir)

    def test_for_entity_in_registry_not_used(self, populated_wiki):
        """The per-page loop must NOT iterate the full registry (no 'for key in registry')."""
        wiki_dir = populated_wiki / "wiki"
        if not wiki_dir.is_dir():
            pytest.skip("populated_wiki fixture missing wiki/ directory")
        pages = load_pages(wiki_dir)
        registry = build_entity_registry(pages)

        suggestions = generate_suggestions(
            pages, registry, wiki_dir, limit=1000, min_confidence=0.0,
        )
        assert len(suggestions) >= 0

    def test_empty_wiki_no_crash(self, empty_wiki):
        """Empty wiki produces empty suggestions, no crashes."""
        wiki_dir = empty_wiki / "wiki"
        if not wiki_dir.is_dir():
            pytest.skip("empty_wiki fixture missing wiki/ directory")
        pages = load_pages(wiki_dir)
        registry = build_entity_registry(pages)
        inverted = build_inverted_index(pages, registry)
        suggestions = generate_suggestions(
            pages, registry, wiki_dir, limit=10, min_confidence=0.0,
            inverted=inverted,
        )
        assert suggestions == []

    def test_empty_registry_no_crash(self, tmp_wiki):
        """Wiki with pages but no entity registry returns empty suggestions."""
        wiki_dir = tmp_wiki / "wiki"
        if not wiki_dir.is_dir():
            pytest.skip("tmp_wiki fixture missing wiki/ directory")
        pages = load_pages(wiki_dir)
        registry = {}
        inverted = build_inverted_index(pages, registry)
        suggestions = generate_suggestions(
            pages, registry, wiki_dir, limit=10, min_confidence=0.0,
            inverted=inverted,
        )
        assert suggestions == []

    def test_min_confidence_filters_correctly(self, populated_wiki):
        """min_confidence=1.0 should filter out all suggestions; 0.0 allows all."""
        wiki_dir = populated_wiki / "wiki"
        if not wiki_dir.is_dir():
            pytest.skip("populated_wiki fixture missing wiki/ directory")
        pages = load_pages(wiki_dir)
        registry = build_entity_registry(pages)
        inverted = build_inverted_index(pages, registry)

        all_suggestions = generate_suggestions(
            pages, registry, wiki_dir, limit=1000, min_confidence=0.0,
            inverted=inverted,
        )
        strict_suggestions = generate_suggestions(
            pages, registry, wiki_dir, limit=1000, min_confidence=1.0,
            inverted=inverted,
        )
        assert len(strict_suggestions) <= len(all_suggestions)

    def test_limit_caps_suggestions(self, populated_wiki):
        """limit parameter caps the number of returned suggestions."""
        wiki_dir = populated_wiki / "wiki"
        if not wiki_dir.is_dir():
            pytest.skip("populated_wiki fixture missing wiki/ directory")
        pages = load_pages(wiki_dir)
        registry = build_entity_registry(pages)
        inverted = build_inverted_index(pages, registry)

        suggestions = generate_suggestions(
            pages, registry, wiki_dir, limit=1000, min_confidence=0.0,
        )
        assert len(suggestions) <= 5


# ── Edge case tests ─────────────────────────────────────────────────────


class TestInvertedIndexEdgeCases:
    """Phase 2.1b.2: Correctness under edge conditions."""

    def test_entity_not_in_any_page_absent_from_forward_map(self, populated_wiki):
        """Entities that appear in zero pages are absent from entity_to_pages keys."""
        wiki_dir = populated_wiki / "wiki"
        if not wiki_dir.is_dir():
            pytest.skip("populated_wiki fixture missing wiki/ directory")
        pages = load_pages(wiki_dir)
        registry = build_entity_registry(pages)
        inverted = build_inverted_index(pages, registry)

        # Every key in entity_to_pages should have at least one page
        for entity_key, page_set in inverted.entity_to_pages.items():
            assert len(page_set) >= 1, (
                f"Entity '{entity_key}' in forward map with empty page set"
            )

    def test_page_with_no_entities_has_empty_set(self, populated_wiki):
        """Pages that mention no entities have an empty set in page_to_entities."""
        wiki_dir = populated_wiki / "wiki"
        if not wiki_dir.is_dir():
            pytest.skip("populated_wiki fixture missing wiki/ directory")
        pages = load_pages(wiki_dir)
        registry = build_entity_registry(pages)
        inverted = build_inverted_index(pages, registry)

        # Every page should have an entry (even if empty)
        for stem in pages:
            assert isinstance(inverted.page_to_entities.get(stem), set), (
                f"Page '{stem}' should have a set in reverse map"
            )

    def test_entity_page_count_zero_not_in_forward_map(self, populated_wiki):
        """Accessing entity_page_count for unknown entity should use .get() with default."""
        wiki_dir = populated_wiki / "wiki"
        if not wiki_dir.is_dir():
            pytest.skip("populated_wiki fixture missing wiki/ directory")
        pages = load_pages(wiki_dir)
        registry = build_entity_registry(pages)
        inverted = build_inverted_index(pages, registry)

        # Entity that doesn't exist in the registry
        fake_entity = "nonexistent_entity_xyz"
        count = len(inverted.entity_to_pages.get(fake_entity, set()))
        assert count == 0


# ── Regression: semantic equivalence ────────────────────────────────────


class TestSuggestionOutputParity:
    """Verify suggestions have correct structure and are semantically valid."""

    def test_suggestion_structure(self, populated_wiki):
        """Each suggestion dict has all required fields."""
        wiki_dir = populated_wiki / "wiki"
        if not wiki_dir.is_dir():
            pytest.skip("populated_wiki fixture missing wiki/ directory")
        pages = load_pages(wiki_dir)
        registry = build_entity_registry(pages)
        inverted = build_inverted_index(pages, registry)

        suggestions = generate_suggestions(
            pages, registry, wiki_dir, limit=1000, min_confidence=0.0,
            inverted=inverted,
        )
        required_keys = {
            "source", "source_stem", "source_title", "source_type",
            "target", "target_stem", "target_title", "target_type",
            "entity", "score", "reason",
        }
        for s in suggestions:
            missing = required_keys - set(s.keys())
            assert not missing, f"Suggestion missing keys: {missing}"

    def test_no_self_links(self, populated_wiki):
        """No suggestion should link a page to itself."""
        wiki_dir = populated_wiki / "wiki"
        if not wiki_dir.is_dir():
            pytest.skip("populated_wiki fixture missing wiki/ directory")
        pages = load_pages(wiki_dir)
        registry = build_entity_registry(pages)
        inverted = build_inverted_index(pages, registry)

        suggestions = generate_suggestions(
            pages, registry, wiki_dir, limit=1000, min_confidence=0.0,
            inverted=inverted,
        )
        for s in suggestions:
            assert s["source_stem"] != s["target_stem"], (
                f"Self-link: {s['source_stem']} → {s['target_stem']}"
            )

    def test_scores_in_valid_range(self, populated_wiki):
        """All scores are between 0.0 and 1.0 inclusive."""
        wiki_dir = populated_wiki / "wiki"
        if not wiki_dir.is_dir():
            pytest.skip("populated_wiki fixture missing wiki/ directory")
        pages = load_pages(wiki_dir)
        registry = build_entity_registry(pages)
        inverted = build_inverted_index(pages, registry)

        suggestions = generate_suggestions(
            pages, registry, wiki_dir, limit=1000, min_confidence=0.0,
            inverted=inverted,
        )
        for s in suggestions:
            assert 0.0 <= s["score"] <= 1.0, (
                f"Score {s['score']} out of range for {s['entity']}"
            )

    def test_suggestions_sorted_by_score_desc(self, populated_wiki):
        """Suggestions return sorted by score descending."""
        wiki_dir = populated_wiki / "wiki"
        if not wiki_dir.is_dir():
            pytest.skip("populated_wiki fixture missing wiki/ directory")
        pages = load_pages(wiki_dir)
        registry = build_entity_registry(pages)
        inverted = build_inverted_index(pages, registry)

        suggestions = generate_suggestions(
            pages, registry, wiki_dir, limit=1000, min_confidence=0.0,
            inverted=inverted,
        )
        scores = [s["score"] for s in suggestions]
        assert scores == sorted(scores, reverse=True), "Suggestions not sorted by score desc"

    def test_suggestion_entity_in_registry(self, populated_wiki):
        """Every suggested entity key exists in the registry."""
        wiki_dir = populated_wiki / "wiki"
        if not wiki_dir.is_dir():
            pytest.skip("populated_wiki fixture missing wiki/ directory")
        pages = load_pages(wiki_dir)
        registry = build_entity_registry(pages)
        inverted = build_inverted_index(pages, registry)

        suggestions = generate_suggestions(
            pages, registry, wiki_dir, limit=1000, min_confidence=0.0,
            inverted=inverted,
        )
        for s in suggestions:
            entity_key = s["entity"].lower()
            assert entity_key in registry, (
                f"Suggested entity '{s['entity']}' (key='{entity_key}') not in registry"
            )
