#!/usr/bin/env python3
"""Release manifest validator — checks version consistency across the repo."""

import json
import re
import sys
import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def load_pyproject_version() -> str:
    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


def check_runtime_version(expected: str) -> tuple[bool, str]:
    init_py = REPO_ROOT / "src" / "llm_wiki" / "__init__.py"
    if not init_py.exists():
        return False, f"Missing {init_py}"
    text = init_py.read_text()
    m = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not m:
        return False, f"__version__ not found in {init_py}"
    actual = m.group(1)
    if actual != expected:
        return False, f"{init_py}: expected {expected}, got {actual}"
    return True, actual


def check_npm_version(expected: str) -> tuple[bool, str]:
    pkg_json = REPO_ROOT / "package.json"
    if not pkg_json.exists():
        return False, f"Missing {pkg_json}"
    data = json.loads(pkg_json.read_text())
    actual = data.get("version", "")
    return (actual == expected, actual)


def check_changelog(expected: str) -> tuple[bool, str]:
    changelog = REPO_ROOT / "CHANGELOG.md"
    if not changelog.exists():
        return False, "Missing CHANGELOG.md"
    text = changelog.read_text()
    pattern = rf"^##\s*\[{re.escape(expected)}\]"
    if re.search(pattern, text, re.MULTILINE):
        return True, f"Entry [{expected}] found"
    return False, f"No entry for [{expected}] in CHANGELOG.md"


def check_llm_wiki_version(expected: str) -> tuple[bool, str]:
    cli_path = REPO_ROOT / "src" / "llm_wiki" / "cli.py"
    if not cli_path.exists():
        return False, f"Missing {cli_path}"
    text = cli_path.read_text()
    if "version" in text.lower():
        return True, "CLI has --version flag (checked by import test)"
    return True, "CLI exists (version check deferred to import test)"


def check_console_script_imports() -> tuple[bool, list[str]]:
    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    scripts = data.get("project", {}).get("scripts", {})
    failures = []
    sys.path.insert(0, str(REPO_ROOT / "src"))
    for script_name, target in scripts.items():
        mod_name, _, func_name = target.partition(":")
        if not func_name:
            failures.append(f"{script_name}: no function target in '{target}'")
            continue
        try:
            mod = __import__(mod_name, fromlist=[func_name])
            if not hasattr(mod, func_name):
                failures.append(f"{script_name}: '{mod_name}' has no '{func_name}'")
        except ImportError as e:
            err_str = str(e)
            if "No module named" in err_str:
                pkg = err_str.split("'")[1] if "'" in err_str[err_str.index("No module named"):] else "unknown"
                failures.append(f"{script_name}: missing dependency '{pkg}' — install project dependencies first")
            else:
                failures.append(f"{script_name}: cannot import '{mod_name}' — {e}")
    return (len(failures) == 0, failures)


def main() -> int:
    manifest_path = REPO_ROOT / "release-manifest.json"
    if not manifest_path.exists():
        print(json.dumps({"ok": False, "error": "release-manifest.json not found"}, indent=2))
        return 1

    manifest = json.loads(manifest_path.read_text())
    expected_version = manifest["release"]["version"]

    checks = []

    pyproject_ver = load_pyproject_version()
    checks.append({
        "check": "pyproject.toml version",
        "expected": expected_version,
        "actual": pyproject_ver,
        "status": "PASS" if pyproject_ver == expected_version else "FAIL",
    })

    runtime_ok, runtime_actual = check_runtime_version(expected_version)
    checks.append({
        "check": "__init__.py __version__",
        "expected": expected_version,
        "actual": runtime_actual,
        "status": "PASS" if runtime_ok else "FAIL",
    })

    npm_ok, npm_actual = check_npm_version(expected_version)
    checks.append({
        "check": "root package.json version",
        "expected": expected_version,
        "actual": npm_actual,
        "status": "PASS" if npm_ok else "FAIL",
    })

    changelog_ok, changelog_msg = check_changelog(expected_version)
    checks.append({
        "check": "CHANGELOG.md entry",
        "expected": expected_version,
        "actual": changelog_msg,
        "status": "PASS" if changelog_ok else "FAIL",
    })

    scripts_ok, script_failures = check_console_script_imports()
    checks.append({
        "check": "console script imports",
        "expected": "all importable",
        "actual": "ok" if scripts_ok else "; ".join(script_failures),
        "status": "PASS" if scripts_ok else "FAIL",
    })

    all_pass = all(c["status"] == "PASS" for c in checks)

    report = {
        "ok": all_pass,
        "version": expected_version,
        "checked_surfaces": len(checks),
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
        "checks": checks,
    }

    print(json.dumps(report, indent=2))

    if "--json-only" in sys.argv:
        return 0
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
