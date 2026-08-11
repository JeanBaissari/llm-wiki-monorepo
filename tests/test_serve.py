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
import llm_wiki.ops.serve as serve

MCP_SERVER_DIR = REPO_ROOT / "mcp-server"

# The E2E startup/shutdown tests spawn `llm-wiki serve`, which runs the
# COMPILED MCP server (mcp-server/dist/main.js — gitignored). Fresh CI
# checkouts have no dist, so these tests skip unless the build exists; the
# compiled-server path is covered by the integration + certify jobs instead.
_NEEDS_MCP_BUILD = pytest.mark.skipif(
    not (MCP_SERVER_DIR / "dist" / "main.js").exists(),
    reason="mcp-server/dist/main.js not built (run `cd mcp-server && npx tsc`)",
)


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

    def test_help_lists_build_flag(self):
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
        assert "--build" in result.stdout


class _FakeProc:
    """Minimal stand-in for a subprocess.Popen child that already exited 0."""

    def __init__(self, returncode=0):
        self.returncode = returncode

    def poll(self):
        return self.returncode

    def send_signal(self, signum):
        pass

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        pass


class _FakeRunResult:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestServeBuildFlag:
    """Unit tests for the missing-dist error message + `--build` flag.

    These patch REPO_ROOT / dist existence / shutil.which / the subprocess seam
    so they run with or without a real mcp-server dist (no real server spawns).
    """

    def _call_main(self, monkeypatch, tmp_path, *args, repo_root=None):
        monkeypatch.setattr(serve, "REPO_ROOT", repo_root or tmp_path)
        monkeypatch.setattr(sys, "argv", ["llm-wiki serve", str(tmp_path / "wiki")] + list(args))
        return serve.main()

    def test_serve_missing_dist_error_message(self, tmp_path, monkeypatch, capsys):
        rc = self._call_main(monkeypatch, tmp_path)
        captured = capsys.readouterr()
        server_path = tmp_path / "mcp-server"
        assert rc == 1
        assert f"cd {server_path} && npm run build" in captured.err
        assert "bash install.sh" in captured.err
        assert "llm-wiki setup" in captured.err
        assert "dist/main.js" in captured.err

    def test_serve_build_flag_node_missing(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(serve.shutil, "which", lambda _name: None)
        build_run = []
        monkeypatch.setattr(serve.subprocess, "run", lambda *a, **k: build_run.append(a))
        rc = self._call_main(monkeypatch, tmp_path, "--build")
        captured = capsys.readouterr()
        assert rc == 1
        assert "Node.js 18+" in captured.err
        assert "bash install.sh" in captured.err
        assert build_run == [], "no build subprocess should run when node is absent"

    def test_serve_build_flag_builds_then_serves(self, tmp_path, monkeypatch, capsys):
        server_path = tmp_path / "mcp-server"
        (server_path / "node_modules").mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(serve.shutil, "which", lambda _name: "/usr/bin/node")

        build_calls = []
        monkeypatch.setattr(
            serve.subprocess, "run",
            lambda cmd, cwd=None, capture_output=False, text=False, **kw: (
                build_calls.append((list(cmd), cwd)),
                _FakeRunResult(),
            )[1],
        )
        launched = {}
        monkeypatch.setattr(
            serve.subprocess, "Popen",
            lambda cmd, cwd=None: (launched.update(cmd=list(cmd), cwd=cwd), _FakeProc())[1],
        )

        rc = self._call_main(monkeypatch, tmp_path, "--build")
        assert rc == 0
        assert build_calls == [(["npm", "run", "build"], str(server_path))]
        assert launched["cwd"] == str(server_path)
        assert launched["cmd"][0] == "node"
        assert "dist" in launched["cmd"][1]

    def test_serve_dist_present_no_build(self, tmp_path, monkeypatch, capsys):
        server_path = tmp_path / "mcp-server"
        dist = server_path / "dist" / "main.js"
        dist.parent.mkdir(parents=True)
        dist.write_text("// built")

        run_calls = []
        monkeypatch.setattr(
            serve.subprocess, "run",
            lambda cmd, cwd=None, capture_output=False, text=False, **kw: (
                run_calls.append(list(cmd)),
                _FakeRunResult(),
            )[1],
        )
        launched = {}
        monkeypatch.setattr(
            serve.subprocess, "Popen",
            lambda cmd, cwd=None: (launched.update(cmd=list(cmd)), _FakeProc())[1],
        )

        rc = self._call_main(monkeypatch, tmp_path, "--build")
        assert rc == 0
        assert run_calls == [], "dist present: --build is a no-op, no build runs"
        assert launched["cmd"][0] == "node"

        # Default (no --build) with dist present behaves exactly the same.
        launched.clear()
        rc = self._call_main(monkeypatch, tmp_path)
        assert rc == 0
        assert run_calls == []
        assert launched["cmd"][0] == "node"



@_NEEDS_MCP_BUILD
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


@_NEEDS_MCP_BUILD
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
