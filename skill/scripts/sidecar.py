#!/usr/bin/env python3
"""
JSON-RPC 2.0 Sidecar for the TypeScript MCP Server.

Reads JSON-RPC requests from stdin, dispatches to registered handlers,
writes JSON-RPC responses to stdout. One request/response per line.

Run by the MCP server at startup; stays alive for the server's lifetime.

Startup config: wiki_root is passed via LLM_WIKI_ROOT env var,
set to layout.root at sidecar initialization.
"""

import sys
import json
import os
import traceback
import signal
import shutil
from pathlib import Path
from typing import Any, Callable

# ── Startup config ──────────────────────────────────────────────────────────
WIKI_ROOT = os.environ.get("LLM_WIKI_ROOT", "")
SIDECAR_TMP = os.path.join(WIKI_ROOT, ".sidecar-tmp") if WIKI_ROOT else ""

# ── Crash cleanup ───────────────────────────────────────────────────────────
# Clean up any leftover temp directory from a previous crash
if SIDECAR_TMP and os.path.isdir(SIDECAR_TMP):
    try:
        shutil.rmtree(SIDECAR_TMP)
        sys.stderr.write(f"[sidecar] Cleaned leftover temp dir: {SIDECAR_TMP}\n")
        sys.stderr.flush()
    except Exception:
        pass

# Ensure import paths for sibling scripts
_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

# ── Handler Registry ─────────────────────────────────────────────────────────
handlers: dict[str, Callable[[dict], Any]] = {}


def register(method: str):
    """Decorator to register a handler function."""
    def decorator(fn: Callable[[dict], Any]):
        handlers[method] = fn
        return fn
    return decorator


# ── Built-in Handlers ───────────────────────────────────────────────────────

@register("health")
def handle_health(params: dict) -> dict:
    """Health check — confirms sidecar is alive and responsive."""
    return {"status": "ok", "wiki_root": WIKI_ROOT}


@register("lint_wiki")
def handle_lint_wiki(params: dict) -> dict:
    """Run lint checks on wiki pages. Dynamic import for graceful fallback."""
    try:
        from lint_wiki import lint_files
    except ImportError as e:
        return {"error": f"lint_wiki module not available: {e}"}

    root = params.get("wiki_root", WIKI_ROOT)
    return lint_files(
        root=root,
        paths=params.get("paths", []),
        fix=params.get("fix", False),
        check_broken_links=params.get("check_broken_links", True),
    )


@register("ingest_source")
def handle_ingest(params: dict) -> dict:
    """Ingest a source file into the wiki. Dynamic import for graceful fallback."""
    try:
        from ingest import ingest_source
    except ImportError as e:
        return {"error": f"ingest module not available: {e}"}

    wiki_root = params.get("wiki_root", WIKI_ROOT)
    source_path = params.get("source_path", "")
    if not source_path:
        return {"error": "missing required parameter: source_path"}

    options = params.get("options", {})
    return ingest_source(
        wiki_root=wiki_root,
        source_path=source_path,
        **options,
    )


# ── Main Loop ───────────────────────────────────────────────────────────────

def main():
    """Main loop: read JSON-RPC requests from stdin, dispatch, write responses."""
    # Signal handlers for graceful shutdown
    running = True

    def _handle_signal(signum, frame):
        nonlocal running
        running = False
        sys.stderr.write(f"[sidecar] Received signal {signum}, shutting down\n")
        sys.stderr.flush()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    # Write ready signal so TypeScript side can detect startup
    sys.stderr.write("[sidecar] JSON-RPC sidecar started\n")
    sys.stderr.flush()

    for line in sys.stdin:
        if not running:
            break

        line = line.strip()
        if not line:
            continue

        req_id = None
        try:
            request = json.loads(line)
            req_id = request.get("id")
            method = request.get("method", "")
            params = request.get("params", {})

            if method not in handlers:
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }
            else:
                result = handlers[method](params)
                response = {"jsonrpc": "2.0", "id": req_id, "result": result}

        except json.JSONDecodeError as e:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"},
            }
        except Exception as e:
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32000,
                    "message": str(e),
                    "data": traceback.format_exc(),
                },
            }

        sys.stdout.write(json.dumps(response, default=str) + "\n")
        sys.stdout.flush()

    sys.stderr.write("[sidecar] Shutdown complete\n")
    sys.stderr.flush()


if __name__ == "__main__":
    main()
