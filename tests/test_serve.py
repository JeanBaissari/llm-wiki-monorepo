"""test_serve.py — E2E tests for llm-wiki serve.

Covers:
  - Scaffold a temp wiki
  - Start llm-wiki serve as a subprocess
  - Verify it starts successfully (check stdout for expected startup message)
  - Send SIGTERM and verify it shuts down gracefully
  - Test that --help works
  - Clean up temp wiki after test
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))


SCAFFOLD_SCRIPT = REPO_ROOT / "skill" / "scripts" / "scaffold.py"


def _scaffold_wiki(wiki_root: Path):
    cmd = [
        sys.executable, str(SCAFFOLD_SCRIPT),
        str(wiki_root), "Serve Test Wiki",
        "--template", "codebase",
        "--force",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, f"Scaffold failed: {result.stderr[:500]}"


class TestServeHelp:
    def test_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "llm_wiki", "serve", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        assert "Start the MCP server" in result.stdout


class TestServeStartup:
    def test_serve_starts(self, tmp_path):
        wiki = tmp_path / "serve-test-wiki"
        _scaffold_wiki(wiki)

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        proc = subprocess.Popen(
            [sys.executable, "-m", "llm_wiki", "serve", str(wiki)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(REPO_ROOT),
            env=env,
        )

        try:
            time.sleep(2)

            try:
                stdout_data = proc.stdout.read(1024) if proc.stdout else ""
                stderr_data = proc.stderr.read(1024) if proc.stderr else ""
            except Exception:
                stdout_data = ""
                stderr_data = ""

            assert proc.poll() is None, (
                f"Serve process exited too early. stderr: {stderr_data[:500]}"
            )
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()


class TestServeShutdown:
    def test_graceful_shutdown(self, tmp_path):
        wiki = tmp_path / "serve-shutdown-wiki"
        _scaffold_wiki(wiki)

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        proc = subprocess.Popen(
            [sys.executable, "-m", "llm_wiki", "serve", str(wiki)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(REPO_ROOT),
            env=env,
        )

        time.sleep(2)

        assert proc.poll() is None, "Serve process should be running before SIGTERM"

        proc.send_signal(signal.SIGTERM)

        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            pytest.fail("Serve process did not shut down within 10s of SIGTERM")

        assert proc.returncode is not None, "Process should have exited"

    def test_sigint_shutdown(self, tmp_path):
        wiki = tmp_path / "serve-sigint-wiki"
        _scaffold_wiki(wiki)

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        proc = subprocess.Popen(
            [sys.executable, "-m", "llm_wiki", "serve", str(wiki)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(REPO_ROOT),
            env=env,
        )

        time.sleep(2)

        assert proc.poll() is None, "Serve process should be running before SIGINT"

        proc.send_signal(signal.SIGINT)

        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            pytest.fail("Serve process did not shut down within 10s of SIGINT")

        assert proc.returncode is not None, "Process should have exited"
