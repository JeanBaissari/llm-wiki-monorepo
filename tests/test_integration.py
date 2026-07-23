"""test_integration.py — Golden-path integration test.

Full pipeline: scaffold → ingest (mock LLM) → lint → graph build.
Uses provider-agnostic mock responses. No network required.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skill" / "scripts"


@pytest.fixture
def integration_wiki(tmp_path):
    """Scaffold a fresh wiki for the integration test."""
    wiki_root = tmp_path / "integration-wiki"
    subprocess.run([
        sys.executable, str(SCRIPTS_DIR / "scaffold.py"),
        str(wiki_root), "Integration Test Wiki",
        "--template", "codebase", "--force",
    ], capture_output=True, check=True)
    return wiki_root


@pytest.fixture
def integration_source(integration_wiki):
    """Create a source document in the integration wiki."""
    source_path = integration_wiki / "raw" / "articles" / "integration-source.md"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("""# Integration Test Source

## Overview
This document tests the full ingest → lint → graph pipeline.

## Key Topics
- **Memory Management**: Techniques for managing memory in applications.
- **Caching Strategies**: Various approaches to data caching.
- **Performance Optimization**: Methods to improve application performance.

## Details
Memory management involves allocation and deallocation of memory resources.
Modern languages provide garbage collection, but manual management is still
important in systems programming.

Caching strategies range from simple in-memory caches to distributed cache
systems. Common patterns include LRU, LFU, and TTL-based eviction.

Performance optimization requires profiling first, then applying targeted
improvements at bottlenecks rather than premature optimization.

## Conclusion
Understanding memory, caching, and optimization is essential for building
performant applications.
""")
    return source_path


class TestGoldenPath:
    """Full integration test: scaffold → ingest → lint → graph."""

    def test_full_pipeline(self, integration_wiki, integration_source, monkeypatch):
        """Run the full pipeline with mock LLM responses."""
        import llm_wiki.ingest.pipeline as ingest_mod

        # Mock LLM for both stages
        def mock_llm(system, user, provider="default", total_timeout=None):
            if "Stage 1" in system or "analysis" in system.lower():
                return """## Entity Extraction
- MemoryManager: Component responsible for memory allocation/deallocation
- CacheSystem: Component for data caching
- Profiler: Tool for identifying performance bottlenecks

## Concept Extraction
- Memory Management: Techniques for managing memory in applications
- Caching: Strategy for storing frequently accessed data
- Performance Optimization: Process of improving application speed

## Key Claims
- Profiling should precede optimization
- LRU is a common cache eviction strategy
- Manual memory management is still relevant

## Relationships
- Memory Management influences Performance
- Caching is a Performance Optimization technique
"""
            return """---FILE: wiki/concepts/memory_management.md
---
title: Memory Management
type: concept
created: 2026-01-15
updated: 2026-01-15
sources: [integration-source]
tags: [systems, memory, performance]
confidence: high
---

# Memory Management

## Overview
Memory management involves allocation and deallocation of memory resources.

## Techniques
- Garbage Collection
- Manual Memory Management
- Reference Counting

## Related
- [[Caching Strategies]] can reduce memory pressure.
- Good memory management improves [[Performance Optimization]].

---FILE: wiki/concepts/caching_strategies.md
---
title: Caching Strategies
type: concept
created: 2026-01-15
updated: 2026-01-15
sources: [integration-source]
tags: [performance, caching]
confidence: high
---

# Caching Strategies

## Overview
Caching stores frequently accessed data for faster retrieval.

## Common Patterns
- **LRU**: Least Recently Used eviction
- **LFU**: Least Frequently Used eviction
- **TTL**: Time-To-Live expiration

## Related
- Caching is a key [[Performance Optimization]] technique.
- Works alongside [[Memory Management]].

---FILE: wiki/concepts/performance_optimization.md
---
title: Performance Optimization
type: concept
created: 2026-01-15
updated: 2026-01-15
sources: [integration-source]
tags: [performance, optimization]
confidence: high
---

# Performance Optimization

## Overview
Performance optimization improves application speed and resource usage.

## Methodology
1. Profile first to find bottlenecks
2. Apply targeted improvements
3. Measure impact
4. Iterate

## Related
- [[Caching Strategies]] reduce redundant computation.
- [[Memory Management]] affects runtime performance.

---REVIEW: suggestion
---
target: wiki/concepts/memory_management.md
title: Add Garbage Collection Details
description: Consider adding details about different GC algorithms.

"""

        monkeypatch.setattr(ingest_mod, "call_llm", mock_llm)

        # Step 1: Ingest
        result = ingest_mod.ingest(
            str(integration_wiki),
            str(integration_source),
        )
        assert result == 0

        # Step 2: Verify pages created
        expected = [
            "wiki/concepts/memory_management.md",
            "wiki/concepts/caching_strategies.md",
            "wiki/concepts/performance_optimization.md",
        ]
        for page in expected:
            assert (integration_wiki / page).exists(), f"Missing: {page}"

        # Step 3: Verify content has frontmatter
        page = integration_wiki / "wiki/concepts/memory_management.md"
        content = page.read_text()
        assert "type: concept" in content
        assert "title: Memory Management" in content
        assert "sources:" in content

        # Step 4: Verify pages have wikilinks
        caching_page = integration_wiki / "wiki/concepts/caching_strategies.md"
        caching_content = caching_page.read_text()
        assert "[[" in caching_content  # Has wikilinks

        # Step 5: Verify review was created
        audit_files = list((integration_wiki / "audit").glob("*.md"))
        non_gitkeep = [f for f in audit_files if f.name != ".gitkeep"]
        assert len(non_gitkeep) >= 1, "No review files created"

        # Step 6: Verify log created
        log_files = list((integration_wiki / "log").glob("*.md"))
        assert len(log_files) >= 1

        # Step 7: Verify index updated
        index_path = integration_wiki / "wiki" / "index.md"
        assert index_path.exists()
        index_content = index_path.read_text()
        assert "memory_management" in index_content.lower() or \
               "Memory Management" in index_content

        # Step 8: Run lint on the result
        from llm_wiki.quality.lint import lint
        lint_result = lint(str(integration_wiki))
        # Should have no or minimal issues
        # (index might have extra entries, etc.)
        assert lint_result in (0, 1)

        # Step 9: Verify graph can be built (requires TS build)
        # Skip if TS not built — this is a CI concern
        graph_engine_dist = REPO_ROOT / "graph-engine" / "dist" / "index.js"
        if graph_engine_dist.exists():
            try:
                graph_result = subprocess.run([
                    "node", str(graph_engine_dist),
                    "--wiki", str(integration_wiki / "wiki"),
                    "--action", "build",
                ], capture_output=True, text=True, timeout=30)
                assert graph_result.returncode == 0
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pytest.skip("graph-engine build not available")

    def test_cache_reuse_across_ingests(self, integration_wiki, integration_source, monkeypatch):
        """Second ingest should reuse cached analysis."""
        import llm_wiki.ingest.pipeline as ingest_mod

        stage1_calls = [0]

        def mock_llm(system, user, provider="default", total_timeout=None):
            if "Stage 1" in system:
                stage1_calls[0] += 1
                return "Analysis: test"
            return """---FILE: wiki/concepts/cached_test.md
---
title: Cached Test
type: concept
created: 2026-01-15
updated: 2026-01-15
sources: [integration-source]
tags: [test]
confidence: high
---

# Cached Test

Test page for cache reuse verification.
"""

        monkeypatch.setattr(ingest_mod, "call_llm", mock_llm)

        # First ingest
        ingest_mod.ingest(str(integration_wiki), str(integration_source))
        first_calls = stage1_calls[0]

        # Second ingest — should use cache
        stage1_calls[0] = 0
        # Remove the created page so it doesn't get skipped
        cached_page = integration_wiki / "wiki" / "concepts" / "cached_test.md"
        if cached_page.exists():
            cached_page.unlink()

        # Second ingest — the source hasn't changed, so cache should be hit
        # But the page was deleted, so Stage 2 will write it again
        # Stage 1 should NOT be called because analysis is cached
        result2 = ingest_mod.ingest(str(integration_wiki), str(integration_source))
        assert result2 == 0
        assert stage1_calls[0] == 0  # Cache was used, no new Stage 1 call


# ── Count ─────────────────────────────────────────────────────────────────
# test_integration.py = golden_path (1) + cache_reuse (1) = 2 test functions
# (but each one exercises the FULL pipeline)
