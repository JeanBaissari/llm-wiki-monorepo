"""test_mcp_integration.py — MCP Sidecar Integration Tests (LWM_07).

Tests the Python JSON-RPC sidecar process end-to-end:
  - Health check
  - Lint via sidecar RPC
  - Ingest via sidecar RPC (with mock LLM)
  - Crash recovery
  - Concurrent requests
  - Graceful shutdown

The sidecar is spawned once per test class (session-level fixture)
and reused across most tests to avoid per-call spawn overhead.
"""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skill" / "scripts"
SIDECAR_PATH = SCRIPTS_DIR / "sidecar.py"


# ── JSON-RPC helpers ────────────────────────────────────────────────────────

def rpc_request(method: str, params: dict, req_id: int = 1) -> dict:
    """Build a JSON-RPC 2.0 request dict."""
    return {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}


def rpc_line(request: dict) -> str:
    """Serialize a request to a JSON-RPC line."""
    return json.dumps(request) + "\n"


def parse_response(line: str) -> dict:
    """Parse a JSON-RPC response line."""
    return json.loads(line.strip())


# ── Sidecar process management ──────────────────────────────────────────────

class SidecarProcess:
    """Manages a sidecar subprocess for testing.

    Usage:
        sidecar = SidecarProcess(wiki_root="/path/to/wiki")
        sidecar.start()
        result = sidecar.call("health", {})
        sidecar.stop()
    """

    def __init__(self, wiki_root: str, request_timeout: float = 10.0):
        self.wiki_root = wiki_root
        self.request_timeout = request_timeout
        self.process = None
        self._next_id = 1

    def start(self):
        """Spawn the sidecar subprocess."""
        env = os.environ.copy()
        env["LLM_WIKI_ROOT"] = self.wiki_root
        env["PYTHONUNBUFFERED"] = "1"

        self.process = subprocess.Popen(
            [sys.executable, "-u", str(SIDECAR_PATH)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
        )
        # Health check on startup
        result = self.call("health", {})
        assert result.get("status") == "ok", f"Sidecar health check failed: {result}"

    def stop(self):
        """Gracefully stop the sidecar."""
        if self.process is None or self.process.poll() is not None:
            return
        self.process.send_signal(signal.SIGTERM)
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()

    def kill(self):
        """Force-kill the sidecar (simulate crash)."""
        if self.process is None or self.process.poll() is not None:
            return
        self.process.kill()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass

    def call(self, method: str, params: dict) -> dict:
        """Send a JSON-RPC request and return the result."""
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError("Sidecar is not running")

        req_id = self._next_id
        self._next_id += 1
        request = rpc_request(method, params, req_id)

        try:
            self.process.stdin.write(rpc_line(request))
            self.process.stdin.flush()
        except BrokenPipeError:
            raise RuntimeError("Sidecar stdin closed unexpectedly")

        # Read response line
        deadline = time.time() + self.request_timeout
        while time.time() < deadline:
            line = self.process.stdout.readline()
            if line:
                response = parse_response(line)
                if response.get("id") == req_id:
                    if "error" in response:
                        err = response["error"]
                        raise RuntimeError(
                            f"RPC error [{err.get('code')}]: {err.get('message')}"
                        )
                    return response.get("result", {})
                # Response for a different request — should not happen in tests
            else:
                # EOF
                raise RuntimeError("Sidecar stdout closed unexpectedly")
            time.sleep(0.01)

        raise TimeoutError(f"RPC timeout after {self.request_timeout}s for method '{method}'")

    def is_running(self) -> bool:
        """Check if the sidecar process is alive."""
        return self.process is not None and self.process.poll() is None

    def drain_stderr(self) -> str:
        """Read any pending stderr output non-blocking."""
        if self.process is None:
            return ""
        import select
        output = []
        while True:
            ready = select.select([self.process.stderr], [], [], 0.1)
            if not ready[0]:
                break
            data = self.process.stderr.readline()
            if not data:
                break
            output.append(data)
        return "".join(output)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def sidecar_for_wiki(populated_wiki: Path) -> SidecarProcess:
    """Create a sidecar process connected to the populated wiki fixture."""
    sidecar = SidecarProcess(wiki_root=str(populated_wiki))
    sidecar.start()
    yield sidecar
    sidecar.stop()


@pytest.fixture
def fresh_wiki_for_ingest(tmp_path: Path) -> Path:
    """Scaffold a fresh wiki for ingest testing."""
    wiki_root = tmp_path / "fresh-wiki"
    subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "scaffold.py"),
            str(wiki_root),
            "Ingest Test Wiki",
            "--template", "codebase",
            "--force",
        ],
        capture_output=True,
        check=True,
    )
    return wiki_root


@pytest.fixture
def sidecar_for_fresh_wiki(fresh_wiki_for_ingest: Path) -> SidecarProcess:
    """Sidecar connected to a fresh wiki for ingest tests."""
    sidecar = SidecarProcess(wiki_root=str(fresh_wiki_for_ingest))
    sidecar.start()
    yield sidecar
    sidecar.stop()


# ── Tests: Health ────────────────────────────────────────────────────────────

class TestSidecarHealth:
    """Sidecar health check and basic lifecycle."""

    def test_health_check(self, sidecar_for_wiki: SidecarProcess):
        """Health check returns ok with wiki_root."""
        result = sidecar_for_wiki.call("health", {})
        assert result["status"] == "ok"
        assert result["wiki_root"] == str(sidecar_for_wiki.wiki_root)

    def test_health_after_multiple_calls(self, sidecar_for_wiki: SidecarProcess):
        """Multiple health checks all succeed."""
        for i in range(5):
            result = sidecar_for_wiki.call("health", {})
            assert result["status"] == "ok"

    def test_unknown_method(self, sidecar_for_wiki: SidecarProcess):
        """Unknown method returns proper JSON-RPC error."""
        with pytest.raises(RuntimeError, match="Method not found"):
            sidecar_for_wiki.call("nonexistent_method", {})


# ── Tests: Lint via Sidecar ──────────────────────────────────────────────────

class TestSidecarLint:
    """Lint tests via the sidecar RPC interface."""

    def test_lint_on_populated_wiki(self, sidecar_for_wiki: SidecarProcess):
        """Lint returns structured issues/warnings/passed for populated wiki."""
        result = sidecar_for_wiki.call("lint_wiki", {
            "wiki_root": sidecar_for_wiki.wiki_root,
            "paths": [],
            "fix": False,
            "check_broken_links": True,
        })
        assert "issues" in result
        assert "warnings" in result
        assert "passed" in result
        assert isinstance(result["issues"], list)
        assert isinstance(result["warnings"], list)
        assert isinstance(result["passed"], bool)

    def test_lint_produces_issues_structure(self, sidecar_for_wiki: SidecarProcess):
        """Lint issues have type, severity, page, detail fields."""
        result = sidecar_for_wiki.call("lint_wiki", {
            "wiki_root": sidecar_for_wiki.wiki_root,
        })
        for issue in result["issues"]:
            assert "type" in issue
            assert "severity" in issue
            assert "page" in issue
            assert "detail" in issue

    def test_lint_fallback_to_empty_paths(self, sidecar_for_wiki: SidecarProcess):
        """Lint with empty paths param still works (scans all)."""
        result = sidecar_for_wiki.call("lint_wiki", {"paths": []})
        assert "passed" in result

    def test_lint_on_empty_wiki(self, sidecar_for_fresh_wiki: SidecarProcess):
        """Lint on a fresh/unpopulated wiki is fast and clean."""
        result = sidecar_for_fresh_wiki.call("lint_wiki", {
            "wiki_root": sidecar_for_fresh_wiki.wiki_root,
        })
        assert "passed" in result
        # Fresh wiki should have no errors (may have warnings)
        error_issues = [i for i in result["issues"] if i.get("severity") == "error"]
        assert len(error_issues) == 0, f"Unexpected errors: {error_issues}"


# ── Tests: Ingest via Sidecar ────────────────────────────────────────────────

class TestSidecarIngest:
    """Ingest tests via the sidecar RPC interface.

    Note: Full ingest requires an LLM provider, which the sidecar subprocess
    can't access via monkeypatch. These tests verify the RPC dispatch path
    and error handling, while full ingest logic is tested in test_ingest.py.
    """

    def test_ingest_dispatch_calls_handler(self, sidecar_for_fresh_wiki: SidecarProcess,
                                            tmp_path: Path):
        """Ingest RPC reaches the handler and returns structured error for
        invalid wiki_root — proving dispatch works end-to-end."""
        result = sidecar_for_fresh_wiki.call("ingest_source", {
            "wiki_root": "/nonexistent/wiki",
            "source_path": str(tmp_path / "fake.md"),
        })
        assert result["success"] is False
        assert "wiki root not found" in result.get("error", "")

    def test_ingest_missing_source_path(self, sidecar_for_fresh_wiki: SidecarProcess):
        """Ingest with missing source_path returns error in result dict."""
        result = sidecar_for_fresh_wiki.call("ingest_source", {
            "wiki_root": sidecar_for_fresh_wiki.wiki_root,
            "source_path": "/nonexistent/file.md",
        })
        assert result["success"] is False
        assert "source file not found" in result.get("error", "")

    def test_ingest_invalid_wiki_root(self, sidecar_for_fresh_wiki: SidecarProcess):
        """Ingest with invalid wiki_root returns error via structured result."""
        result = sidecar_for_fresh_wiki.call("ingest_source", {
            "wiki_root": "/nonexistent/wiki",
            "source_path": "/tmp/fake.md",
        })
        assert result["success"] is False
        assert "wiki root not found" in result.get("error", "")

    def test_ingest_result_structure_on_error(self, tmp_path: Path):
        """ingest_source() returns structured error dict (in-process test)."""
        from llm_wiki.ingest.pipeline import ingest_source

        result = ingest_source(
            wiki_root="/nonexistent/wiki",
            source_path="/tmp/fake.md",
        )
        assert result["success"] is False
        assert "wiki root not found" in result["error"]
        assert result["pages_created"] == 0
        assert result["pages_updated"] == 0
        assert result["reviews_written"] == 0

    def test_ingest_source_in_process_with_mock(self, fresh_wiki_for_ingest: Path,
                                                  tmp_path: Path, monkeypatch):
        """ingest_source() works with mock LLM in-process."""
        import llm_wiki.ingest.pipeline as ingest_mod

        def _mock(system: str, user: str, provider: str = "default",
                  total_timeout=None) -> str | None:
            if "Stage 1" in system or "analysis" in system.lower():
                return """## Entity Extraction
- TestEntity: A test entity for sidecar integration tests

## Concept Extraction
- TestPattern: A pattern used in testing

## Key Claims
This is a mock analysis.

## Relationships
- TestEntity relates to TestPattern"""
            return """---FILE: wiki/concepts/sidecar_test_concept.md
---
title: Sidecar Test Concept
type: concept
created: 2026-01-15
updated: 2026-01-15
sources: [sidecar-test]
tags: [test, sidecar]
confidence: high
---

# Sidecar Test Concept

## Overview
Created via ingest_source().
"""

        monkeypatch.setattr(ingest_mod, "call_llm", _mock)

        source_path = tmp_path / "test-source.md"
        source_path.write_text("# Test Source\n\nTest content.\n")

        result = ingest_mod.ingest_source(
            wiki_root=str(fresh_wiki_for_ingest),
            source_path=str(source_path),
        )

        assert result["success"] is True, f"Ingest failed: {result.get('error')}"
        assert result["pages_created"] >= 1

        # Verify page was written
        page = fresh_wiki_for_ingest / "wiki" / "concepts" / "sidecar_test_concept.md"
        assert page.exists(), f"Page not created at {page}"


# ── Tests: Crash Recovery ────────────────────────────────────────────────────

class TestSidecarCrashRecovery:
    """Sidecar resilience: crash detection and restart."""

    def test_health_after_restart(self, populated_wiki: Path):
        """After stopping and restarting, health check succeeds."""
        sidecar = SidecarProcess(wiki_root=str(populated_wiki))
        sidecar.start()
        try:
            assert sidecar.call("health", {})["status"] == "ok"
            sidecar.stop()
            # Restart
            sidecar.start()
            assert sidecar.call("health", {})["status"] == "ok"
        finally:
            sidecar.stop()

    def test_kill_and_recreate(self, populated_wiki: Path):
        """A new sidecar process works after killing the old one."""
        sidecar = SidecarProcess(wiki_root=str(populated_wiki))
        sidecar.start()
        try:
            assert sidecar.call("health", {})["status"] == "ok"
            sidecar.kill()
            assert not sidecar.is_running()
            # Create a new sidecar
            sidecar.start()
            assert sidecar.is_running()
            assert sidecar.call("health", {})["status"] == "ok"
        finally:
            sidecar.stop()


# ── Tests: Concurrent Requests ───────────────────────────────────────────────

class TestSidecarConcurrency:
    """Sidecar handles multiple in-flight requests via request IDs."""

    def test_interleaved_requests(self, sidecar_for_wiki: SidecarProcess):
        """Send multiple requests and verify each gets correct response."""
        # Send two health checks with different IDs
        import threading
        import queue

        results = queue.Queue()

        def do_call(req_id: int):
            try:
                r = sidecar_for_wiki.call("health", {})
                results.put((req_id, r))
            except Exception as e:
                results.put((req_id, {"error": str(e)}))

        threads = [
            threading.Thread(target=do_call, args=(i,))
            for i in range(3)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # Collect results
        outcomes = {}
        while not results.empty():
            rid, res = results.get()
            outcomes[rid] = res

        assert len(outcomes) == 3
        for rid, res in outcomes.items():
            assert res.get("status") == "ok", f"Request {rid} failed: {res}"


# ── Tests: Graceful Shutdown ─────────────────────────────────────────────────

class TestSidecarShutdown:
    """Sidecar graceful shutdown behavior."""

    def test_stop_returns_cleanly(self, populated_wiki: Path):
        """stop() returns without error and process exits."""
        sidecar = SidecarProcess(wiki_root=str(populated_wiki))
        sidecar.start()
        assert sidecar.is_running()
        sidecar.stop()
        assert not sidecar.is_running()
        # Process should have exited
        assert sidecar.process is not None
        assert sidecar.process.poll() is not None

    def test_double_stop_is_safe(self, populated_wiki: Path):
        """Calling stop() twice does not raise."""
        sidecar = SidecarProcess(wiki_root=str(populated_wiki))
        sidecar.start()
        sidecar.stop()
        sidecar.stop()  # Should be a no-op


# ── Tests: Sidecar stdout/stderr separation ──────────────────────────────────

class TestSidecarOutputSeparation:
    """Verify that JSON-RPC responses go to stdout, not stderr."""

    def test_health_response_on_stdout_only(self, populated_wiki: Path):
        """Health check response is on stdout; stderr has diagnostics only."""
        env = os.environ.copy()
        env["LLM_WIKI_ROOT"] = str(populated_wiki)
        env["PYTHONUNBUFFERED"] = "1"

        proc = subprocess.Popen(
            [sys.executable, "-u", str(SIDECAR_PATH)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
        )
        try:
            proc.stdin.write(rpc_line(rpc_request("health", {}, 1)))
            proc.stdin.flush()
            proc.stdin.close()

            stdout = proc.stdout.read()
            stderr = proc.stderr.read()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
            raise

        # stdout should contain valid JSON-RPC response
        lines = [l for l in stdout.splitlines() if l.strip()]
        assert len(lines) >= 1, f"No stdout received. stderr: {stderr[:200]}"
        response = json.loads(lines[0])
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert response["result"]["status"] == "ok"

        # stderr should contain startup message
        assert "sidecar started" in stderr.lower() or "sidecar" in stderr.lower()
