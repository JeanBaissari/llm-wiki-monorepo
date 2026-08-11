"""Per-client MCP registration writers for ``llm-wiki setup``.

Zero-dependency, idempotent, reversible. Every writer:
- merges into existing config (never clobbers unrelated keys),
- is idempotent (a second write is byte-stable),
- is reversible via its matching ``unregister_*``,
- honors ``dry_run`` (returns the planned actions without touching disk).

Supported clients: claude (`.mcp.json` / ``claude mcp add``), codex
(``~/.codex/config.toml``), opencode (``opencode.json``), hermes (skill symlink).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

MCP_SERVER_CMD = "npx"
MCP_SERVER_BIN = "llm-wiki-mcp"

_ACTION_LIST = list[str]


def mcp_args(wiki_root: str) -> list[str]:
    """The argument list passed to the MCP server for a wiki root."""
    return [MCP_SERVER_BIN, "--wiki", os.path.abspath(wiki_root)]


def _read_text(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _write_text(path: Path, text: str, dry_run: bool) -> _ACTION_LIST:
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return [f"write {path}"]


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _write_json(path: Path, data: dict, dry_run: bool) -> _ACTION_LIST:
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return [f"write {path}"]


# ── Detection ─────────────────────────────────────────────────────────────

def detect_clients(home: Path, project_dir: Path) -> list[str]:
    """Detect which clients are present/configured on this machine."""
    found: list[str] = []
    if shutil.which("claude"):
        found.append("claude")
    if shutil.which("codex") or (home / ".codex" / "config.toml").exists():
        found.append("codex")
    if (project_dir / "opencode.json").exists():
        found.append("opencode")
    if (home / ".hermes").exists():
        found.append("hermes")
    return found


# ── Claude ────────────────────────────────────────────────────────────────

def register_claude(
    wiki_root: str,
    project_dir: Path,
    *,
    dry_run: bool = False,
) -> _ACTION_LIST:
    """Prefer ``claude mcp add`` when the binary is present; else write ``.mcp.json``."""
    if shutil.which("claude"):
        cmd = [
            "claude", "mcp", "add", "llm-wiki", "--",
            MCP_SERVER_CMD, *mcp_args(wiki_root),
        ]
        if dry_run:
            return [f"run: {' '.join(cmd)}"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return [f"claude mcp add llm-wiki (ok)"]
        return register_claude_mcp_json(wiki_root, project_dir, dry_run=dry_run)
    return register_claude_mcp_json(wiki_root, project_dir, dry_run=dry_run)


def register_claude_mcp_json(
    wiki_root: str,
    project_dir: Path,
    *,
    dry_run: bool = False,
) -> _ACTION_LIST:
    """Merge the ``llm-wiki`` server into a project-scoped ``.mcp.json``."""
    path = project_dir / ".mcp.json"
    data = _read_json(path)
    servers = data.setdefault("mcpServers", {})
    servers["llm-wiki"] = {"command": MCP_SERVER_CMD, "args": mcp_args(wiki_root)}
    return _write_json(path, data, dry_run)


def unregister_claude(project_dir: Path, *, dry_run: bool = False) -> _ACTION_LIST:
    if shutil.which("claude"):
        cmd = ["claude", "mcp", "remove", "llm-wiki"]
        if not dry_run:
            subprocess.run(cmd, capture_output=True, text=True)
    return unregister_claude_mcp_json(project_dir, dry_run=dry_run)


def unregister_claude_mcp_json(project_dir: Path, *, dry_run: bool = False) -> _ACTION_LIST:
    path = project_dir / ".mcp.json"
    if not path.exists():
        return []
    data = _read_json(path)
    servers = data.get("mcpServers", {})
    if "llm-wiki" not in servers:
        return []
    del servers["llm-wiki"]
    if not servers:
        data.pop("mcpServers", None)
    if dry_run:
        return [f"unregister {path}: mcpServers.llm-wiki"]
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return [f"unregister {path}: mcpServers.llm-wiki"]


# ── Codex (TOML text merge — no stdlib TOML writer) ──────────────────────

_TABLE_RE = re.compile(r"^\s*\[(.+)]\s*$")


def _toml_string_list(values: list[str]) -> str:
    return "[" + ", ".join(json.dumps(v) for v in values) + "]"


def _find_table(lines: list[str], header: str) -> tuple[int, int] | None:
    start: int | None = None
    for i, line in enumerate(lines):
        m = _TABLE_RE.match(line)
        if m and m.group(1).strip() == header:
            start = i
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if _TABLE_RE.match(lines[j]):
            end = j
            break
    return (start, end)


def _upsert_toml_table(text: str, header: str, body: list[str]) -> tuple[str, bool]:
    """Return (new_text, changed). Idempotent: identical body -> no change."""
    body = [f'{key} = {value}' for key, value in body]
    if not text.strip():
        block = f"[{header}]\n" + "\n".join(body) + "\n"
        return text + block, True
    lines = text.split("\n")
    span = _find_table(lines, header)
    if span is not None:
        start, end = span
        kept = [lines[start]]
        for line in lines[start + 1:end]:
            stripped = line.strip()
            if not stripped or stripped.startswith("command") or stripped.startswith("args"):
                continue
            kept.append(line)
        kept.extend(body)
        out = "\n".join(lines[:start] + kept + lines[end:])
        if not out.endswith("\n"):
            out += "\n"
    else:
        out = text.rstrip("\n") + f"\n\n[{header}]\n" + "\n".join(body) + "\n"
    return out, out != text


def codex_config_path(home: Path) -> Path:
    return home / ".codex" / "config.toml"


def register_codex(wiki_root: str, home: Path, *, dry_run: bool = False) -> _ACTION_LIST:
    path = codex_config_path(home)
    text = _read_text(path)
    body = [
        ("command", '"npx"'),
        ("args", _toml_string_list(mcp_args(wiki_root))),
    ]
    new_text, changed = _upsert_toml_table(text, "mcp_servers.llm-wiki", body)
    if not changed:
        return []
    return _write_text(path, new_text, dry_run)


def unregister_codex(home: Path, *, dry_run: bool = False) -> _ACTION_LIST:
    path = codex_config_path(home)
    text = _read_text(path)
    if not text.strip():
        return []
    lines = text.split("\n")
    span = _find_table(lines, "mcp_servers.llm-wiki")
    if span is None:
        return []
    start, end = span
    new_lines = lines[:start] + lines[end:]
    # Collapse any double blank lines introduced by removal.
    collapsed: list[str] = []
    prev_blank = False
    for line in new_lines:
        blank = line.strip() == ""
        if blank and prev_blank:
            continue
        collapsed.append(line)
        prev_blank = blank
    new_text = "\n".join(collapsed)
    if dry_run:
        return [f"unregister {path}: mcp_servers.llm-wiki"]
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
    return [f"unregister {path}: mcp_servers.llm-wiki"]


# ── opencode ──────────────────────────────────────────────────────────────

def opencode_config_path(project_dir: Path) -> Path:
    return project_dir / "opencode.json"


def register_opencode(wiki_root: str, project_dir: Path, *, dry_run: bool = False) -> _ACTION_LIST:
    path = opencode_config_path(project_dir)
    data = _read_json(path)
    mcp = data.setdefault("mcp", {})
    mcp["llm-wiki"] = {
        "type": "local",
        "command": [MCP_SERVER_CMD, *mcp_args(wiki_root)],
        "enabled": True,
    }
    return _write_json(path, data, dry_run)


def unregister_opencode(project_dir: Path, *, dry_run: bool = False) -> _ACTION_LIST:
    path = opencode_config_path(project_dir)
    if not path.exists():
        return []
    data = _read_json(path)
    mcp = data.get("mcp", {})
    if "llm-wiki" not in mcp:
        return []
    del mcp["llm-wiki"]
    if not mcp:
        data.pop("mcp", None)
    if dry_run:
        return [f"unregister {path}: mcp.llm-wiki"]
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return [f"unregister {path}: mcp.llm-wiki"]


# ── Hermes (skill symlink) ────────────────────────────────────────────────

def resolve_skill_dir() -> Path | None:
    """Repo checkout ``skill/`` dir; fall back to an installed-package sibling."""
    here = Path(__file__).resolve()
    repo_skill = here.parents[3] / "skill"
    if repo_skill.is_dir():
        return repo_skill
    pkg_skill = here.parents[1] / "skill"
    return pkg_skill if pkg_skill.is_dir() else None


def hermes_skill_path(home: Path) -> Path:
    return home / ".hermes" / "skills" / "research" / "llm-wiki"


def register_hermes(home: Path, *, dry_run: bool = False) -> _ACTION_LIST:
    skill_dir = resolve_skill_dir()
    if skill_dir is None:
        return ["skip hermes: skill directory not found"]
    dest = hermes_skill_path(home)
    if dest.exists() or dest.is_symlink():
        if dest.is_symlink() and dest.resolve() == skill_dir.resolve():
            return [f"hermes already linked: {dest}"]
        return [f"skip hermes: {dest} exists and is not this repo's skill"]
    if not dry_run:
        dest.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(str(skill_dir), str(dest))
    return [f"symlink {skill_dir} -> {dest}"]


def unregister_hermes(home: Path, *, dry_run: bool = False) -> _ACTION_LIST:
    dest = hermes_skill_path(home)
    skill_dir = resolve_skill_dir()
    if skill_dir is not None and dest.is_symlink() and dest.resolve() == skill_dir.resolve():
        if not dry_run:
            dest.unlink()
        return [f"unlink {dest}"]
    return []
