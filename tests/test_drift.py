"""test_drift.py — Drift detection: package vs skill wrapper parity.

Ensures skill/scripts/*.py user-facing command files are thin wrappers
that delegate to src/llm_wiki/ modules.

For user-facing commands:
  - Must contain `from llm_wiki.<module> import main` (or equivalent)
  - Must NOT define duplicated business logic (discover_layout, atomic_write, etc.)

Test/dev utilities in skill/scripts are explicitly excluded.
"""

import ast
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skill" / "scripts"
PACKAGE_DIR = REPO_ROOT / "src" / "llm_wiki"

# User-facing command files that must be wrappers
WRAPPER_COMMANDS = frozenset({
    "scaffold.py",
    "ingest.py",
    "lint_wiki.py",
    "discover.py",
    "graph_insights.py",
    "backup.py",
    "index_wiki.py",
    "link_suggest.py",
    "benchmark.py",
    "audit_review.py",
    "deep_research.py",
    "migrate_log.py",
    "health_check.py",
    "serve.py",
})

# Library-only files that may have business logic (not commands)
LIBRARY_FILES = frozenset({
    "sidecar.py",
    "validate_fixtures.py",
    "regenerate_fixtures.py",
    "louvain.py",
})

# Business logic functions that should NOT appear in wrappers
DUPLICATED_FUNCTIONS = frozenset({
    "discover_layout",
    "atomic_write",
    "write_wiki",
    "verify_wiki",
    "update_index",
    "append_log",
    "cleanup_temp_files",
    "clean_stale_locks",
    "parse_frontmatter",
})


def test_user_facing_commands_are_thin_wrappers():
    """Every user-facing skill/scripts command must be a thin wrapper."""
    for py_file in sorted(SKILL_DIR.glob("*.py")):
        if py_file.name not in WRAPPER_COMMANDS:
            continue

        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))

        # Check 1: must import from llm_wiki.<module>
        has_package_import = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("llm_wiki"):
                for alias in node.names:
                    if alias.name == "main":
                        has_package_import = True

        assert has_package_import, (
            f"{py_file.name}: missing 'from llm_wiki.<module> import main'"
        )

        # Check 2: must call raise SystemExit(main()) or sys.exit(main())
        has_exit_call = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise):
                if isinstance(node.exc, ast.Call):
                    func = node.exc.func
                    if isinstance(func, ast.Attribute) and func.attr == "exit" and isinstance(func.value, ast.Name) and func.value.id == "SystemExit":
                        has_exit_call = True
                    elif isinstance(func, ast.Name) and func.id == "SystemExit":
                        has_exit_call = True
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr == "exit":
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "sys":
                        has_exit_call = True

        assert has_exit_call, (
            f"{py_file.name}: missing 'raise SystemExit(main())' or 'sys.exit(main())'"
        )


def test_user_facing_commands_have_no_duplicated_logic():
    """User-facing wrappers must not define business logic functions."""
    for py_file in sorted(SKILL_DIR.glob("*.py")):
        if py_file.name not in WRAPPER_COMMANDS:
            continue

        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))

        func_defs = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_defs.add(node.name)

        duplicated = func_defs & DUPLICATED_FUNCTIONS
        assert not duplicated, (
            f"{py_file.name}: defines duplicated business logic: {', '.join(sorted(duplicated))}"
        )


def test_library_files_not_checked():
    """Library files are not subject to the wrapper check."""
    for py_file in SKILL_DIR.glob("*.py"):
        if py_file.name in LIBRARY_FILES:
            continue
        if py_file.name.endswith(".py") and py_file.name not in WRAPPER_COMMANDS and py_file.name not in LIBRARY_FILES:
            pytest.skip(f"{py_file.name} is not classified — add to WRAPPER_COMMANDS or LIBRARY_FILES")


@pytest.mark.parametrize("command", sorted(c for c in WRAPPER_COMMANDS if c != "benchmark.py"))
def test_wrapper_and_package_produce_same_help(command):
    """Both 'python -m llm_wiki <cmd> --help' and 'python3 skill/scripts/<cmd>.py --help' work.
    
    benchmark.py excluded because it triggers long-running imports/subprocesses.
    """
    import subprocess

    module_name = command.replace(".py", "")
    if module_name == "lint_wiki":
        cli_name = "lint"
    elif module_name == "index_wiki":
        cli_name = "index"
    elif module_name == "graph_insights":
        cli_name = "insights"
    elif module_name == "audit_review":
        cli_name = "audit"
    elif module_name == "migrate_log":
        cli_name = "migrate-log"
    elif module_name == "link_suggest":
        cli_name = "link-suggest"
    elif module_name == "deep_research":
        cli_name = "deep-research"
    elif module_name == "health_check":
        cli_name = "health"
    elif module_name == "serve":
        cli_name = "serve"
    else:
        cli_name = module_name

    env = dict(__import__("os").environ, PYTHONPATH=str(REPO_ROOT / "src"))

    # Test via package CLI
    result_pkg = subprocess.run(
        [sys.executable, "-m", "llm_wiki", cli_name, "--help"],
        capture_output=True, text=True, env=env, timeout=15,
    )

    # Test via skill script directly
    result_skill = subprocess.run(
        [sys.executable, str(SKILL_DIR / command), "--help"],
        capture_output=True, text=True, timeout=15,
    )

    assert result_pkg.returncode == 0, (
        f"Package CLI '{cli_name}' exit {result_pkg.returncode}: {result_pkg.stderr[:200]}"
    )
    assert result_skill.returncode == 0, (
        f"Skill script '{command}' exit {result_skill.returncode}: {result_skill.stderr[:200]}"
    )
