#!/usr/bin/env python3
"""
demo.py — Materialize the committed demo wiki playground.

Copies the byte-deterministic "Redis Internals" demo fixture (packaged with the
library at ``llm_wiki/wiki/demo_wiki``) to a target directory so a first-run user
can search, lint, summarize, serve, and ask against a real, cross-linked wiki in
seconds — no LLM calls, no content authoring.

Usage:
    llm-wiki demo <dest> [--force] [--json]

Examples:
    llm-wiki demo /tmp/redis-demo
    llm-wiki demo ~/playground/redis-demo --force

Behavior:
    - Resolves the fixture from the installed package first, then the repo
      checkout (mirrors ``scaffold.py``'s template resolution).
    - Copies recursively with git-copy semantics (no symlinks).
    - Refuses to overwrite an existing non-empty <dest> (exit 1) unless
      ``--force``, mirroring ``scaffold.py``'s refusal semantics.
    - Regenerates caches in place: the FTS5 search index via ``index_wiki``
      (pure Python, always), and ``graph-data.json`` via the graph engine only
      when ``graph-engine/dist/index.js`` exists — a base install never requires
      node; without it a clear hint is printed and the command continues.
    - Prints next-step commands and, with ``--json``, the dest + page count.

Exit codes:
    0 — success
    1 — refused (non-empty dest without --force) or runtime error
    2 — usage error / fixture unavailable
"""

import io
import json
import shutil
import subprocess
import sys
import contextlib
from pathlib import Path

from llm_wiki.core.layout import discover_layout
from llm_wiki.search.index import index_wiki


# Try multiple locations: installed package, then dev repo (mirrors scaffold.py).
_D = Path(__file__).resolve().parent / "demo_wiki"
DEMO_WIKI_DIR = _D if _D.is_dir() else Path(__file__).resolve().parent.parent.parent.parent / "src" / "llm_wiki" / "wiki" / "demo_wiki"


def demo_source() -> Path:
    """Return the committed demo fixture directory."""
    if not DEMO_WIKI_DIR.is_dir():
        raise FileNotFoundError(
            f"Demo wiki fixture not found at {DEMO_WIKI_DIR} "
            f"(install the package or run from the repo checkout)"
        )
    return DEMO_WIKI_DIR


def _graph_engine_js() -> Path | None:
    """Locate the graph-engine CLI entry, or None when the dist is absent."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    js = repo_root / "graph-engine" / "dist" / "index.js"
    return js if js.is_file() else None


def _count_pages(wiki_root: Path) -> int:
    """Count .md pages under the discovered pages directory."""
    layout = discover_layout(str(wiki_root))
    pages_dir = Path(layout.pages_dir)
    if not pages_dir.is_dir():
        return 0
    return len(list(pages_dir.rglob("*.md")))


def _regenerate_caches(wiki_root: Path) -> dict:
    """Rebuild the FTS5 search index; optionally run the graph build.

    Prints human-readable progress. Returns a status dict for JSON output.
    """
    info = {"indexed": None, "graph": None}

    # FTS5 index — pure Python, always available on a base install.
    stats = index_wiki(wiki_root, rebuild=True)
    info["indexed"] = stats.get("total_indexed")
    print(f"✓ Rebuilt FTS5 search index: {stats['total_indexed']} pages indexed")

    # Graph build — only when the graph-engine dist is present. A base install
    # must never require node: without the dist we print a hint and continue.
    graph_js = _graph_engine_js()
    if graph_js is None:
        info["graph"] = "skipped"
        print(
            "ℹ Graph build skipped (graph-engine/dist/index.js not found). "
            "For the graph view run:\n"
            "   node graph-engine/dist/index.js --wiki <dest> --action build",
            file=sys.stderr,
        )
        return info

    try:
        result = subprocess.run(
            ["node", str(graph_js), "--wiki", str(wiki_root), "--action", "build"],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (FileNotFoundError, OSError) as e:
        info["graph"] = "skipped"
        print(
            f"ℹ Graph build skipped (node unavailable: {e}). "
            "Run the graph build later for the graph view.",
            file=sys.stderr,
        )
        return info

    if result.returncode == 0:
        info["graph"] = "built"
        print("✓ Rebuilt graph data (graph-data.json)")
    else:
        info["graph"] = "failed"
        print(
            f"⚠ Graph build reported an error (exit {result.returncode}); "
            "continuing — the wiki is fully functional without graph-data.json.",
            file=sys.stderr,
        )
    return info


def _print_next_steps(wiki_root: Path) -> None:
    dest = str(wiki_root)
    print("\nNext steps:")
    print(f"   llm-wiki search {dest} \"event loop\"")
    print(f"   llm-wiki summarize-communities {dest} --dry-run")
    print(f"   llm-wiki serve {dest}")
    # LWM_033 'ask' is gated on availability so a base install never advertises
    # a command that does not exist yet.
    if _ask_available():
        print(f"   llm-wiki ask {dest} \"how does Redis persist data?\"")


def _ask_available() -> bool:
    try:
        import importlib.util
        return importlib.util.find_spec("llm_wiki.ops.ask") is not None
    except (ImportError, ValueError):
        return False


def run(argv=None) -> int:
    """Run the demo command; returns an exit code (0/1/2)."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Materialize the committed demo wiki (Redis Internals) to <dest>.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  llm-wiki demo /tmp/redis-demo\n"
            "  llm-wiki demo ~/playground/redis-demo --force\n"
        ),
    )
    parser.add_argument("dest", help="Directory to materialize the demo wiki into")
    parser.add_argument("--force", "-f", action="store_true",
                        help="Replace an existing non-empty destination directory")
    parser.add_argument("--json", action="store_true",
                        help="Print the dest + page count as JSON")

    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        return code

    try:
        fixture = demo_source()
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 2

    dest = Path(args.dest)

    # ── Overwrite protection (mirrors scaffold.py's refusal) ─────────────
    if dest.exists() and not args.force:
        nonempty = (dest.is_dir() and any(dest.iterdir())) or dest.is_file()
        if nonempty:
            print(f"⚠️  Target directory already exists and is not empty:")
            print(f"   - {dest}")
            print(f"\nUse --force to overwrite, or choose a different path.")
            return 1
        # Empty existing directory: fall through and replace cleanly.

    # ── Materialize with git-copy semantics (no symlinks) ────────────────
    if dest.exists():
        if dest.is_dir():
            shutil.rmtree(dest)
        else:
            dest.unlink()
    shutil.copytree(fixture, dest, symlinks=False)

    if args.json:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            info = _regenerate_caches(dest)
        page_count = _count_pages(dest)
        print(json.dumps(
            {"dest": str(dest), "page_count": page_count,
             "graph": info.get("graph"), "indexed": info.get("indexed")},
            indent=2,
        ))
        return 0

    print(f"✅ Demo wiki materialized at: {dest}")
    print(f"   Pages:   {_count_pages(dest)}")
    print(f"   Source:  {fixture}")
    _regenerate_caches(dest)
    _print_next_steps(dest)
    return 0


def main() -> int:
    import sys as _sys

    for _stream in (_sys.stdout, _sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            break

    return run()


if __name__ == "__main__":
    sys.exit(main())
