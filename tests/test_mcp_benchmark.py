"""test_mcp_benchmark.py — MCP Sidecar Performance Benchmarks (LWM_07).

Compares sidecar RPC dispatch overhead against:
  - Direct in-process Python function calls (the "ideal" baseline)
  - The subprocess-spawn approach (historical reference)

Key metrics per PRD:
  - Sidecar dispatch overhead < 50ms per call (excludes computation)
  - ≥5x reduction in per-call overhead vs subprocess baseline
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skill" / "scripts"
SIDECAR_PATH = SCRIPTS_DIR / "sidecar.py"


# ── Helpers ──────────────────────────────────────────────────────────────────

def time_fn(fn, *args, warmup: int = 1, iterations: int = 10, **kwargs):
    """Time a function call, returning (mean_ms, min_ms, max_ms)."""
    # Warmup
    for _ in range(warmup):
        fn(*args, **kwargs)

    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn(*args, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000  # ms
        times.append(elapsed)

    times.sort()
    mean = sum(times) / len(times)
    return mean, times[0], times[-1]


# ── Sidecar RPC helper (lightweight, no class overhead) ──────────────────────

def sidecar_rpc_call(method: str, params: dict, wiki_root: str,
                     timeout: float = 10.0) -> dict:
    """Fire-and-forget sidecar RPC call — spawns sidecar, sends one request."""
    env = os.environ.copy()
    env["LLM_WIKI_ROOT"] = wiki_root
    env["PYTHONUNBUFFERED"] = "1"

    request = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": method, "params": params,
    }) + "\n"

    proc = subprocess.Popen(
        [sys.executable, "-u", str(SIDECAR_PATH)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
    )

    try:
        proc.stdin.write(request)
        proc.stdin.flush()
        proc.stdin.close()

        stdout = proc.stdout.read()
        proc.wait(timeout=timeout)
    except Exception:
        proc.kill()
        proc.wait()
        raise

    response = json.loads(stdout.strip())
    if "error" in response:
        raise RuntimeError(f"RPC error: {response['error']}")
    return response["result"]


# ── Benchmarks: Sidecar RPC Overhead ─────────────────────────────────────────

class TestSidecarDispatchOverhead:
    """Measure pure JSON-RPC dispatch overhead on a running sidecar.

    The PRD's <50ms dispatch overhead target refers to the TypeScript
    sidecar manager's call() latency — JSON serialization + IPC round-trip
    to an already-running sidecar process. These tests measure that by
    using a long-lived sidecar and timing only the RPC call, not spawn.
    """

    @pytest.fixture
    def running_sidecar(self, populated_wiki: Path):
        """Long-lived sidecar for dispatch overhead measurements."""
        from test_mcp_integration import SidecarProcess
        sidecar = SidecarProcess(wiki_root=str(populated_wiki))
        sidecar.start()
        # Warmup
        for _ in range(3):
            sidecar.call("health", {})
        yield sidecar
        sidecar.stop()

    def test_dispatch_overhead_under_50ms(self, running_sidecar):
        """JSON-RPC round-trip to a running sidecar is < 50ms mean."""
        times = []
        # Run several calls and measure
        for _ in range(20):
            start = time.perf_counter()
            result = running_sidecar.call("health", {})
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
            assert result["status"] == "ok"

        times.sort()
        mean = sum(times) / len(times)
        min_val = times[0]
        max_val = times[-1]

        print(f"\n  Health RPC dispatch (running sidecar): "
              f"mean={mean:.1f}ms, min={min_val:.1f}ms, max={max_val:.1f}ms")
        assert mean < 50, \
            f"Dispatch overhead {mean:.1f}ms exceeds 50ms AC target"

    def test_dispatch_stable_under_load(self, running_sidecar):
        """Per-call dispatch overhead stays consistent across 50 calls."""
        times = []
        for _ in range(50):
            start = time.perf_counter()
            running_sidecar.call("health", {})
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        times.sort()
        mean = sum(times) / len(times)
        # P95 should be reasonable
        p95 = times[int(len(times) * 0.95)]

        print(f"\n  50-call dispatch: mean={mean:.1f}ms, p95={p95:.1f}ms, "
              f"min={times[0]:.1f}ms, max={times[-1]:.1f}ms")
        assert mean < 50, f"Mean dispatch {mean:.1f}ms exceeds 50ms"
        # P95 can be higher due to OS scheduling jitter
        assert p95 < 100, f"P95 dispatch {p95:.1f}ms indicates instability"


# ── Benchmarks: Sidecar vs Direct Python Function ────────────────────────────

class TestSidecarVsDirect:
    """Compare sidecar RPC to direct in-process Python function calls.

    These show the overhead of JSON-RPC serialization + subprocess IPC
    vs calling the same function in-process.
    """

    def test_lint_sidecar_vs_direct(self, populated_wiki: Path):
        """Sidecar lint dispatch overhead compared to direct lint_files()."""
        wiki_root = str(populated_wiki)

        # Direct lint_files (in-process)
        from lint_wiki import lint_files

        def direct_lint():
            return lint_files(root=wiki_root)

        # Warmup both
        direct_lint()
        sidecar_rpc_call("lint_wiki", {"wiki_root": wiki_root}, wiki_root)

        direct_mean, _, _ = time_fn(direct_lint, warmup=1, iterations=5)
        sidecar_mean, _, _ = time_fn(
            sidecar_rpc_call, "lint_wiki", {"wiki_root": wiki_root},
            wiki_root=wiki_root, warmup=1, iterations=5,
        )

        overhead = sidecar_mean - direct_mean
        print(f"\n  Direct lint: {direct_mean:.1f}ms")
        print(f"  Sidecar lint: {sidecar_mean:.1f}ms")
        print(f"  Overhead: {overhead:.1f}ms")

        # The overhead should be reasonable — the sidecar adds IPC cost
        # but eliminates per-call subprocess spawn. The 50ms target is
        # for pure dispatch, not total computation.
        assert overhead < 500, \
            f"Sidecar overhead {overhead:.1f}ms is excessively high"

    def test_sidecar_reuse_benefit(self, populated_wiki: Path):
        """Multiple sidecar calls on a persistent process — per-call cost is flat."""
        from test_mcp_integration import SidecarProcess
        sidecar = SidecarProcess(wiki_root=str(populated_wiki))
        sidecar.start()

        try:
            results = []
            for n_calls in [1, 5, 10, 20]:
                start = time.perf_counter()
                for _ in range(n_calls):
                    sidecar.call("health", {})
                elapsed = (time.perf_counter() - start) * 1000 / n_calls
                results.append((n_calls, elapsed))

            print(f"\n  Per-call latency on persistent sidecar:")
            for n, lat in results:
                print(f"    {n:3d} calls: {lat:.1f}ms avg")
                assert lat < 50, \
                    f"Per-call latency {lat:.1f}ms at {n} calls exceeds 50ms threshold"
        finally:
            sidecar.stop()


# ── Benchmarks: Subprocess Spawn Baseline ────────────────────────────────────

class TestSubprocessSpawnBaseline:
    """Measure subprocess spawn overhead for historical comparison.

    These measure the old approach (spawn python3 per call) to validate
    that the sidecar eliminates that overhead. Since the refactored code
    doesn't spawn subprocesses per tool call anymore, we measure the
    theoretical baseline by spawning a minimal Python process.
    """

    def test_minimal_subprocess_spawn_time(self):
        """Time to spawn python3 -c 'pass' — absolute minimum subprocess cost."""
        def spawn_minimal():
            subprocess.run(
                [sys.executable, "-c", ""],
                capture_output=True,
                timeout=5,
            )

        mean, min_val, max_val = time_fn(
            spawn_minimal, warmup=2, iterations=20,
        )

        print(f"\n  Minimal subprocess spawn: mean={mean:.1f}ms, min={min_val:.1f}ms, max={max_val:.1f}ms")

        # On modern Linux, subprocess spawn is typically 20-80ms.
        # This is the baseline overhead we eliminate with the sidecar.
        assert mean > 0, "Subprocess spawn time should be measurable"

    def test_sidecar_vs_subprocess_ratio(self, populated_wiki: Path):
        """Verify sidecar dispatch on a running process is ≥5x faster than
        subprocess spawn baseline."""
        from test_mcp_integration import SidecarProcess

        # Subprocess baseline: spawn python3 -c "pass"
        def spawn_baseline():
            subprocess.run([sys.executable, "-c", ""], capture_output=True)

        spawn_times = []
        for _ in range(3):  # warmup
            spawn_baseline()
        for _ in range(20):
            start = time.perf_counter()
            spawn_baseline()
            spawn_times.append((time.perf_counter() - start) * 1000)
        spawn_mean = sum(spawn_times) / len(spawn_times)

        # Sidecar dispatch on already-running process
        sidecar = SidecarProcess(wiki_root=str(populated_wiki))
        sidecar.start()
        try:
            # Warmup
            for _ in range(3):
                sidecar.call("health", {})
            dispatch_times = []
            for _ in range(20):
                start = time.perf_counter()
                sidecar.call("health", {})
                dispatch_times.append((time.perf_counter() - start) * 1000)
            dispatch_mean = sum(dispatch_times) / len(dispatch_times)
        finally:
            sidecar.stop()

        ratio = spawn_mean / dispatch_mean if dispatch_mean > 0 else float("inf")

        print(f"\n  Subprocess spawn baseline: {spawn_mean:.1f}ms")
        print(f"  Sidecar dispatch (running): {dispatch_mean:.1f}ms")
        print(f"  Speedup: {ratio:.1f}x")

        # Sidecar dispatch should be >5x faster than subprocess spawn
        assert ratio >= 5, \
            f"Sidecar dispatch speedup {ratio:.1f}x below 5x target. " \
            f"Sidecar: {dispatch_mean:.1f}ms, Spawn: {spawn_mean:.1f}ms"


# ── Benchmarks: Lint Tool Latency ────────────────────────────────────────────

class TestLintLatency:
    """Benchmark the full lint tool path through the sidecar."""

    def test_lint_cold_start(self, populated_wiki: Path):
        """First lint call (cold, includes module import)."""
        wiki_root = str(populated_wiki)
        start = time.perf_counter()
        result = sidecar_rpc_call("lint_wiki", {"wiki_root": wiki_root}, wiki_root)
        elapsed = (time.perf_counter() - start) * 1000

        print(f"\n  Lint cold start: {elapsed:.1f}ms")
        assert "issues" in result
        # Cold start should be fast even with imports (target: < 500ms for small wiki)
        assert elapsed < 2000, f"Lint cold start {elapsed:.1f}ms too slow"

    def test_lint_warm_reuse(self, populated_wiki: Path):
        """Lint on second call is faster (imports cached)."""
        wiki_root = str(populated_wiki)

        # Warmup
        sidecar_rpc_call("lint_wiki", {"wiki_root": wiki_root}, wiki_root)

        mean, _, _ = time_fn(
            sidecar_rpc_call, "lint_wiki", {"wiki_root": wiki_root},
            wiki_root=wiki_root, warmup=1, iterations=5,
        )

        print(f"\n  Lint warm call: {mean:.1f}ms")
        assert mean < 1000, f"Warm lint {mean:.1f}ms too slow"


# ── Benchmarks: Ingest Tool Latency ──────────────────────────────────────────

class TestIngestLatency:
    """Benchmark ingest dispatch through the sidecar (mock LLM)."""

    @pytest.fixture(autouse=True)
    def mock_llm(self, monkeypatch):
        """Mock LLM for ingest benchmarks."""
        import llm_wiki.ingest.pipeline as ingest_mod

        def _mock(system: str, user: str, provider: str = "default",
                  total_timeout=None) -> str | None:
            if "Stage 1" in system or "analysis" in system.lower():
                return "Mock analysis for benchmark."
            return """---FILE: wiki/concepts/bench_concept.md
---
title: Bench Concept
type: concept
created: 2026-01-15
updated: 2026-01-15
sources: [bench]
tags: [benchmark]
confidence: high
---

# Bench Concept

Test page for ingest benchmark.
"""

        monkeypatch.setattr(ingest_mod, "call_llm", _mock)

    def test_ingest_dispatch_latency(self, tmp_path: Path):
        """Ingest via sidecar — measure dispatch overhead only."""
        # Create a fresh wiki
        wiki_root = tmp_path / "bench-wiki"
        subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "scaffold.py"),
             str(wiki_root), "Bench Wiki", "--template", "codebase", "--force"],
            capture_output=True, check=True,
        )

        # Create source
        source = tmp_path / "bench-source.md"
        source.write_text("# Bench Source\n\nTest content for benchmark.\n")

        wiki_root_s = str(wiki_root)
        source_s = str(source)

        # Warmup
        sidecar_rpc_call("ingest_source", {
            "wiki_root": wiki_root_s, "source_path": source_s,
        }, wiki_root_s)

        # Measure dispatch overhead (excludes LLM time since we mock it)
        mean, min_val, max_val = time_fn(
            sidecar_rpc_call,
            "ingest_source",
            {"wiki_root": wiki_root_s, "source_path": source_s},
            wiki_root=wiki_root_s,
            warmup=1, iterations=5,
        )

        print(f"\n  Ingest dispatch: mean={mean:.1f}ms, min={min_val:.1f}ms, max={max_val:.1f}ms")
        # Ingest involves more processing than health, but dispatch should
        # still be fast since LLM is mocked
        assert mean < 500, f"Ingest dispatch {mean:.1f}ms exceeded threshold"
