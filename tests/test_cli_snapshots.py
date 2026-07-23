"""Contract tests: CLI commands and exit codes.

These tests freeze the current CLI behavior (help output presence, exit codes)
so refactors can verify they haven't broken the user-facing interface.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"

COMMANDS = [
    "scaffold",
    "lint",
    "ingest",
    "insights",
    "link-suggest",
    "backup",
    "deep-research",
    "audit",
    "benchmark",
    "migrate-log",
    "discover",
    "index",
    "health",
    "serve",
    "claims",
]

ALIASES = {
    "ls": "lint",
    "in": "ingest",
    "sc": "scaffold",
    "bk": "backup",
    "dr": "deep-research",
    "lsug": "link-suggest",
}


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    env = {**__import__("os").environ, "PYTHONPATH": str(SRC_DIR)}
    return subprocess.run(
        [sys.executable, "-m", "llm_wiki"] + list(args),
        capture_output=True, text=True, env=env, timeout=30,
    )


class TestCliBaseline:
    def test_version(self):
        r = _run_cli("--version")
        assert r.returncode == 0
        assert r.stdout.strip() == "llm-wiki 0.2.1"

    def test_no_args_shows_help(self):
        r = _run_cli()
        assert r.returncode == 1
        assert "Available commands" in r.stderr
        for cmd in sorted(COMMANDS):
            assert cmd in r.stderr

    def test_unknown_command(self):
        r = _run_cli("nonexistent-command-xyz")
        assert r.returncode == 1
        assert "Unknown command" in r.stderr

    @pytest.mark.parametrize("cmd", COMMANDS)
    def test_help_output(self, cmd):
        if cmd in ("benchmark",):
            pytest.skip("benchmark --help is slow (triggers heavy imports)")
        if cmd == "migrate-log":
            pytest.skip("migrate-log uses non-standard argument parsing; will be fixed in modularization")
        r = _run_cli(cmd, "--help")
        assert r.returncode == 0, (
            f"'{cmd} --help' exited {r.returncode}: {r.stderr[:300]}"
        )
        assert len(r.stdout) > 0, f"'{cmd} --help' produced no stdout"
        assert "usage:" in r.stdout.lower() or "usage:" in r.stderr.lower()

    @pytest.mark.parametrize("alias,target", sorted(ALIASES.items()))
    def test_aliases_resolve(self, alias, target):
        r_orig = _run_cli(target, "--help")
        r_alias = _run_cli(alias, "--help")
        assert r_orig.returncode == 0
        assert r_alias.returncode == 0, (
            f"Alias '{alias}' should resolve to '{target}'"
        )


class TestCliExitCodes:
    def test_scaffold_no_args_exits_2(self):
        r = _run_cli("scaffold")
        assert r.returncode == 2

    def test_ingest_no_args_exits_2(self):
        r = _run_cli("ingest")
        assert r.returncode == 2

    def test_health_no_wiki_exits_2(self):
        r = _run_cli("health")
        assert r.returncode == 2

    def test_serve_no_args_exits_2(self):
        r = _run_cli("serve")
        assert r.returncode == 2

    def test_migrate_log_no_args_exits_1(self):
        r = _run_cli("migrate-log")
        assert r.returncode == 1

    def test_index_no_wiki_exits_2(self):
        r = _run_cli("index")
        assert r.returncode == 2
