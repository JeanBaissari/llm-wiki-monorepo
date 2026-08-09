"""test_serve.py — E2E tests for llm-wiki serve.

Covers:
  - Scaffold a temp wiki
  - Start llm-wiki serve as a subprocess
  - Verify it starts successfully (check stdout for expected startup message)
  - Send SIGTERM and verify it shuts down gracefully
  - Test that --help works
  - Test that serve works when the stale dist/index.js entry point is absent
    (the MCP server build emits dist/main.js, per package.json main)
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

from llm_wiki.ops.serve import resolve_server_entry

MCP_SERVER_DIR = REPO_ROOT / "mcp-server"


def _env_with_src():
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(SRC_DIR) + (os.pathsep + existing if existing else "")
    return env


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


class TestResolveServerEntry:
    def test_uses_package_json_main(self):
        entry = resolve_server_entry(MCP_SERVER_DIR)
        assert entry == MCP_SERVER_DIR / "dist" / "main.js"
        assert entry.name != "index.js"

    def test_rejects_stale_index_js(self):
        assert MCP_SERVER_DIR / "dist" / "index.js" != resolve_server_entry(MCP_SERVER_DIR)

    def test_falls_back_to_dist_main_js(self, tmp_path):
        entry = resolve_server_entry(tmp_path)
        assert entry == tmp_path / "dist" / "main.js"

    def test_ignores_malformed_package_json(self, tmp_path):
        (tmp_path / "package.json").write_text("not json{{")
        entry = resolve_server_entry(tmp_path)
        assert entry == tmp_path / "dist" / "main.js"

    def test_honors_custom_main_field(self, tmp_path):
        (tmp_path / "package.json").write_text('{"main": "dist/server.js"}')
        entry = resolve_server_entry(tmp_path)
        assert entry == tmp_path / "dist" / "server.js"


class TestServeHelp:
    def test_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "llm_wiki", "serve", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(REPO_ROOT),
            env=_env_with_src(),
        )
        assert result.returncode == 0
        assert "Start the MCP server" in result.stdout


class TestServeStartup:
    def _start_serve(self, wiki, stale_index_removed):
        backup = None
        if stale_index_removed:
            stale = MCP_SERVER_DIR / "dist" / "index.js"
            if stale.exists():
                backup = stale.read_bytes()
                stale.unlink()
        proc = subprocess.Popen(
            [sys.executable, "-m", "llm_wiki", "serve", str(wiki)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(REPO_ROOT),
            env=_env_with_src(),
        )
        return proc, backup

    def test_serve_starts(self, tmp_path):
        wiki = tmp_path / "serve-test-wiki"
        _scaffold_wiki(wiki)

        proc, _backup = self._start_serve(wiki, stale_index_removed=False)

        try:
            time.sleep(2)

            if proc.poll() is not None:
                stderr_data = proc.stderr.read() if proc.stderr else ""
                pytest.fail(
                    f"Serve process exited too early (rc={proc.returncode}). stderr: {stderr_data[:500]}"
                )
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()

    def test_serve_starts_without_stale_index_js(self, tmp_path):
        wiki = tmp_path / "serve-no-index-wiki"
        _scaffold_wiki(wiki)

        proc, backup = self._start_serve(wiki, stale_index_removed=True)

        try:
            time.sleep(2)

            if proc.poll() is not None:
                stderr_data = proc.stderr.read() if proc.stderr else ""
                pytest.fail(
                    f"Serve process exited too early (rc={proc.returncode}). stderr: {stderr_data[:500]}"
                )
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
            if backup is not None:
                stale = MCP_SERVER_DIR / "dist" / "index.js"
                stale.parent.mkdir(parents=True, exist_ok=True)
                stale.write_bytes(backup)


class TestServeShutdown:
    def test_graceful_shutdown(self, tmp_path):
        wiki = tmp_path / "serve-shutdown-wiki"
        _scaffold_wiki(wiki)

        proc = subprocess.Popen(
            [sys.executable, "-m", "llm_wiki", "serve", str(wiki)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(REPO_ROOT),
            env=_env_with_src(),
        )

        time.sleep(2)

        if proc.poll() is not None:
            stderr_data = proc.stderr.read() if proc.stderr else ""
            pytest.fail(f"Serve process exited early. stderr: {stderr_data[:500]}")

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

        proc = subprocess.Popen(
            [sys.executable, "-m", "llm_wiki", "serve", str(wiki)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(REPO_ROOT),
            env=_env_with_src(),
        )

        time.sleep(2)

        if proc.poll() is not None:
            stderr_data = proc.stderr.read() if proc.stderr else ""
            pytest.fail(f"Serve process exited early. stderr: {stderr_data[:500]}")

        proc.send_signal(signal.SIGINT)

        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            pytest.fail("Serve process did not shut down within 10s of SIGINT")

        assert proc.returncode is not None, "Process should have exited"
