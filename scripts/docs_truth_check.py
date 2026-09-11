#!/usr/bin/env python3
"""Docs truth checker — validates documentation against source registries.

Scans the live user-facing docs for stale surface-count claims (MCP tools,
CLI commands, templates, skill scripts) and fails when a source registry
drifts from its expected size. Both ``--json-only`` and the default mode emit
the same machine-readable report and exit nonzero on failure.
"""

import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent

# Expected registry sizes. A drift here means the docs must be swept for the
# old count — the checker fails on the registry itself, not just the docs.
EXPECTED_COUNTS = {
    "mcp_tools": 15,
    "cli_commands": 27,
    "templates": 20,
    "scripts": 26,
}

# Historical/audit documents that describe past states are exempt.
EXCLUDED_REFERENCE_DOCS = {
    "prd-implementation-path.md",
    "production-readiness-audit.md",
}

# Always-scanned live docs. Every other docs/reference/*.md is scanned too.
FIXED_DOCS = (
    "README.md",
    "USAGE.md",
    "AGENTS.md",
    "docs/contributing.md",
    "docs/getting-started/quickstart.md",
    "skill/SKILL.md",
    "skill/references/examples-and-workflows.md",
)

# registry -> (count-claim regex, minimum plausible count). The minimum
# filters incidental numbers, e.g. README's "7 templates previously created
# wrong directories" — that is a bugfix note, not a registry claim.
CLAIM_PATTERNS = {
    "mcp_tools": (re.compile(r"(\d+)[\s-]+(?:MCP\s+)?tools?\b(?!\s+handler)", re.IGNORECASE), 4),
    "cli_commands": (re.compile(r"(\d+)[\s-]+(?:CLI\s+)?(?:commands?|cmds?)\b", re.IGNORECASE), 5),
    "templates": (re.compile(r"(\d+)[\s-]+(?:domain\s+)?templates?\b", re.IGNORECASE), 10),
    "scripts": (re.compile(r"(\d+)[\s-]+(?:skill\s+)?scripts?\b", re.IGNORECASE), 10),
}

REGISTRY_LABELS = {
    "mcp_tools": "MCP tools",
    "cli_commands": "CLI commands",
    "templates": "templates",
    "scripts": "skill scripts",
}


def discover_mcp_tools() -> list[str]:
    index_path = REPO_ROOT / "mcp-server" / "src" / "registry.ts"
    text = index_path.read_text()
    start = text.index("const TOOL_DEFINITIONS")
    end = text.index("];", start) + 2
    block = text[start:end]
    return re.findall(r'name:\s*"([^"]+)"', block)


def discover_cli_commands() -> list[str]:
    cli_path = REPO_ROOT / "src" / "llm_wiki" / "cli.py"
    text = cli_path.read_text()
    m = re.search(r"COMMANDS\s*=\s*\{([^}]+)\}", text, re.DOTALL)
    if not m:
        return []
    return re.findall(r'"([^"]+)"\s*:', m.group(1))


def discover_templates() -> list[str]:
    templates_dir = REPO_ROOT / "templates"
    return sorted(
        d.name for d in templates_dir.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    )


def discover_scripts() -> list[str]:
    scripts_dir = REPO_ROOT / "skill" / "scripts"
    return sorted(p.name for p in scripts_dir.glob("*.py"))


def doc_files() -> list[Path]:
    files = [REPO_ROOT / rel for rel in FIXED_DOCS]
    reference_dir = REPO_ROOT / "docs" / "reference"
    files.extend(
        p for p in sorted(reference_dir.glob("*.md"))
        if p.name not in EXCLUDED_REFERENCE_DOCS
    )
    # De-duplicate while preserving order.
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in files:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def check_doc_claims(doc_path: Path, registry_counts: dict[str, int]) -> list[dict]:
    """Return one check entry per registry with stale claims in this doc."""
    text = doc_path.read_text()
    rel = str(doc_path.relative_to(REPO_ROOT)) if doc_path.is_relative_to(REPO_ROOT) else doc_path.name
    checks = []

    for registry, (pattern, min_count) in CLAIM_PATTERNS.items():
        expected = registry_counts[registry]
        issues: list[str] = []
        for match in pattern.finditer(text):
            claimed = int(match.group(1))
            if claimed < min_count or claimed == expected:
                continue
            issues.append(
                f"{rel}: claims {claimed} {REGISTRY_LABELS[registry]}, actual is {expected}"
            )
        if issues:
            checks.append({
                "file": rel,
                "registry": registry,
                "expected_count": expected,
                "issues": sorted(set(issues)),
            })

    return checks


def main() -> int:
    mcp_tools = discover_mcp_tools()
    cli_commands = discover_cli_commands()
    template_names = discover_templates()
    script_names = discover_scripts()

    registry_counts = {
        "mcp_tools": len(mcp_tools),
        "cli_commands": len(cli_commands),
        "templates": len(template_names),
        "scripts": len(script_names),
    }

    report = {
        "ok": True,
        "expected_counts": EXPECTED_COUNTS,
        "registries": {
            "mcp_tools": {"count": len(mcp_tools), "names": mcp_tools},
            "cli_commands": {"count": len(cli_commands), "names": cli_commands},
            "templates": {"count": len(template_names), "names": template_names},
            "scripts": {"count": len(script_names), "names": script_names},
        },
        "doc_checks": [],
        "failures": [],
    }

    for registry, expected in EXPECTED_COUNTS.items():
        actual = registry_counts[registry]
        if actual != expected:
            report["failures"].append(
                f"{registry} registry drift: expected {expected}, discovered {actual}"
            )

    for doc_path in doc_files():
        if not doc_path.exists():
            rel = doc_path.relative_to(REPO_ROOT)
            report["failures"].append(f"Missing doc file: {rel}")
            continue
        checks = check_doc_claims(doc_path, registry_counts)
        report["doc_checks"].extend(checks)
        for check in checks:
            report["failures"].extend(check["issues"])

    if report["failures"]:
        report["ok"] = False

    print(json.dumps(report, indent=2))

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
