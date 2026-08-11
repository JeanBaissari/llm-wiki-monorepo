"""Contract tests for `llm-wiki setup` (LWM_035).

Covers: scaffold-reuse, validation, dry-run-writes-nothing, per-client
idempotency + no-clobber, uninstall round-trip, HOME/cwd isolation,
unknown-client exit 2, no-secrets, and the smoke-test paths.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from llm_wiki.setup import run  # noqa: E402
from llm_wiki.setup import clients  # noqa: E402


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """HOME + cwd isolated in tmp_path, and no client binaries detected."""
    home = tmp_path / "home"
    cwd = tmp_path / "cwd"
    home.mkdir()
    cwd.mkdir()
    monkeypatch.setattr(os, "environ", {**os.environ, "HOME": str(home)})
    monkeypatch.setattr(clients.shutil, "which", lambda _: None)
    return {"home": home, "cwd": cwd}


def _setup_args(root, **kw):
    # run() receives argv exactly as cli.py passes it (command name stripped).
    args = [str(root)]
    for key, value in kw.items():
        if value is True:
            args.append(f"--{key.replace('_', '-')}")
        elif value is False:
            pass
        else:
            args.append(f"--{key.replace('_', '-')}")
            args.append(str(value))
    return args


def _existing_mcp_json(cwd, servers=None):
    data = {"mcpServers": servers or {"other-server": {"command": "x", "args": ["y"]}}}
    (cwd / ".mcp.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


class TestDryRun:
    def test_dry_run_writes_nothing(self, isolated, tmp_path):
        home, cwd = isolated["home"], isolated["cwd"]
        root = tmp_path / "wiki"
        code = run(
            _setup_args(root, title="Demo", client="opencode", dry_run=True),
            home=home, cwd=cwd,
        )
        assert code == 0
        assert not root.exists()
        assert not (cwd / "opencode.json").exists()
        assert not (cwd / ".mcp.json").exists()
        assert not (home / ".codex" / "config.toml").exists()
        assert not (home / ".hermes").exists()

    def test_dry_run_existing_wiki_no_rewrite(self, isolated, tmp_path):
        home, cwd = isolated["home"], isolated["cwd"]
        root = tmp_path / "wiki"
        (root / "wiki" / "concepts").mkdir(parents=True)
        (root / "CLAUDE.md").write_text("keep", encoding="utf-8")
        code = run(
            _setup_args(root, client="opencode", dry_run=True),
            home=home, cwd=cwd,
        )
        assert code == 0
        assert (root / "CLAUDE.md").read_text(encoding="utf-8") == "keep"


class TestScaffold:
    def test_scaffold_reuse(self, isolated, tmp_path):
        home, cwd = isolated["home"], isolated["cwd"]
        root = tmp_path / "wiki"
        code = run(_setup_args(root, title="Demo", client="auto"), home=home, cwd=cwd)
        assert code == 0
        assert (root / "PURPOSE.md").exists()
        assert (root / "CLAUDE.md").exists()

    def test_scaffold_requires_title(self, isolated, tmp_path):
        home, cwd = isolated["home"], isolated["cwd"]
        root = tmp_path / "wiki"
        code = run(_setup_args(root, client="auto"), home=home, cwd=cwd)
        assert code == 2


class TestClaude:
    def test_writes_mcp_json_idempotent_no_clobber(self, isolated, tmp_path):
        home, cwd = isolated["home"], isolated["cwd"]
        root = tmp_path / "wiki"
        _existing_mcp_json(cwd)
        before = (cwd / ".mcp.json").read_text(encoding="utf-8")
        code = run(_setup_args(root, title="Demo", client="claude"), home=home, cwd=cwd)
        assert code == 0
        data = json.loads((cwd / ".mcp.json").read_text(encoding="utf-8"))
        assert "other-server" in data["mcpServers"]
        assert data["mcpServers"]["llm-wiki"]["command"] == "npx"
        assert "llm-wiki-mcp" in data["mcpServers"]["llm-wiki"]["args"]
        # idempotent
        run(_setup_args(root, client="claude"), home=home, cwd=cwd)
        after = (cwd / ".mcp.json").read_text(encoding="utf-8")
        after_data = json.loads(after)
        assert after_data["mcpServers"]["llm-wiki"]["args"] == data["mcpServers"]["llm-wiki"]["args"]
        assert after != before  # llm-wiki added
        assert "other-server" in after_data["mcpServers"]


class TestCodex:
    def test_writes_toml_preserves_unrelated(self, isolated, tmp_path):
        home, cwd = isolated["home"], isolated["cwd"]
        root = tmp_path / "wiki"
        cfg = home / ".codex" / "config.toml"
        cfg.parent.mkdir(parents=True)
        cfg.write_text(
            '# keep this comment\n[model]\nname = "gpt-5"\n\n[other]\nx = 1\n',
            encoding="utf-8",
        )
        code = run(_setup_args(root, title="Demo", client="codex"), home=home, cwd=cwd)
        assert code == 0
        text = cfg.read_text(encoding="utf-8")
        assert "# keep this comment" in text
        assert '[model]\nname = "gpt-5"' in text
        assert "[other]\nx = 1" in text
        assert "[mcp_servers.llm-wiki]" in text
        assert 'args = ["llm-wiki-mcp", "--wiki",' in text

    def test_toml_idempotent_byte_stable(self, isolated, tmp_path):
        home, cwd = isolated["home"], isolated["cwd"]
        root = tmp_path / "wiki"
        run(_setup_args(root, title="Demo", client="codex"), home=home, cwd=cwd)
        first = (home / ".codex" / "config.toml").read_text(encoding="utf-8")
        run(_setup_args(root, client="codex"), home=home, cwd=cwd)
        second = (home / ".codex" / "config.toml").read_text(encoding="utf-8")
        assert first == second


class TestOpencode:
    def test_writes_json_preserves_keys(self, isolated, tmp_path):
        home, cwd = isolated["home"], isolated["cwd"]
        root = tmp_path / "wiki"
        (cwd / "opencode.json").write_text(
            json.dumps({"theme": "dark", "mcp": {"other": {"type": "local", "command": ["x"]}}}),
            encoding="utf-8",
        )
        code = run(_setup_args(root, title="Demo", client="opencode"), home=home, cwd=cwd)
        assert code == 0
        data = json.loads((cwd / "opencode.json").read_text(encoding="utf-8"))
        assert data["theme"] == "dark"
        assert "other" in data["mcp"]
        assert data["mcp"]["llm-wiki"]["enabled"] is True
        assert data["mcp"]["llm-wiki"]["command"] == ["npx", "llm-wiki-mcp", "--wiki", str(root)]


class TestHermes:
    def test_symlink_created_and_skipped_on_repeat(self, isolated, tmp_path):
        home, cwd = isolated["home"], isolated["cwd"]
        root = tmp_path / "wiki"
        code = run(_setup_args(root, title="Demo", client="hermes"), home=home, cwd=cwd)
        assert code == 0
        dest = home / ".hermes" / "skills" / "research" / "llm-wiki"
        assert dest.is_symlink()
        assert dest.resolve() == clients.resolve_skill_dir().resolve()
        # repeat → still a symlink, no error
        code = run(_setup_args(root, client="hermes"), home=home, cwd=cwd)
        assert code == 0
        assert dest.is_symlink()


class TestUninstall:
    def test_uninstall_roundtrip(self, isolated, tmp_path):
        home, cwd = isolated["home"], isolated["cwd"]
        root = tmp_path / "wiki"
        _existing_mcp_json(cwd)
        (cwd / "opencode.json").write_text(
            json.dumps({"theme": "dark"}, indent=2) + "\n", encoding="utf-8",
        )
        mcp_before = (cwd / ".mcp.json").read_text(encoding="utf-8")
        opencode_before = (cwd / "opencode.json").read_text(encoding="utf-8")

        run(_setup_args(root, title="Demo", client="claude"), home=home, cwd=cwd)
        run(_setup_args(root, client="opencode"), home=home, cwd=cwd)
        run(_setup_args(root, client="codex"), home=home, cwd=cwd)
        run(_setup_args(root, client="hermes"), home=home, cwd=cwd)

        code = run(_setup_args(root, uninstall=True), home=home, cwd=cwd)
        assert code == 0
        assert (cwd / ".mcp.json").read_text(encoding="utf-8") == mcp_before
        assert (cwd / "opencode.json").read_text(encoding="utf-8") == opencode_before
        cfg = home / ".codex" / "config.toml"
        assert "[mcp_servers.llm-wiki]" not in cfg.read_text(encoding="utf-8")
        assert not (home / ".hermes" / "skills" / "research" / "llm-wiki").exists()

    def test_uninstall_idempotent(self, isolated, tmp_path):
        home, cwd = isolated["home"], isolated["cwd"]
        root = tmp_path / "wiki"
        run(_setup_args(root, uninstall=True), home=home, cwd=cwd)
        code = run(_setup_args(root, uninstall=True), home=home, cwd=cwd)
        assert code == 0


class TestArgsAndSafety:
    def test_unknown_client_exits_2(self, isolated, tmp_path):
        home, cwd = isolated["home"], isolated["cwd"]
        root = tmp_path / "wiki"
        code = run(["--client", "bogus", str(root)], home=home, cwd=cwd)
        assert code == 2

    def test_no_secrets_written(self, isolated, tmp_path):
        home, cwd = isolated["home"], isolated["cwd"]
        root = tmp_path / "wiki"
        run(_setup_args(root, title="Demo", client="claude"), home=home, cwd=cwd)
        run(_setup_args(root, client="codex"), home=home, cwd=cwd)
        run(_setup_args(root, client="opencode"), home=home, cwd=cwd)
        for path in [cwd / ".mcp.json", cwd / "opencode.json", home / ".codex" / "config.toml"]:
            text = path.read_text(encoding="utf-8")
            for needle in ("api_key", "api-key", "sk-", "bearer"):
                assert needle not in text.lower(), f"{needle} leaked into {path}"

    def test_extras_prompt_declined(self, isolated, tmp_path):
        home, cwd = isolated["home"], isolated["cwd"]
        root = tmp_path / "wiki"
        code = run(
            _setup_args(root, title="Demo", extras="recommended", client="auto"),
            home=home, cwd=cwd,
            confirm=lambda _: False,
        )
        assert code == 0

    def test_home_override_isolated(self, isolated, tmp_path):
        home, cwd = isolated["home"], isolated["cwd"]
        root = tmp_path / "wiki"
        run(_setup_args(root, title="Demo", client="codex"), home=home, cwd=cwd)
        assert (home / ".codex" / "config.toml").exists()
        assert not (tmp_path / "does-not-exist").exists()

    def test_module_entry_parses(self, isolated, tmp_path):
        home, cwd = isolated["home"], isolated["cwd"]
        root = tmp_path / "wiki"
        from llm_wiki.setup import main
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(sys, "argv", ["llm-wiki setup", str(root), "--title", "Demo", "--dry-run"])
        # main() reads sys.argv; HOME/cwd come from env — isolated via monkeypatched environ above
        code = main()
        monkeypatch.undo()
        assert code == 0
