#!/usr/bin/env python3
"""Zero-test guard — fails if a package test command runs zero tests."""

import json
import re
import subprocess
import sys
from pathlib import Path


def detect_zero_test(output: str, runner: str = "auto") -> tuple[bool, str]:
    if runner in ("vitest", "auto"):
        if re.search(r"Tests\s+\d+\s+\(0\s+tests?\)", output):
            return True, "Vitest reported 0 tests"
        m = re.search(r"Tests\s+(\d+)", output)
        if m and int(m.group(1)) == 0:
            return True, f"Vitest reported {m.group(1)} tests"
        m = re.search(r'"totalTests"\s*:\s*(\d+)', output)
        if m and int(m.group(1)) == 0:
            return True, f"Vitest JSON reported {m.group(1)} tests"

    if runner in ("node", "auto"):
        m = re.search(r"#\s+tests\s+(\d+)", output)
        if m and int(m.group(1)) == 0:
            return True, f"Node TAP reported {m.group(1)} tests"
        if "1..0" in output:
            return True, "Node TAP reported 1..0 (zero tests)"
        m = re.search(r"tests\s+(\d+)", output, re.IGNORECASE)
        if m and int(m.group(1)) == 0:
            return True, f"Node reported {m.group(1)} tests"

    if runner in ("pytest", "auto"):
        if "no tests ran" in output.lower():
            return True, "pytest reported 'no tests ran'"
        m = re.search(r"collected\s+(\d+)\s+item", output)
        if m and int(m.group(1)) == 0:
            return True, f"pytest collected {m.group(1)} items"
        m = re.search(r"(\d+)\s+passed", output)
        if not m:
            m = re.search(r"(\d+)\s+failed", output)
        if not m:
            m = re.search(r"(\d+)\s+error", output)
        if m is None and "==" in output and "passed" not in output and "failed" not in output:
            return True, "pytest output has no test results"

    return False, ""


def run_test(package_path: Path, test_command: list[str], timeout: int = 60) -> dict:
    try:
        result = subprocess.run(
            test_command,
            cwd=package_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        return {"package": package_path.name, "status": "TIMEOUT", "tests_run": 0,
                "zero_test": True, "evidence": "Command timed out"}
    except FileNotFoundError as e:
        return {"package": package_path.name, "status": "MISSING_BINARY",
                "tests_run": 0, "zero_test": True, "evidence": str(e)}

    is_zero, evidence = detect_zero_test(output)
    return {
        "package": package_path.name,
        "status": "PASS" if exit_code == 0 else "FAIL",
        "tests_run": 0 if is_zero else -1,
        "zero_test": is_zero,
        "evidence": evidence if is_zero else "",
        "exit_code": exit_code,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Zero-test guard for package tests")
    parser.add_argument("--report", type=str, help="Path to write JSON report")
    parser.add_argument("--packages", type=str, nargs="*", default=[],
                        help="Package paths to check (relative to repo root)")
    parser.add_argument("--test-command", type=str, default="npm test",
                        help="Test command to run (default: npm test)")
    parser.add_argument("--allow-zero", type=str, nargs="*", default=[],
                        help="Package names where zero tests are allowed")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    results = []
    overall_ok = True

    packages_to_check = args.packages or [
        "graph-engine",
        "mcp-server",
        "audit-shared",
    ]

    for pkg in packages_to_check:
        pkg_path = repo_root / pkg
        if not pkg_path.is_dir():
            results.append({"package": pkg, "status": "SKIP", "reason": "Directory not found"})
            continue

        test_cmd = args.test_command.split()
        result = run_test(pkg_path, test_cmd)

        if result["zero_test"]:
            if pkg not in args.allow_zero:
                result["status"] = "ZERO_TEST_FAIL"
                overall_ok = False
        elif result["status"] == "FAIL":
            overall_ok = False

        results.append(result)

    report = {"ok": overall_ok, "results": results}
    print(json.dumps(report, indent=2))

    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2))

    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
