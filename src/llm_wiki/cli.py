"""Unified CLI entry point for llm-wiki.

Dispatches to the appropriate script based on the first argument.

Usage:
    llm-wiki scaffold <wiki-root> <title> [--template <name>]
    llm-wiki lint <wiki-root>
    llm-wiki ingest <wiki-root> <source-path>
    llm-wiki insights <wiki-root> [--format json]
    llm-wiki link-suggest <wiki-root> [--apply]
    llm-wiki backup <wiki-root> [--snapshot|--auto]
    llm-wiki deep-research <wiki-root> <topic>
    llm-wiki audit <wiki-root> [--open|--resolved]
    llm-wiki benchmark <output-csv>
    llm-wiki migrate-log <wiki-root>
    llm-wiki discover <wiki-root> [--json]
    llm-wiki serve <wiki-root> [--projects <names>]
    llm-wiki embed <wiki-root> [--rebuild]        # requires [semantic] extra; no-op without it
    llm-wiki eval <wiki-root> [--goldset <path>] [--split gate|tune|all]
"""

import sys
from importlib import import_module


COMMANDS = {
    "scaffold": "llm_wiki.wiki.scaffold",
    "lint": "llm_wiki.quality.lint",
    "ingest": "llm_wiki.ingest.pipeline",
    "insights": "llm_wiki.graph.insights",
    "link-suggest": "llm_wiki.graph.suggest",
    "backup": "llm_wiki.wiki.backup",
    "deep-research": "llm_wiki.research.deep_research",
    "audit": "llm_wiki.quality.audit",
    "benchmark": "llm_wiki.ops.benchmark",
    "migrate-log": "llm_wiki.ops.migrate",
    "ops": "llm_wiki.ops.list",
    "discover": "llm_wiki.core.layout",
    "index": "llm_wiki.search",
    "search": "llm_wiki.search.query",
    "embed": "llm_wiki.semantic.embed",
    "eval": "llm_wiki.eval.cli",
    "health": "llm_wiki.ops.health",
    "serve": "llm_wiki.ops.serve",
    "claims": "llm_wiki.quality.claims",
}


ALIASES = {
    "ls": "lint",
    "in": "ingest",
    "sc": "scaffold",
    "bk": "backup",
    "dr": "deep-research",
    "lsug": "link-suggest",
}


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: llm-wiki <command> [args...]\n", file=sys.stderr)
        print("Available commands:", file=sys.stderr)
        for name in sorted(COMMANDS):
            aliases = [a for a, t in ALIASES.items() if t == name]
            alias_str = f"  ({', '.join(aliases)})" if aliases else ""
            print(f"  {name:15s}{alias_str}", file=sys.stderr)
        print(file=sys.stderr)
        print("Flags:  llm-wiki --version   Show version", file=sys.stderr)
        return 1

    if sys.argv[1] in ("--version", "-V"):
        from llm_wiki import __version__
        print(f"llm-wiki {__version__}")
        return 0

    cmd = sys.argv[1]
    module_path = COMMANDS.get(cmd) or COMMANDS.get(ALIASES.get(cmd))
    if not module_path:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(f"Run 'llm-wiki' to see available commands.", file=sys.stderr)
        return 1

    module = import_module(module_path)
    # Forward remaining args to the subcommand (strip the command name)
    sys.argv = [f"llm-wiki {cmd}"] + sys.argv[2:]
    return module.main()
