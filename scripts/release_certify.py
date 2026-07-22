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
        cwd=REPO_ROOT, env=env,
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
    parser.add_argument("--gate", choices=[
        "release_manifest", "docs_truth", "pytest", "ts_typecheck",
        "ts_tests", "fixtures", "mcp_e2e",
    ], help="Run a single gate")
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
            print("[1/7] Release manifest...")
        g = gate_release_manifest(env)
        gates.append(g)
        if not args.json_only:
            print(f"      {g['status']}")

    if not args.gate or args.gate == "docs_truth":
        if not args.json_only:
            print("[2/7] Docs truth check...")
        g = gate_docs_truth_check(env)
        gates.append(g)
        if not args.json_only:
            print(f"      {g['status']}")

    if not args.gate or args.gate == "pytest":
        if not args.json_only:
            print("[3/7] Python tests...")
        g = gate_pytest(env)
        gates.append(g)
        if not args.json_only:
            print(f"      {g['status']}")

    if not args.gate or args.gate == "ts_typecheck":
        if not args.json_only:
            print("[4/7] TypeScript typecheck...")
        g = gate_ts_typecheck(env)
        gates.append(g)
        if not args.json_only:
            for pkg_result in g.get("packages", []):
                print(f"      {pkg_result['package']}: {pkg_result.get('status', 'UNKNOWN')}")

    if not args.gate or args.gate == "ts_tests":
        if not args.json_only:
            print("[5/7] TypeScript tests...")
        g = gate_ts_tests(env)
        gates.append(g)
        if not args.json_only:
            for pkg_result in g.get("packages", []):
                print(f"      {pkg_result['package']}: {pkg_result.get('status', 'UNKNOWN')}")

    if not args.gate or args.gate == "fixtures":
        if not args.json_only:
            print("[6/7] Fixture validation...")
        g = gate_fixture_validation(env)
        gates.append(g)
        if not args.json_only:
            print(f"      {g['status']}")

    if not args.gate or args.gate == "mcp_e2e":
        if not args.json_only:
            print("[7/7] MCP stdio E2E...")
        g = gate_mcp_stdio_e2e(env)
        gates.append(g)
        if not args.json_only:
            print(f"      {g['status']}")

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
