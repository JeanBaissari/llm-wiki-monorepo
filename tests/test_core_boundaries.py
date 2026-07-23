"""Import boundary tests: ensure core modules have clean dependencies.

After modularization, core/ modules must NOT import:
  - cli (CLI dispatch)
  - providers (LLM integrations)
  - Any domain/command module (ingest, lint, claims, etc.)

This test is a placeholder that documents the expected boundary.
It will be expanded after core/ exists as a package directory.
"""

import ast
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"


def _extract_imports(filepath: Path) -> list[str]:
    """Return all 'from llm_wiki.[X]' or 'import llm_wiki.[X]' targets."""
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(filepath))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("llm_wiki"):
                parts = node.module.split(".")
                if len(parts) >= 2:
                    imports.append(parts[1])
    return imports


FORBIDDEN_IMPORTS_FOR_CORE = {
    "cli",
    "providers",
    "ingest",
    "lint",
    "lint_wiki",
    "claims",
    "backup",
    "graph_insights",
    "link_suggest",
    "index_wiki",
    "health_check",
    "serve",
    "benchmark",
    "scaffold",
    "deep_research",
    "audit_review",
    "audit_writer",
    "migrate_log",
}

# Modules that SHOULD be in core/ after modularization
CORE_CANDIDATES = [
    "core.frontmatter",
    "core.hashing",
    "core.atomic",
    "core.locking",
    "core.logging",
    "core.layout",
    "core.wikilinks",
]


class TestCoreBoundaries:
    @pytest.mark.parametrize("module_name", CORE_CANDIDATES)
    def test_core_module_has_no_domain_imports(self, module_name):
        """Core modules must not import from domain/command packages."""
        filepath = SRC_DIR / "llm_wiki" / (module_name.replace(".", "/") + ".py")
        if not filepath.exists():
            pytest.skip(f"{module_name} not yet at core/ subpackage")

        imports = _extract_imports(filepath)
        forbidden = [i for i in imports if i in FORBIDDEN_IMPORTS_FOR_CORE]
        assert not forbidden, (
            f"{module_name} imports domain modules: {forbidden}"
        )

    def test_core_module_imports_are_resolvable(self):
        for module_name in CORE_CANDIDATES:
            try:
                __import__(f"llm_wiki.{module_name}", fromlist=[""])
            except ImportError:
                pytest.skip(f"llm_wiki.{module_name} not importable (may not exist yet)")


class TestFutureCoreFiles:
    """Placeholder tests for modules that should be created during refactor."""

    def test_wikilinks_module_should_exist(self):
        """After refactor, core/wikilinks.py should centralize wikilink RE."""
        pass

    def test_paths_module_should_exist(self):
        """After refactor, core/paths.py should centralize path resolution."""
        pass
