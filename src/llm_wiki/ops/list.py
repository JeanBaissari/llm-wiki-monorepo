#!/usr/bin/env python3
"""ops — Operation management commands."""
import argparse
import json
import sys
from pathlib import Path


def _format_table(manifests):
    header = f"{'Op ID':<10} {'Command':<15} {'Status':<12} {'Started':<20} {'Paths':<8}"
    sep = "-" * len(header)
    lines = [sep, header, sep]
    for m in manifests:
        op_id = m.get("operation_id", "")[:8]
        cmd = m.get("command", "")[:14]
        status = m.get("status", "?")[:11]
        started = m.get("started", "")[:19]
        paths = str(len(m.get("touched_paths", [])))
        lines.append(f"{op_id:<10} {cmd:<15} {status:<12} {started:<20} {paths:<8}")
    lines.append(sep)
    return "\n".join(lines)


def cmd_list(wiki_root: str, limit: int = 20, status: str = "all", as_json: bool = False) -> int:
    """List completed operation manifests."""
    dirs_to_check = []
    if status in ("completed", "all"):
        d = Path(wiki_root) / ".llm-wiki" / "operations" / "completed"
        if d.exists():
            dirs_to_check.append(("completed", d))
    if status in ("failed", "all"):
        d = Path(wiki_root) / ".llm-wiki" / "operations" / "failed"
        if d.exists():
            dirs_to_check.append(("failed", d))

    manifests = []
    for _status, d in dirs_to_check:
        for f in sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(f.read_text())
                if "status" not in data:
                    data["status"] = _status
                manifests.append(data)
            except json.JSONDecodeError:
                pass

    if not manifests:
        print("No operations found.")
        return 0

    manifests.sort(key=lambda m: m.get("started", ""), reverse=True)
    manifests = manifests[:limit]

    if as_json:
        print(json.dumps(manifests, indent=2, default=str))
    else:
        print(_format_table(manifests))
        print(f"\n{len(manifests)} operation(s) shown.")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Operation management for LLM Wiki.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  llm-wiki ops list ~/my-wiki\n  llm-wiki ops list ~/my-wiki --json --limit 5",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand")

    list_parser = subparsers.add_parser("list", help="List completed operation manifests")
    list_parser.add_argument("wiki_root", help="Path to the wiki root directory")
    list_parser.add_argument("--limit", type=int, default=20, help="Max operations to show")
    list_parser.add_argument("--status", choices=["completed", "failed", "all"], default="all")
    list_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.subcommand == "list":
        return cmd_list(args.wiki_root, args.limit, args.status, args.json)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
