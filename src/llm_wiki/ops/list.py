#!/usr/bin/env python3
"""ops list — List completed operation manifests."""
import argparse
import json
import os
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List completed operation manifests.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  llm-wiki ops list ~/my-wiki\n  llm-wiki ops list ~/my-wiki --json --limit 5",
    )
    parser.add_argument("wiki_root", help="Path to the wiki root directory")
    parser.add_argument("--limit", type=int, default=20, help="Max operations to show")
    parser.add_argument("--status", choices=["completed", "failed", "all"], default="all")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    manifest_dir = Path(args.wiki_root) / ".llm-wiki" / "operations" / "completed"
    if not manifest_dir.exists() and args.status == "completed":
        print("No completed operations found.")
        return 0

    # Gather manifests from completed dir (and failed dir if requested)
    manifests = []
    dirs_to_check = []
    if args.status in ("completed", "all"):
        completed = Path(args.wiki_root) / ".llm-wiki" / "operations" / "completed"
        if completed.exists():
            dirs_to_check.append(("completed", completed))
    if args.status in ("failed", "all"):
        failed = Path(args.wiki_root) / ".llm-wiki" / "operations" / "failed"
        if failed.exists():
            dirs_to_check.append(("failed", failed))

    for status, d in dirs_to_check:
        for f in d.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                if "status" not in data:
                    data["status"] = status
                manifests.append(data)
            except json.JSONDecodeError:
                pass

    manifests.sort(key=lambda m: m.get("started", ""), reverse=True)
    manifests = manifests[:args.limit]

    if not manifests:
        print("No operations found.")
        return 0

    if args.json:
        print(json.dumps(manifests, indent=2, default=str))
    else:
        print(_format_table(manifests))
        print(f"\n{len(manifests)} operation(s) shown.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
