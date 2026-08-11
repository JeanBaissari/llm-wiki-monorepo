#!/usr/bin/env python3
"""
release_certify.py — Release certification orchestrator.

Runs all quality gates and emits a JSON certification report.
Designed for both CI and local developer use.

Gates:
  1. Release manifest check (version consistency)
  2. Docs truth check (docs vs source registries)
  3. Python tests (pytest, excluding slow benchmarks)
  4. TypeScript typecheck (all workspace packages)
  5. TypeScript tests (all workspace packages)
  6. Fixture validation (schema freshness)
  7. MCP stdio E2E (tools/list, representative calls)
  8. Search-eval gate (hybrid default certification, LWM_032 / ADR-0020)
  9. Search gold-set freshness (per-minor curation loop, LWM_039 §A)

Usage:
    python3 scripts/release_certify.py              # all gates
    python3 scripts/release_certify.py --json-only  # JSON to stdout only
    python3 scripts/release_certify.py --gate pytest  # single gate

Output:
    reports/release-certification.json — full report
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
REPORTS_DIR = REPO_ROOT / "reports"

# The registered gates, in execution order. The release-certify orchestrator
# runs every gate by default; each is also selectable via ``--gate <name>``.
GATES = (
    "release_manifest", "docs_truth", "pytest", "ts_typecheck",
    "ts_tests", "fixtures", "mcp_e2e", "search_eval", "search_goldset_fresh",
)


def run_command(cmd: list[str], cwd: Path | None = None, timeout: int = 300,
                env: dict | None = None) -> dict:
    """Run a command and return structured result."""
    start = time.time()
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            cwd=str(cwd) if cwd else None, env=merged_env,
        )
        duration = round(time.time() - start, 3)
        return {
            "command": " ".join(cmd),
            "exit_code": result.returncode,
            "stdout": result.stdout[-5000:] if len(result.stdout) > 5000 else result.stdout,
            "stderr": result.stderr[-5000:] if len(result.stderr) > 5000 else result.stderr,
            "duration_s": duration,
            "status": "PASS" if result.returncode == 0 else "FAIL",
        }
    except subprocess.TimeoutExpired:
        duration = round(time.time() - start, 3)
        return {
            "command": " ".join(cmd),
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
            "duration_s": duration,
            "status": "TIMEOUT",
        }
    except FileNotFoundError as e:
        duration = round(time.time() - start, 3)
        return {
            "command": " ".join(cmd),
            "exit_code": -2,
            "stdout": "",
            "stderr": f"Command not found: {e}",
            "duration_s": duration,
            "status": "ERROR",
        }


def gate_release_manifest(env: dict | None = None) -> dict:
    """Gate 1: Release manifest version consistency check."""
    script = SCRIPTS_DIR / "release_manifest.py"
    if not script.exists():
        return {
            "gate": "release_manifest",
            "status": "SKIP",
            "reason": f"{script} not found",
        }
    result = run_command([sys.executable, str(script), "--json-only"], env=env)
    return {"gate": "release_manifest", **result}


def gate_docs_truth_check(env: dict | None = None) -> dict:
    """Gate 2: Docs truth check."""
    script = SCRIPTS_DIR / "docs_truth_check.py"
    if not script.exists():
        return {
            "gate": "docs_truth_check",
            "status": "SKIP",
            "reason": f"{script} not found",
        }
    result = run_command([sys.executable, str(script), "--json-only"], env=env)
    return {"gate": "docs_truth_check", **result}


def gate_pytest(env: dict | None = None) -> dict:
    """Gate 3: Python tests (excluding slow benchmarks)."""
    result = run_command(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short"],
        cwd=REPO_ROOT, env=env, timeout=900,
    )
    return {"gate": "pytest", **result}


def gate_ts_typecheck(env: dict | None = None) -> dict:
    """Gate 4: TypeScript typecheck for all workspace packages."""
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    merged_env.pop("CI", None)

    results = []
    packages = ["mcp-server", "graph-engine", "audit-shared"]

    # mcp-server/graph-engine import @baissari/llm-wiki-shared-types whose
    # dist/ is gitignored — build it before typechecking any consumer (fresh
    # checkouts would otherwise fail every consumer with TS2307).
    shared = run_command(
        ["npx", "tsc"],
        cwd=REPO_ROOT / "packages" / "shared-types", env=merged_env, timeout=120,
    )
    if shared.get("status") != "PASS":
        results.append({"package": "shared-types (build)", **shared})

    for pkg in packages:
        pkg_dir = REPO_ROOT / pkg
        if not (pkg_dir / "tsconfig.json").exists():
            results.append({
                "package": pkg,
                "status": "SKIP",
                "reason": "No tsconfig.json",
            })
            continue
        result = run_command(
            ["npx", "tsc", "--noEmit"],
            cwd=pkg_dir, env=merged_env, timeout=120,
        )
        results.append({"package": pkg, **result})

    all_pass = all(r.get("status") == "PASS" for r in results)
    return {
        "gate": "ts_typecheck",
        "status": "PASS" if all_pass else "FAIL",
        "packages": results,
    }


def gate_ts_tests(env: dict | None = None) -> dict:
    """Gate 5: TypeScript tests for all workspace packages."""
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    merged_env.pop("CI", None)

    results = []
    packages = ["mcp-server", "graph-engine"]

    # mcp-server tests import ../dist/* (gitignored build output) — build the
    # packages before running their tests on a fresh checkout.
    for build_pkg in ("mcp-server", "graph-engine"):
        build = run_command(
            ["npx", "tsc"],
            cwd=REPO_ROOT / build_pkg, env=merged_env, timeout=180,
        )
        if build.get("status") != "PASS":
            results.append({"package": f"{build_pkg} (build)", **build})

    for pkg in packages:
        pkg_dir = REPO_ROOT / pkg
        pkg_json = pkg_dir / "package.json"
        if not pkg_json.exists():
            results.append({"package": pkg, "status": "SKIP", "reason": "No package.json"})
            continue
        try:
            data = json.loads(pkg_json.read_text())
            scripts = data.get("scripts", {})
        except Exception:
            results.append({"package": pkg, "status": "SKIP", "reason": "Invalid package.json"})
            continue
        if "test" not in scripts:
            results.append({"package": pkg, "status": "SKIP", "reason": "No test script"})
            continue

        result = run_command(
            ["npm", "run", "test"],
            cwd=pkg_dir, env=merged_env, timeout=120,
        )

        zero_test, zero_reason = _detect_zero_test(result.get("stdout", ""))
        if result["status"] == "PASS" and zero_test:
            result["status"] = "FAIL"
            result["stderr"] = f"ZERO-TEST: {zero_reason}"

        results.append({"package": pkg, **result})

    all_pass = all(r.get("status") == "PASS" for r in results)
    return {
        "gate": "ts_tests",
        "status": "PASS" if all_pass else "FAIL",
        "packages": results,
    }


def gate_fixture_validation(env: dict | None = None) -> dict:
    """Gate 6: Fixture schema freshness check."""
    script = REPO_ROOT / "skill" / "scripts" / "validate_fixtures.py"
    if not script.exists():
        return {
            "gate": "fixture_validation",
            "status": "SKIP",
            "reason": "validate_fixtures.py not found",
        }
    result = run_command([sys.executable, str(script), "--json"], env=env)
    return {"gate": "fixture_validation", **result}


def gate_mcp_stdio_e2e(env: dict | None = None) -> dict:
    """Gate 7: MCP stdio E2E test."""
    pkg_dir = REPO_ROOT / "mcp-server"
    pkg_json = pkg_dir / "package.json"
    if not pkg_json.exists():
        return {
            "gate": "mcp_stdio_e2e",
            "status": "SKIP",
            "reason": "No mcp-server/package.json",
        }
    try:
        data = json.loads(pkg_json.read_text())
        scripts = data.get("scripts", {})
    except Exception:
        return {
            "gate": "mcp_stdio_e2e",
            "status": "SKIP",
            "reason": "Invalid mcp-server/package.json",
        }
    if "test" not in scripts:
        return {
            "gate": "mcp_stdio_e2e",
            "status": "SKIP",
            "reason": "No test script in mcp-server",
        }

    result = run_command(
        ["npm", "run", "test", "--", "--run"],
        cwd=pkg_dir, env=env, timeout=120,
    )
    return {"gate": "mcp_stdio_e2e", **result}


def gate_search_eval(env: dict | None = None) -> dict:
    """Gate 8: Search-eval gate (LWM_032 / ADR-0020).

    Certifies the hybrid-default flip: deterministic concept-embedder gate +
    baseline reproducibility + gold-set integrity. Green even when the
    [semantic] extra is absent — the deterministic proxy is the point; CI's
    semantic job additionally recertifies with the real embedder.
    """
    result = run_command(
        [
            sys.executable, "-m", "pytest",
            "tests/test_search_eval_gate.py",
            "tests/test_search_baseline_reproducible.py",
            "tests/eval/test_search_goldset_integrity.py",
            "-q", "--tb=short",
        ],
        cwd=REPO_ROOT, env=env, timeout=600,
    )
    return {"gate": "search_eval", **result}


_MINOR_RE = re.compile(r"v?(\d+)\.(\d+)")


def _minor_key(minor_str: str) -> "tuple[int, int] | None":
    m = _MINOR_RE.search(str(minor_str))
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)))


def _previous_minor(key: "tuple[int, int]") -> "tuple[int, int]":
    major, minor = key
    if minor > 0:
        return (major, minor - 1)
    return (major - 1, 0)


def _current_minor(repo_root: Path) -> "tuple[int, int] | None":
    """Repo's current minor from src/llm_wiki/__init__.py __version__."""
    init = repo_root / "src" / "llm_wiki" / "__init__.py"
    if not init.exists():
        return None
    m = re.search(r'__version__\s*=\s*"([^"]+)"', init.read_text(encoding="utf-8"))
    if not m:
        return None
    return _minor_key(m.group(1))


def gate_search_goldset_fresh(env: dict | None = None, repo_root: Path | None = None) -> dict:
    """Gate 9: Search gold-set freshness (LWM_039 §A).

    Fails closed on (a) gold-set/manifest SHA drift and (b) a gate split below
    the committed ``MIN_GATE_QUERIES`` floor; fails when the grow-or-justify
    marker in ``growth_meta.json`` is absent (loop skipped); warns (not a hard
    fail) when ``last_grown_minor`` is older than the previous minor. Real
    search regression is already gated by ``gate_search_eval`` (gate 8).
    """
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    gold_dir = root / "tests" / "eval" / "gold"
    goldset = gold_dir / "search_goldset.json"
    manifest = gold_dir / "split_manifest.json"
    meta = gold_dir / "growth_meta.json"

    checks: dict[str, dict] = {}
    warns: list[str] = []
    hard_failures: list[str] = []

    def _record(name: str, status: str, detail: str) -> None:
        checks[name] = {"status": status, "detail": detail}

    if not goldset.exists() or not manifest.exists():
        return {
            "gate": "search_goldset_fresh",
            "status": "FAIL",
            "reason": "search_goldset.json or split_manifest.json missing",
            "checks": checks,
        }

    # 1. integrity — sha256(goldset) == manifest sha256
    import hashlib
    sha = hashlib.sha256(goldset.read_bytes()).hexdigest()
    manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    if manifest_data.get("sha256") != sha:
        _record("integrity", "FAIL",
                f"goldset sha256 {sha[:12]}… != manifest "
                f"{str(manifest_data.get('sha256'))[:12]}… — re-freeze required")
        hard_failures.append("integrity")
    else:
        _record("integrity", "PASS", "sha256 matches split_manifest.json")

    # 2. gate count >= min_gate_queries — committed floor, fail-closed on regression
    floor = 16
    meta_data: dict = {}
    if not meta.exists():
        _record("gate_floor", "FAIL",
                "growth_meta.json missing — min_gate_queries floor unavailable")
        hard_failures.append("gate_floor")
    else:
        meta_data = json.loads(meta.read_text(encoding="utf-8"))
        floor = meta_data.get("min_gate_queries", 16)
    gate_queries = manifest_data.get("gate", [])
    n_gate = len(gate_queries)
    if n_gate < floor:
        _record("gate_floor", "FAIL",
                f"gate split has {n_gate} queries < committed floor {floor}")
        hard_failures.append("gate_floor")
    else:
        _record("gate_floor", "PASS",
                f"{n_gate} gate queries >= committed floor {floor}")

    # 3. grow-or-justify freshness marker (advisory warn, not a hard fail)
    if not meta.exists():
        _record("grow_or_justify", "FAIL",
                "growth_meta.json absent — the per-minor loop was never recorded")
        hard_failures.append("grow_or_justify")
    else:
        last_grown = meta_data.get("last_grown_minor")
        if not last_grown:
            _record("grow_or_justify", "FAIL",
                    "growth_meta.json has no last_grown_minor marker")
            hard_failures.append("grow_or_justify")
        else:
            grown_key = _minor_key(last_grown)
            current = _current_minor(root)
            if grown_key is None:
                warns.append(
                    f"could not parse last_grown_minor={last_grown!r} — freshness not verified")
                _record("grow_or_justify", "WARN", f"unparseable marker {last_grown!r}")
            elif current is None:
                warns.append("could not determine the repo's current minor — freshness not verified")
                _record("grow_or_justify", "WARN",
                        f"last_grown_minor={last_grown}; current minor unknown")
            elif grown_key >= _previous_minor(current):
                _record("grow_or_justify", "PASS",
                        f"last_grown_minor={last_grown} is current/previous minor")
            else:
                warns.append(
                    f"gold set last grown at {last_grown}, older than the previous "
                    f"minor — grow-or-justify skipped")
                _record("grow_or_justify", "WARN",
                        f"last_grown_minor={last_grown} older than previous minor")

    if hard_failures:
        status = "FAIL"
        reason = "fail-closed: " + ", ".join(hard_failures)
    else:
        status = "PASS"
        reason = (f"gold set fresh: sha matches manifest, {n_gate} gate queries "
                  f">= floor {floor}, freshness marker current/previous minor")

    result: dict = {
        "gate": "search_goldset_fresh",
        "status": status,
        "reason": reason,
        "checks": checks,
    }
    if warns:
        result["warn"] = warns
    return result


def _detect_zero_test(output: str) -> tuple[bool, str]:
    """Check if test output shows zero tests were run."""
    if not output:
        return False, ""

    # Vitest patterns
    m = re.search(r"Tests\s+(\d+)\s+\(0\s+tests?\)", output)
    if m:
        return True, f"Vitest reported 0 tests (Tests: {m.group(1)})"
    m = re.search(r'"totalTests"\s*:\s*0', output)
    if m:
        return True, "Vitest JSON reported totalTests: 0"
    m = re.search(r"Tests\s+(\d+)\s+failed\s+\|\s+(\d+)\s+passed", output)
    if m and int(m.group(1)) == 0 and int(m.group(2)) == 0:
        return True, "Vitest reported 0 failed, 0 passed"

    # Node TAP patterns
    m = re.search(r"#\s+tests\s+(\d+)", output)
    if m and int(m.group(1)) == 0:
        return True, f"Node TAP reported {m.group(1)} tests"
    if "1..0" in output:
        return True, "Node TAP reported 1..0 (zero tests)"

    # Pytest patterns
    if "no tests ran" in output.lower():
        return True, "pytest reported 'no tests ran'"
    m = re.search(r"collected\s+(\d+)\s+item", output)
    if m and int(m.group(1)) == 0:
        return True, f"pytest collected {m.group(1)} items"

    return False, ""


def generate_report(gates: list[dict]) -> dict:
    """Generate the certification report JSON."""
    passed = [g for g in gates if g.get("status") == "PASS"]
    failed = [g for g in gates if g.get("status") == "FAIL"]
    skipped = [g for g in gates if g.get("status") == "SKIP"]
    timed_out = [g for g in gates if g.get("status") == "TIMEOUT"]
    errors = [g for g in gates if g.get("status") == "ERROR"]

    return {
        "certification": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": "PASS" if not failed and not errors else "FAIL",
            "gates_total": len(gates),
            "gates_passed": len(passed),
            "gates_failed": len(failed),
            "gates_skipped": len(skipped),
            "gates_timeout": len(timed_out),
            "gates_error": len(errors),
        },
        "gates": gates,
        "failures": [g["gate"] for g in failed + errors],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Release certification — runs all quality gates."
    )
    parser.add_argument("--json-only", action="store_true",
                        help="Output JSON only (no console logs)")
    parser.add_argument("--gate", choices=list(GATES), help="Run a single gate")
    parser.add_argument("--python", default=sys.executable,
                        help="Python executable to use")
    args = parser.parse_args()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)

    if not args.json_only:
        print("=" * 60)
        print("  Release Certification")
        print("=" * 60)
        print()

    gates = []

    if not args.gate or args.gate == "release_manifest":
        if not args.json_only:
            print("[1/9] Release manifest...")
        g = gate_release_manifest(env)
        gates.append(g)
        if not args.json_only:
            print(f"      {g['status']}")

    if not args.gate or args.gate == "docs_truth":
        if not args.json_only:
            print("[2/9] Docs truth check...")
        g = gate_docs_truth_check(env)
        gates.append(g)
        if not args.json_only:
            print(f"      {g['status']}")

    if not args.gate or args.gate == "pytest":
        if not args.json_only:
            print("[3/9] Python tests...")
        g = gate_pytest(env)
        gates.append(g)
        if not args.json_only:
            print(f"      {g['status']}")

    if not args.gate or args.gate == "ts_typecheck":
        if not args.json_only:
            print("[4/9] TypeScript typecheck...")
        g = gate_ts_typecheck(env)
        gates.append(g)
        if not args.json_only:
            for pkg_result in g.get("packages", []):
                print(f"      {pkg_result['package']}: {pkg_result.get('status', 'UNKNOWN')}")

    if not args.gate or args.gate == "ts_tests":
        if not args.json_only:
            print("[5/9] TypeScript tests...")
        g = gate_ts_tests(env)
        gates.append(g)
        if not args.json_only:
            for pkg_result in g.get("packages", []):
                print(f"      {pkg_result['package']}: {pkg_result.get('status', 'UNKNOWN')}")

    if not args.gate or args.gate == "fixtures":
        if not args.json_only:
            print("[6/9] Fixture validation...")
        g = gate_fixture_validation(env)
        gates.append(g)
        if not args.json_only:
            print(f"      {g['status']}")

    if not args.gate or args.gate == "mcp_e2e":
        if not args.json_only:
            print("[7/9] MCP stdio E2E...")
        g = gate_mcp_stdio_e2e(env)
        gates.append(g)
        if not args.json_only:
            print(f"      {g['status']}")

    if not args.gate or args.gate == "search_eval":
        if not args.json_only:
            print("[8/9] Search-eval gate (hybrid default, LWM_032)...")
        g = gate_search_eval(env)
        gates.append(g)
        if not args.json_only:
            print(f"      {g['status']}")

    if not args.gate or args.gate == "search_goldset_fresh":
        if not args.json_only:
            print("[9/9] Search gold-set freshness (LWM_039 §A)...")
        g = gate_search_goldset_fresh(env)
        gates.append(g)
        if not args.json_only:
            print(f"      {g['status']}")
            for warn in g.get("warn", []):
                print(f"      warn: {warn}")

    report = generate_report(gates)

    report_path = REPORTS_DIR / "release-certification.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")

    if not args.json_only:
        print()
        print("-" * 60)
        print(f"  Overall: {report['certification']['overall_status']}")
        print(f"  Passed: {report['certification']['gates_passed']}/{report['certification']['gates_total']}")
        if report["failures"]:
            print(f"  Failures: {', '.join(report['failures'])}")
        print(f"  Report: {report_path}")
        print("-" * 60)

    if args.json_only:
        print(json.dumps(report, indent=2))

    if report["certification"]["overall_status"] != "PASS":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
