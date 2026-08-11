"""llm-wiki setup — one-command client wiring.

Scaffold/validate a wiki, register the MCP server with the detected client(s)
(claude / codex / opencode / hermes), optionally install the recommended extras,
and smoke-test the result. Idempotent, reversible (``--uninstall``), dry-run safe
(v0.6.0 invariant 10 / LWM_035).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import clients

DEFAULT_TEMPLATE = "research"


def _yes_no(prompt: str) -> bool:
    try:
        return input(prompt).strip().lower() in ("y", "yes")
    except EOFError:
        return False


def _print_actions(actions: list[str]) -> None:
    for action in actions:
        print(f"  - {action}")


def _client_snippets(wiki_root: str) -> list[str]:
    """Manual-wiring snippets shown when no client is detected."""
    abs_root = os.path.abspath(wiki_root)
    return [
        "# Claude Code:",
        f'  claude mcp add llm-wiki -- npx llm-wiki-mcp --wiki {abs_root}',
        "# or project-scoped .mcp.json:",
        f'  {{ "mcpServers": {{ "llm-wiki": {{ "command": "npx", "args": ["llm-wiki-mcp", "--wiki", "{abs_root}"] }} }} }}',
        "# Codex (~/.codex/config.toml):",
        "  [mcp_servers.llm-wiki]",
        f'  command = "npx"',
        f'  args = ["llm-wiki-mcp", "--wiki", "{abs_root}"]',
        "# opencode.json:",
        f'  {{ "mcp": {{ "llm-wiki": {{ "type": "local", "command": ["npx", "llm-wiki-mcp", "--wiki", "{abs_root}"], "enabled": true }} }} }}',
        "# Hermes:",
        f'  ln -sf <repo>/skill ~/.hermes/skills/research/llm-wiki',
    ]


def _smoke(wiki_root: str) -> None:
    """Run the smoke test: health check + MCP tools/list (skip-with-hint)."""
    print("== smoke test ==")
    try:
        from llm_wiki.ops.health import check_wiki_health
        results = check_wiki_health(wiki_root)
        code = results.get("exit_code", 0)
        print(f"  {'OK' if code == 0 else 'WARN'} health check (exit {code})")
    except Exception as exc:  # noqa: BLE001 — smoke must never crash setup
        print(f"  WARN health check could not run: {exc}", file=sys.stderr)

    repo_root = Path(__file__).resolve().parents[3]
    dist = repo_root / "mcp-server" / "dist" / "main.js"
    if not shutil.which("npx") or not dist.exists():
        print(
            f"  - skip MCP smoke: build the server first (cd {repo_root}/mcp-server && npm run build)"
        )
        return

    proc = None
    try:
        proc = subprocess.Popen(
            ["npx", "llm-wiki-mcp", "--wiki", wiki_root],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=str(repo_root),
        )
        out, _ = proc.communicate(
            input='{"jsonrpc":"2.0","id":1,"method":"tools/list"}\n', timeout=15
        )
        if '"tools"' in out:
            print("  OK MCP tools/list")
        else:
            print("  WARN MCP tools/list returned unexpected output", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001
        print(f"  - skip MCP smoke: {exc}", file=sys.stderr)
    finally:
        if proc is not None:
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass


def run(
    argv: list[str],
    *,
    home: str | Path | None = None,
    cwd: str | Path | None = None,
    confirm=None,
) -> int:
    """Execute setup with an explicit argv (testable)."""
    home = Path(home) if home is not None else Path(os.environ.get("HOME", str(Path.home())))
    cwd = Path(cwd) if cwd is not None else Path(os.getcwd())
    confirm = confirm or _yes_no

    parser = argparse.ArgumentParser(
        prog="llm-wiki setup",
        description="One-command setup: scaffold/validate a wiki, register the MCP "
        "server with the detected client(s), optionally install recommended extras, "
        "and smoke-test the result.",
    )
    parser.add_argument("wiki_root", help="Path to the wiki root directory")
    parser.add_argument("--title", help="Topic title (required when scaffolding a new wiki)")
    parser.add_argument(
        "--template", "-t",
        default=DEFAULT_TEMPLATE,
        help=f"Template to use when scaffolding (default: {DEFAULT_TEMPLATE})",
    )
    parser.add_argument(
        "--client",
        default="auto",
        choices=["auto", "claude", "codex", "opencode", "hermes"],
        help="Client to register (default: auto-detect)",
    )
    parser.add_argument(
        "--extras",
        default="none",
        choices=["recommended", "none"],
        help="Optional extras profile to install (default: none)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be done without writing anything",
    )
    parser.add_argument(
        "--uninstall", action="store_true",
        help="Reverse the registrations made by setup",
    )
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Assume yes for prompts",
    )
    parser.add_argument(
        "--force", "-f", action="store_true",
        help="Allow overwriting an existing wiki when scaffolding",
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 1

    dry = args.dry_run
    wiki_root = os.path.abspath(str(args.wiki_root))

    # 1. Scaffold (if absent) or validate (if present) — skipped for --uninstall.
    if not args.uninstall:
        if not os.path.exists(wiki_root):
            if not args.title:
                print(
                    "Error: --title is required when the wiki root does not exist "
                    "(scaffold mode).",
                    file=sys.stderr,
                )
                return 2
            if dry:
                print(f"  - scaffold {wiki_root}")
            else:
                from llm_wiki.wiki.scaffold import scaffold
                scaffold(wiki_root, args.title, args.template, force=args.force)
                print(f"Scaffolded wiki at {wiki_root}")
        else:
            try:
                from llm_wiki.core.layout import discover_layout
                discover_layout(wiki_root)
                print(f"Validated existing wiki at {wiki_root}")
            except Exception as exc:  # noqa: BLE001 — warn, do not block setup
                print(f"Warning: could not validate wiki at {wiki_root}: {exc}", file=sys.stderr)

    # 2. Uninstall path (reversibility — invariant 5).
    if args.uninstall:
        print("== unregistering llm-wiki ==")
        actions: list[str] = []
        actions += clients.unregister_claude(cwd, dry_run=dry)
        actions += clients.unregister_codex(home, dry_run=dry)
        actions += clients.unregister_opencode(cwd, dry_run=dry)
        actions += clients.unregister_hermes(home, dry_run=dry)
        if not actions:
            print("  (nothing registered)")
        _print_actions(actions)
        return 0

    # 3. Client registration.
    if args.client == "auto":
        detected = clients.detect_clients(home, cwd)
        if not detected:
            print("No supported MCP client detected. Manual wiring:")
            for line in _client_snippets(wiki_root):
                print(f"  {line}")
        else:
            print(f"Detected client(s): {', '.join(detected)}")
            _register_for(detected, wiki_root, home, cwd, dry)
    else:
        _register_for([args.client], wiki_root, home, cwd, dry, explicit=args.client)

    # 4. Recommended extras (prompt-only unless --yes).
    if args.extras == "recommended":
        repo_root = Path(__file__).resolve().parents[3]
        cmd = (
            "uv pip install -e '.[recommended]'"
            if shutil.which("uv")
            else "pip install -e '.[recommended]'"
        )
        print(f"== extras ==")
        print(f"  run: {cmd}")
        if not dry:
            do_it = args.yes or confirm("  Install recommended extras now? [y/N] ")
            if do_it:
                subprocess.run([cmd], shell=True, cwd=str(repo_root), check=False)

    # 5. Smoke test.
    if not dry:
        _smoke(wiki_root)

    return 0


def _register_for(
    clients_to_run: list[str],
    wiki_root: str,
    home: Path,
    cwd: Path,
    dry: bool,
    *,
    explicit: str,
) -> None:
    for client in clients_to_run:
        if client == "claude":
            actions = clients.register_claude(wiki_root, cwd, dry_run=dry)
        elif client == "codex":
            actions = clients.register_codex(wiki_root, home, dry_run=dry)
        elif client == "opencode":
            actions = clients.register_opencode(wiki_root, cwd, dry_run=dry)
        elif client == "hermes":
            actions = clients.register_hermes(home, dry_run=dry)
        else:
            actions = []
        print(f"== {client} ==")
        _print_actions(actions)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            break
    return run(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
