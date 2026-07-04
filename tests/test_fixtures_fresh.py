"""test_fixtures_fresh.py — Verify fixture wikis are current.

Runs validate_fixtures.py as a subprocess and checks exit code.
This test is the programmatic counterpart to the CI validate-fixtures job
— it catches stale fixtures during local development.
"""

import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
VALIDATE_SCRIPT = REPO_ROOT / "skill" / "scripts" / "validate_fixtures.py"


def test_fixtures_are_fresh():
    """All committed fixture wikis must match current schema version."""
    if not VALIDATE_SCRIPT.exists():
        pytest.skip("validate_fixtures.py not found")

    result = subprocess.run(
        [sys.executable, str(VALIDATE_SCRIPT), "--quiet"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(REPO_ROOT),
    )

    assert result.returncode == 0, (
        f"Fixtures are stale. Run: python3 skill/scripts/regenerate_fixtures.py\n"
        f"Details:\n{result.stderr}\n{result.stdout}"
    )


def test_schema_version_deterministic():
    """Schema version is computed deterministically from base-schema.md."""
    result = subprocess.run(
        [sys.executable, str(VALIDATE_SCRIPT), "--schema-version"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0
    version = result.stdout.strip()
    assert len(version) == 8, f"Schema version should be 8 hex chars, got '{version}'"
    assert all(c in "0123456789abcdef" for c in version), \
        f"Schema version should be hex, got '{version}'"
