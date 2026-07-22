#!/usr/bin/env python3
"""Docs truth checker — validates documentation against source registries."""

import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def discover_mcp_tools() -> list[str]:
    index_path = REPO_ROOT / "mcp-server" / "src" / "index.ts"
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
    dirs = sorted(d.name for d in templates_dir.iterdir() if d.is_dir() and not d.name.startswith("_"))
    return dirs


def count_text_occurrences(file_path: Path, pattern: str) -> int:
    text = file_path.read_text()
    return len(re.findall(pattern, text))


def check_tool_count_in_doc(doc_path: Path, tools_in_mcp: list[str]) -> dict:
    text = doc_path.read_text()
    mcp_tool_count = len(tools_in_mcp)
    issues = []

    count_patterns = [
        rf"{mcp_tool_count}\s*(MCP\s+)?tools?",
        rf"{mcp_tool_count}\s*(MCP\s+)?tool",
    ]
    found_exact = False
    for p in count_patterns:
        if re.search(p, text, re.IGNORECASE):
            found_exact = True
            break

    if not found_exact:
        for n in [8, 10, 11]:
            if re.search(rf"{n}\s*(MCP\s+)?tools?", text, re.IGNORECASE):
                issues.append(f"Claims {n} MCP tools, actual is {mcp_tool_count}")

    return {"file": str(doc_path.relative_to(REPO_ROOT)), "expected_count": mcp_tool_count, "issues": issues}


def check_template_count_in_doc(doc_path: Path, template_names: list[str]) -> dict:
    text = doc_path.read_text()
    count = len(template_names)
    issues = []

    for claimed in [19]:
        if re.search(rf"{claimed}\s*(domain\s+)?templates?", text, re.IGNORECASE):
            issues.append(f"Claims {claimed} templates, actual is {count}")
            break

    return {"file": str(doc_path.relative_to(REPO_ROOT)), "expected_count": count, "issues": issues}


def main() -> int:
    mcp_tools = discover_mcp_tools()
    cli_commands = discover_cli_commands()
    template_names = discover_templates()

    report = {
        "ok": True,
        "registries": {
            "mcp_tools": {"count": len(mcp_tools), "names": mcp_tools},
            "cli_commands": {"count": len(cli_commands), "names": cli_commands},
            "templates": {"count": len(template_names), "names": template_names},
        },
        "doc_checks": [],
        "failures": [],
    }

    doc_files = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / "INDEX.md",
        REPO_ROOT / "QUICKGUIDE.md",
    ]

    for doc_path in doc_files:
        if not doc_path.exists():
            report["failures"].append(f"Missing doc file: {doc_path.name}")
            continue

        tool_check = check_tool_count_in_doc(doc_path, mcp_tools)
        if tool_check["issues"]:
            report["doc_checks"].append(tool_check)
            report["failures"].extend(tool_check["issues"])

        tpl_check = check_template_count_in_doc(doc_path, template_names)
        if tpl_check["issues"]:
            report["doc_checks"].append(tpl_check)
            report["failures"].extend(tpl_check["issues"])

    if report["failures"]:
        report["ok"] = False

    print(json.dumps(report, indent=2))

    if "--json-only" in sys.argv:
        return 0
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
