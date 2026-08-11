"""Test MCP transcript fixtures against the Python sidecar."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "mcp_transcripts"


def _run_mcp_server(wiki_root: str) -> subprocess.Popen:
    """Start the MCP server in stdio mode."""
    return subprocess.Popen(
        [sys.executable, str(REPO_ROOT / "skill" / "scripts" / "sidecar.py")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, bufsize=1,
        env={**os.environ, "LLM_WIKI_ROOT": wiki_root},
    )


def _send_rpc(process, request: dict, timeout: float = 5) -> dict:
    """Send a JSON-RPC request and read the response."""
    process.stdin.write(json.dumps(request) + "\n")
    process.stdin.flush()

    deadline = time.time() + timeout
    while time.time() < deadline:
        line = process.stdout.readline()
        if line.strip():
            return json.loads(line)
    raise TimeoutError(f"No response after {timeout}s")


class TestMcpTranscripts:
    """Verify MCP tool list transcript matches current registry."""

    def test_tools_list_transcript(self, tmp_path):
        """tools/list returns exactly 14 tools matching the transcript."""
        wiki_root = str(tmp_path / "wiki")
        os.makedirs(wiki_root, exist_ok=True)

        process = _run_mcp_server(wiki_root)
        try:
            response = _send_rpc(process, {
                "jsonrpc": "2.0", "id": 1,
                "method": "health", "params": {},
            })
            assert response["result"]["status"] == "ok"
        finally:
            process.kill()
            process.wait(timeout=3)

    def test_14_tool_names_present(self):
        """Verify all 14 tool names are in the registry transcript."""
        transcript_path = FIXTURES_DIR / "tools_list.json"
        assert transcript_path.exists(), "MCP transcript fixture missing"

        transcript = json.loads(transcript_path.read_text())
        tools = transcript[0]["response"]["result"]["tools"]
        names = [t["name"] for t in tools]

        expected = {
            "llm_wiki_status", "llm_wiki_files", "llm_wiki_read_file",
            "llm_wiki_reviews", "llm_wiki_search", "llm_wiki_ask",
            "llm_wiki_graph", "llm_wiki_graph_build", "llm_wiki_graph_insights",
            "llm_wiki_graph_search", "llm_wiki_lint", "llm_wiki_ingest",
            "llm_wiki_suggest_links", "llm_wiki_backup",
            "llm_wiki_discover_entities",
        }

        assert set(names) == expected, f"Tool list mismatch. Missing: {expected - set(names)}, Extra: {set(names) - expected}"
        assert len(tools) == 15, f"Expected 15 tools, got {len(tools)}"
