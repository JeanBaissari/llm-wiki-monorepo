"""conftest.py — Shared fixtures for llm-wiki-monorepo test suite.

Fixtures:
    tmp_wiki          — Scaffold a fresh wiki in a temp directory
    mock_llm_success  — Mock call_llm() with controlled Stage 1 + Stage 2 responses
    mock_llm_chunked  — Mock call_llm() for multi-chunk sources
    mock_llm_failure  — Mock call_llm() that returns None (simulates LLM failure)
    populated_wiki    — Copy the populated fixture wiki to a temp directory
    stale_wiki        — Copy the stale fixture wiki to a temp directory
    minimal_wiki      — Copy the minimal fixture wiki to a temp directory
    empty_wiki        — Copy the empty fixture wiki to a temp directory
"""
import os
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

# Ensure skill/scripts is on sys.path for all tests
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skill" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# ── Schema version check ─────────────────────────────────────────────────

def _read_schema_version(wiki_root: Path) -> str | None:
    """Read the .schema_version marker from a fixture wiki."""
    vf = wiki_root / ".schema_version"
    if vf.exists():
        return vf.read_text(encoding="utf-8").strip()
    return None


def _compute_current_schema_version() -> str:
    """Derive schema version from SHA256 of base-schema.md."""
    schema_file = REPO_ROOT / "templates" / "_shared" / "base-schema.md"
    if schema_file.exists():
        return hashlib.sha256(schema_file.read_bytes()).hexdigest()[:8]
    return "00000000"


def _check_fixture_fresh(fixture_path: Path, fixture_name: str) -> None:
    """Check that a fixture's schema version matches current.
    
    Issues a pytest warning if stale, but doesn't skip — this is best-effort.
    The CI validate-fixtures job is the authoritative check.
    """
    stored = _read_schema_version(fixture_path)
    current = _compute_current_schema_version()
    if stored and stored != current:
        import warnings
        warnings.warn(
            f"Fixture '{fixture_name}' is stale (schema version {stored} != current {current}). "
            f"Run: python3 skill/scripts/regenerate_fixtures.py"
        )


def _run_scaffold(wiki_root: Path, name: str = "Test Wiki", template: str = "codebase") -> None:
    """Run scaffold.py to create a fresh wiki."""
    cmd = [
        sys.executable, str(SCRIPTS_DIR / "scaffold.py"),
        str(wiki_root), name,
        "--template", template,
        "--force",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"Scaffold failed: {result.stderr[:500]}")


# ── Wiki fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def tmp_wiki(tmp_path: Path) -> Path:
    """Scaffold a fresh wiki in a temp directory. Returns the wiki root path."""
    wiki_root = tmp_path / "test-wiki"
    _run_scaffold(wiki_root)
    return wiki_root


@pytest.fixture
def populated_wiki(tmp_path: Path) -> Path:
    """Copy the populated fixture wiki to a temp directory."""
    fixture = FIXTURES_DIR / "wikis" / "populated"
    _check_fixture_fresh(fixture, "populated")
    dest = tmp_path / "wiki"
    if fixture.exists():
        shutil.copytree(fixture, dest)
    return dest


@pytest.fixture
def stale_wiki(tmp_path: Path) -> Path:
    """Copy the stale fixture wiki to a temp directory."""
    fixture = FIXTURES_DIR / "wikis" / "stale"
    _check_fixture_fresh(fixture, "stale")
    dest = tmp_path / "wiki"
    if fixture.exists():
        shutil.copytree(fixture, dest)
    return dest


@pytest.fixture
def minimal_wiki(tmp_path: Path) -> Path:
    """Copy the minimal fixture wiki to a temp directory."""
    fixture = FIXTURES_DIR / "wikis" / "minimal"
    _check_fixture_fresh(fixture, "minimal")
    dest = tmp_path / "wiki"
    if fixture.exists():
        shutil.copytree(fixture, dest)
    return dest


@pytest.fixture
def empty_wiki(tmp_path: Path) -> Path:
    """Copy the empty fixture wiki to a temp directory."""
    fixture = FIXTURES_DIR / "wikis" / "empty"
    _check_fixture_fresh(fixture, "empty")
    dest = tmp_path / "wiki"
    if fixture.exists():
        shutil.copytree(fixture, dest)
    return dest


# ── Mock LLM response fixtures ────────────────────────────────────────────

@pytest.fixture
def mock_llm_success(monkeypatch):
    """Mock call_llm to return a controlled Stage 1 + Stage 2 response.

    Injects into all modules that import call_llm from ingest.py.
    """
    def _mock(system: str, user: str, provider: str = "default",
              total_timeout: int | None = None) -> str | None:
        if "Stage 1" in system or "analysis" in system.lower():
            return f"""## Entity Extraction
- TestEntity: A test entity for unit tests
- MockConcept: A mock concept for integration tests

## Concept Extraction
- MockPattern: A pattern used in testing

## Key Claims
This is a mock analysis for testing purposes.

## Relationships
- TestEntity relates to MockConcept"""
        # Stage 2 — generate FILE and REVIEW blocks
        return """---FILE: wiki/concepts/mock_concept.md
---
title: Mock Concept
type: concept
created: 2026-01-15
updated: 2026-01-15
sources: [test-source]
tags: [test, mock]
confidence: high
---

# Mock Concept

## Overview
A mock concept for integration testing.

## Links
- [[Test Entity]] is related.
- [[Mock Pattern]] is another concept.
---FILE: wiki/entities/test_entity.md
---
title: Test Entity
type: entity
created: 2026-01-15
updated: 2026-01-15
sources: [test-source]
tags: [test]
confidence: medium
---

# Test Entity

A test entity generated by mock LLM.
---REVIEW: missing-page
---
target: wiki/entities/missing_entity.md
title: Missing Entity
description: A review to verify missing page detection works.

---REVIEW: suggestion
---
target: wiki/concepts/mock_concept.md
title: Add Examples
description: Consider adding examples to this concept page.
"""

    monkeypatch.setattr("ingest.call_llm", _mock)
    # Also patch in the module namespace where it's used
    import ingest
    monkeypatch.setattr(ingest, "call_llm", _mock)
    return _mock


@pytest.fixture
def mock_llm_chunked(monkeypatch):
    """Mock call_llm that simulates multi-chunk analysis + consolidation."""
    chunk_count = [0]
    analyses = []

    def _mock(system: str, user: str, provider: str = "default",
              total_timeout: int | None = None) -> str | None:
        if "Stage 1" in system:
            if "Consolidate" in system:
                return "Consolidated analysis of " + " | ".join(analyses)
            chunk_count[0] += 1
            analysis = f"Chunk {chunk_count[0]} analysis content"
            analyses.append(analysis)
            return analysis
        # Stage 2
        return """---FILE: wiki/concepts/chunked_result.md
---
title: Chunked Result
type: concept
created: 2026-01-15
updated: 2026-01-15
sources: [test-source]
tags: [chunked]
---

# Chunked Result

Generated from a multi-chunk source document.
"""

    monkeypatch.setattr("ingest.call_llm", _mock)
    import ingest
    monkeypatch.setattr(ingest, "call_llm", _mock)
    return _mock


@pytest.fixture
def mock_llm_failure(monkeypatch):
    """Mock call_llm that always returns None (simulates LLM failure)."""
    def _mock(system: str, user: str, provider: str = "default",
              total_timeout: int | None = None) -> None:
        return None

    monkeypatch.setattr("ingest.call_llm", _mock)
    import ingest
    monkeypatch.setattr(ingest, "call_llm", _mock)
    return _mock


@pytest.fixture
def mock_llm_malformed(monkeypatch):
    """Mock call_llm that returns malformed FILE blocks."""
    def _mock(system: str, user: str, provider: str = "default",
              total_timeout: int | None = None) -> str | None:
        if "Stage 1" in system or "analysis" in system.lower():
            return "Analysis: test analysis content"
        return """---FILE: wiki/incomplete/no_frontmatter.md
---

# No Frontmatter

This FILE block has no useful frontmatter.

---FILE: wiki/concepts/valid_page.md
---
title: Valid Page
type: concept
created: 2026-01-15
updated: 2026-01-15
sources: [test-source]
tags: [valid]
---

# Valid Page

This page has proper frontmatter.

---BROKEN_BLOCK: not-a-valid-type
---
this should be skipped
"""

    monkeypatch.setattr("ingest.call_llm", _mock)
    import ingest
    monkeypatch.setattr(ingest, "call_llm", _mock)
    return _mock


# ── Source file fixtures ──────────────────────────────────────────────────

@pytest.fixture
def short_source() -> str:
    """A source document under CHUNK_SIZE (55,000 chars)."""
    return """# Short Source Document

## Introduction
This is a short test document used for single-chunk ingest testing.
It contains various entities, concepts, and relationships.

## Key Entities
- **Python**: A programming language widely used in data science.
- **PyTorch**: A deep learning framework developed by Meta.
- **TensorFlow**: A deep learning framework developed by Google.

## Concepts
- **Transfer Learning**: Using a pre-trained model on a new task.
- **Fine-Tuning**: Adjusting model weights for a specific dataset.

## Relationships
Python is the primary language for both PyTorch and TensorFlow.
Transfer learning often involves fine-tuning pre-trained models.
"""


@pytest.fixture
def long_source() -> str:
    """A source document exceeding CHUNK_SIZE (55,000 chars) for multi-chunk testing.

    Generates ~60,000 characters of Lorem Ipsum-style content.
    """
    paragraph = (
        "Deep learning architectures have evolved significantly over the past decade. "
        "Convolutional neural networks (CNNs) revolutionized computer vision by introducing "
        "hierarchical feature learning through stacked convolutional layers with shared weights. "
        "The key innovation was that lower layers learn to detect edges and textures, while "
        "higher layers combine these into complex object representations. "
    )
    # Generate enough paragraphs to exceed CHUNK_SIZE
    content = "# Long Source Document\n\n"
    content += paragraph * 150  # ~60K chars
    content += "\n\n## Final Section\nThis is the end of the long document."
    return content


@pytest.fixture
def malformed_source() -> str:
    """A source document with edge cases for testing malformed handling."""
    return """---
invalid_frontmatter: true
no_closing_delimiter:

# Malformed Source Document

This document has various edge cases.

## Broken Wikilinks
- [[Only opening bracket
- ]]Only closing bracket
- [[]] Empty link
- [[valid link]]

## Empty Sections
### 

## Duplicate Content
This paragraph appears twice.

This paragraph appears twice.

## Special Characters
Unicode: 😀 🚀 ñ é ç
Math: f(x) = ∑ᵢ₌₁ⁿ xᵢ²
"""


@pytest.fixture
def source_with_wikilinks() -> str:
    """A source with wikilinks in the body for testing wikilink extraction."""
    return """# Source with Wikilinks

## Overview
This document contains [[Target Page]] and [[Another Concept]] as inline wikilinks.

## Details
See also [[Deep Link|with alias]] and [[path/to/page]].
"""
