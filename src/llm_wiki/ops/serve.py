"""Start the MCP server for a wiki directory."""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

_child_process = None
_shutdown_signaled = False


def resolve_server_entry(server_path: Path) -> Path:
    """Resolve the MCP server entry point as package.json declares it.

    Reads the ``main`` field (e.g. ``dist/main.js``); falls back to
    ``dist/main.js`` when package.json is missing or unparseable.
    """
    main_field = None
    package_json = server_path / "package.json"
    try:
        main_field = json.loads(package_json.read_text()).get("main")
    except (OSError, ValueError):
        main_field = None
    return server_path / (main_field or "dist/main.js")


def _build_mcp_server(server_path: Path) -> bool:
    """Build the MCP server in place (npm install if needed, then npm run build).

    Returns True on success. On any failure (missing node, failed build,
    npm not on PATH) prints an actionable hint to stderr and returns False.
    """
    if shutil.which("node") is None:
        print(
            "Error: Node.js 18+ is required to build/run the MCP server. "
            "Install Node.js, or run `bash install.sh` to build everything.",
            file=sys.stderr,
        )
        return False

    commands = []
    if not (server_path / "node_modules").exists():
        commands.append(["npm", "install"])
    commands.append(["npm", "run", "build"])

    try:
        for cmd in commands:
            result = subprocess.run(
                cmd, cwd=str(server_path), capture_output=True, text=True
            )
            if result.returncode != 0:
                tail = "\n".join(
                    ((result.stdout or "") + "\n" + (result.stderr or "")).splitlines()[-20:]
                )
                print(
                    f"Error: MCP server build failed (`{' '.join(cmd)}` in {server_path}).\n"
                    f"Build log tail:\n{tail}\n"
                    f"Run: cd {server_path} && npm run build  "
                    f"(or: bash install.sh to build everything)",
                    file=sys.stderr,
                )
                return False
    except FileNotFoundError:
        print(
            "Error: npm is not installed or not in PATH. Node.js 18+ is required "
            "to build/run the MCP server. Install Node.js/npm, or run "
            "`bash install.sh` to build everything.",
            file=sys.stderr,
        )
        return False
    return True


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
    parser.add_argument(
        "--build",
        action="store_true",
        help="Build the MCP server (npm run build in mcp-server) before serving when dist is missing",
    )
    args = parser.parse_args()

    server_path = REPO_ROOT / "mcp-server"
    dist_path = resolve_server_entry(server_path)

    if not dist_path.exists():
        if not args.build:
            print(
                f"Error: MCP server not built — dist/main.js missing at {dist_path}. "
                f"Run: cd {server_path} && npm run build  "
                f"(or: bash install.sh to build everything; llm-wiki setup when available)",
                file=sys.stderr,
            )
            return 1
        if not _build_mcp_server(server_path):
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
