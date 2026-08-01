"""Frontmatter parser golden tests.

Freezes the behavior of the canonical frontmatter parser so that
consolidation/refactoring does not silently change parsing results.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from llm_wiki.core.frontmatter import parse_frontmatter, FRONTMATTER_RE

SAMPLE_PAGES = [
    pytest.param(
        "---\ntitle: Test Page\ntype: concept\ncreated: 2026-01-01\nupdated: 2026-06-01\nsources: [src1, src2]\ntags: [tag1, tag2]\n---\n\n# Content here",
        {
            "title": "Test Page",
            "type": "concept",
            "created": "2026-01-01",
            "updated": "2026-06-01",
            "sources": ["src1", "src2"],
            "tags": ["tag1", "tag2"],
        },
        id="full-page",
    ),
    pytest.param(
        "---\ntitle: Minimal\n---\n\nSome content",
        {"title": "Minimal"},
        id="minimal",
    ),
    pytest.param(
        "No frontmatter at all\n\nJust content",
        None,
        id="no-frontmatter",
    ),
    pytest.param(
        "---\nbroken\n---\n\nContent",
        {},
        id="broken-frontmatter-no-colon",
    ),
    pytest.param(
        "---\n---\n\nEmpty frontmatter",
        None,
        id="empty-frontmatter",
    ),
    pytest.param(
        "---\ntitle: Page with colons: in value\ntype: reference\n---\n\nContent",
        {"title": "Page with colons: in value", "type": "reference"},
        id="colons-in-value",
    ),
    pytest.param(
        "---\ntitle: Leading and trailing  \n  \n---\n\nContent",
        {"title": "Leading and trailing"},
        id="whitespace-stripping",
    ),
    pytest.param(
        "---\ntitle: Multi\nconfidence: high\nstatus: active\nsources:\n  - src1\n  - src2\n---\n\nContent",
        {"title": "Multi", "confidence": "high", "status": "active", "sources": ""},
        id="list-values-current-behavior",
    ),
    pytest.param(
        "---\ntitle: Case\nConfidence: low\n---\n\nContent",
        {"title": "Case", "Confidence": "low"},
        id="key-case-preserved",
    ),
    pytest.param(
        '---\ntitle: "Quoted title"\n---\n\nContent',
        {"title": "Quoted title"},
        id="quoted-values",
    ),
]


class TestFrontmatterGolden:
    @pytest.mark.parametrize("text,expected", SAMPLE_PAGES)
    def test_parse_frontmatter(self, text, expected):
        result = parse_frontmatter(text)
        assert result == expected, (
            f"Expected {expected!r}, got {result!r}"
        )
