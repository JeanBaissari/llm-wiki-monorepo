# ADR 0031: `llm-wiki setup` — One-Command Client-Wiring Surface

- **Status:** accepted
- **Date:** 2026-08-11
- **Context:** LWM_035 (v0.6.0) — the top USAGE §8 UX gap. Installing the repo (`install.sh`) and registering the MCP server for each client were separate manual steps (`claude mcp add`, `.mcp.json`, `~/.codex/config.toml`, opencode config, the Hermes symlink). The MCP server (ADR-0010) already had a single entry (`npx llm-wiki-mcp --wiki <root>`); what was missing was one command that scaffolds/validates a wiki, registers that entry for every detected client, and smoke-tests the result.

## Decision

**`llm-wiki setup <root> [--title] [--template] [--client auto|claude|codex|opencode|hermes] [--extras recommended] [--dry-run] [--uninstall] [--yes]`** (`src/llm_wiki/setup/`), with these contracts:

- **Scaffold-or-validate:** absent root → `scaffold()` (title required; mirror its overwrite protection + `--force`); present root → `discover_layout()` validation.
- **Per-client writers, idempotent, zero new dependencies:**
  - claude: prefer `claude mcp add` when the binary exists; else project-scoped `.mcp.json` merge (never clobber other `mcpServers` keys).
  - codex: text-based TOML merge of `[mcp_servers.llm-wiki]` into `~/.codex/config.toml` (TOML has no stdlib writer; the merge preserves unrelated tables/comments byte-for-byte and is byte-stable on re-run).
  - opencode: JSON merge of `mcp.llm-wiki` into project `opencode.json` (other keys preserved).
  - hermes: `ln -sf` the skill symlink (unifies `install.sh` step e).
- **Reversibility + safety:** `--dry-run` writes nothing and prints every action; `--uninstall` removes only the `llm-wiki` entries (round-trip to pre-setup bytes); no secrets are ever written; unknown client → explicit hint; registration writes are git-diffable config edits.
- **Extras + smoke:** `--extras recommended` prompts `pip install -e ".[recommended]"` (never auto-installs without `--yes`); the smoke test runs the health check + a bounded `tools/list` stdio RPC, skipping-with-hint when node/dist are absent (base install never fails on missing TS surfaces).

## Delivered State

`src/llm_wiki/setup/__init__.py` + `clients.py`, `skill/scripts/setup.py`, `tests/test_setup.py` (16 tests: dry-run-writes-nothing, per-client idempotency + no-clobber, uninstall round-trip, HOME/cwd isolation, no-secrets, exit codes). Wired into the CLI dispatcher (27 commands).

## Consequences

**Easier:** a wiki + client wiring + smoke test in one command; `install.sh` remains the repo installer, `llm-wiki setup` is the wiki-to-clients wirer. **Harder:** per-client config formats drift (Codex TOML shape verified at implementation); Windows symlink creation needs privileges; cross-machine provisioning (a `setup --bootstrap` that also installs the repo) remains a follow-on.
