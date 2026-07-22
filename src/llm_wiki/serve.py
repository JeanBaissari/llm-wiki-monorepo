"""Start the MCP server for a wiki directory."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the MCP server for a wiki directory")
    parser.add_argument("wiki", help="Path to wiki directory")
    parser.add_argument("--projects", help="Semicolon-separated project names (multi-wiki mode)")
    args = parser.parse_args()

    server_path = REPO_ROOT / "mcp-server"
    dist_path = server_path / "dist" / "index.js"

    if not dist_path.exists():
        print(
            f"Error: MCP server not built. dist/ not found at {dist_path}",
            file=sys.stderr,
        )
        print(
            f"Run: cd {server_path} && npm run build",
            file=sys.stderr,
        )
        return 1

    cmd = ["node", str(dist_path), "--wiki", args.wiki]
    if args.projects:
        cmd.extend(["--projects", args.projects])

    try:
        result = subprocess.run(cmd, cwd=str(server_path))
        return result.returncode
    except KeyboardInterrupt:
        return 0
    except FileNotFoundError:
        print("Error: node is not installed or not in PATH", file=sys.stderr)
        return 1
