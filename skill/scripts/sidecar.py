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

# Ensure import paths for package modules
_PACKAGE_DIR = str(Path(__file__).resolve().parents[2] / "src")
if _PACKAGE_DIR not in sys.path:
    sys.path.insert(0, _PACKAGE_DIR)

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
        from llm_wiki.lint_wiki import lint_files
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
        from llm_wiki.ingest import ingest
    except ImportError as e:
        return {"error": f"ingest module not available: {e}"}

    wiki_root = params.get("wiki_root", WIKI_ROOT)
    source_path = params.get("source_path", "")
    if not source_path:
        return {"error": "missing required parameter: source_path"}

    options = params.get("options", {})
    return ingest(
        wiki_root=wiki_root,
        source_path=source_path,
        **options,
    )


@register("suggest_links")
def handle_suggest_links(params: dict) -> dict:
    """Suggest missing wikilinks for wiki pages. Uses link_suggest.py."""
    try:
        from llm_wiki.link_suggest import (
            load_pages,
            build_entity_registry,
            build_inverted_index,
            generate_suggestions,
        )
    except ImportError as e:
        return {"error": f"link_suggest module not available: {e}"}

    try:
        from llm_wiki.core.layout import discover_layout
    except ImportError as e:
        return {"error": f"discover module not available: {e}"}

    root = params.get("wiki_root", WIKI_ROOT)
    if not root:
        return {"error": "missing required parameter: wiki_root"}

    threshold = params.get("threshold", 0.3)
    limit = params.get("limit", 20)
    requested_pages = params.get("pages")  # None means all pages

    layout = discover_layout(root)
    wiki_dir = Path(layout.pages_dir)
    if not wiki_dir.is_dir():
        return {"error": f"Pages directory not found: {wiki_dir}"}

    skip_files = frozenset(f"{stem}.md" for stem in layout.skip_stems)
    pages = load_pages(wiki_dir, skip_files)

    if requested_pages:
        # Filter pages to only those requested (match by stem)
        requested_stems = set(requested_pages)
        pages = {
            stem: data
            for stem, data in pages.items()
            if stem in requested_stems
        }

    if not pages:
        return {"suggestions": [], "total": 0}

    registry = build_entity_registry(pages)
    if not registry:
        return {"suggestions": [], "total": 0}

    inverted = build_inverted_index(pages, registry)
    suggestions = generate_suggestions(
        pages, registry, wiki_dir, limit, threshold
    )

    # Strip Path objects for JSON serialization
    clean_suggestions = []
    for s in suggestions:
        clean_suggestions.append({
            "source": str(s["source"]),
            "source_stem": s["source_stem"],
            "source_title": s["source_title"],
            "source_type": s["source_type"],
            "target": str(s["target"]),
            "target_stem": s["target_stem"],
            "target_title": s["target_title"],
            "target_type": s["target_type"],
            "entity": s["entity"],
            "score": s["score"],
            "reason": s["reason"],
        })

    return {"suggestions": clean_suggestions, "total": len(clean_suggestions)}


@register("backup")
def handle_backup(params: dict) -> dict:
    """Create a timestamped snapshot backup of the wiki. Uses backup.py."""
    import io
    import contextlib

    try:
        from llm_wiki.backup import cmd_snapshot, snapshot_path, backups_dir
    except ImportError as e:
        return {"error": f"backup module not available: {e}"}

    root = params.get("wiki_root", WIKI_ROOT)
    if not root:
        return {"error": "missing required parameter: wiki_root"}

    root_path = Path(root).resolve()
    if not root_path.is_dir():
        return {"error": f"Wiki root is not a directory: {root}"}

    # Determine snapshot path before running (cmd_snapshot prints to stdout)
    dest = snapshot_path(root_path)

    # Run snapshot, capturing stdout to avoid JSON-RPC pollution
    stdout_capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout_capture):
            exit_code = cmd_snapshot(root_path)
    except Exception as e:
        return {"error": f"Snapshot failed: {e}"}

    if exit_code != 0:
        return {
            "error": "Snapshot failed",
            "output": stdout_capture.getvalue().strip(),
        }

    if not dest.exists():
        return {"error": f"Snapshot file not found after creation: {dest}"}

    size_bytes = dest.stat().st_size

    # Verify integrity: check the archive is readable
    import tarfile as tarfile_mod
    integrity = "unknown"
    file_count = 0
    try:
        if tarfile_mod.is_tarfile(str(dest)):
            with tarfile_mod.open(str(dest), "r:gz") as tar:
                file_count = sum(1 for m in tar if m.isfile())
            integrity = "valid"
        else:
            integrity = "invalid"
    except Exception:
        integrity = "unverifiable"

    return {
        "archive_path": str(dest),
        "size_bytes": size_bytes,
        "file_count": file_count,
        "integrity": integrity,
    }


@register("discover_entities")
def handle_discover_entities(params: dict) -> dict:
    """Discover all entities registered in the wiki. Uses link_suggest.py registry builder."""
    try:
        from llm_wiki.link_suggest import load_pages, build_entity_registry
    except ImportError as e:
        return {"error": f"link_suggest module not available: {e}"}

    try:
        from llm_wiki.core.layout import discover_layout
    except ImportError as e:
        return {"error": f"discover module not available: {e}"}

    root = params.get("wiki_root", WIKI_ROOT)
    if not root:
        return {"error": "missing required parameter: wiki_root"}

    entity_type = params.get("entity_type")  # None means all

    layout = discover_layout(root)
    wiki_dir = Path(layout.pages_dir)
    if not wiki_dir.is_dir():
        return {"error": f"Pages directory not found: {wiki_dir}"}

    skip_files = frozenset(f"{stem}.md" for stem in layout.skip_stems)
    pages = load_pages(wiki_dir, skip_files)

    if not pages:
        return {"entities": [], "total": 0}

    registry = build_entity_registry(pages)

    entities = []
    for key, entry in registry.items():
        entity = {
            "name": entry["original"],
            "stem": entry["target_stem"],
            "title": entry["target_title"],
            "type": entry["target_type"],
        }

        # Add aliases: all keys that map to the same target_stem
        aliases = [
            k for k, e in registry.items()
            if e["target_stem"] == entry["target_stem"] and k != key
        ]
        if aliases:
            entity["aliases"] = aliases

        entities.append(entity)

    if entity_type:
        entities = [e for e in entities if e.get("type") == entity_type]

    entities.sort(key=lambda e: e["name"].lower())

    return {"entities": entities, "total": len(entities)}


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
