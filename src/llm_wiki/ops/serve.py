"""Start the MCP server for a wiki directory."""

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

_child_process = None
_shutdown_signaled = False


def _signal_handler(signum, frame):
    global _shutdown_signaled
    _shutdown_signaled = True
    if _child_process is not None and _child_process.poll() is None:
        _child_process.send_signal(signum)


def _shutdown_child():
    if _child_process is None or _child_process.poll() is not None:
        return
    try:
        _child_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _child_process.kill()
        _child_process.wait()


def main() -> int:
    global _child_process

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

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    try:
        _child_process = subprocess.Popen(cmd, cwd=str(server_path))

        while _child_process.poll() is None:
            if _shutdown_signaled:
                break
            time.sleep(0.5)

        _shutdown_child()
        return _child_process.returncode or 0
    except KeyboardInterrupt:
        if _child_process is not None and _child_process.poll() is None:
            _child_process.send_signal(signal.SIGINT)
            _shutdown_child()
        return 0
    except FileNotFoundError:
        print("Error: node is not installed or not in PATH", file=sys.stderr)
        return 1
