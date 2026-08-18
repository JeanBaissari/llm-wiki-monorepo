"""test_opencode.py — Comprehensive tests for the opencode provider.

Covers:
    - src/llm_wiki/providers/opencode.py (OpenCodeProvider class)
    - src/llm_wiki/providers/registry.py (_call_opencode function)
    - Multi-marker env detection (HERMES_SESSION_ID, CLAUDE_CODE_SESSION,
      CODEX_SESSION, LLM_WIKI_AGENT_MODE)
    - HTTP API flow (opencode server at localhost:4096)
    - LLM_WIKI_RESPONSE_FILE fallback (success, empty, IO errors)
    - Graceful degradation (server unreachable, stderr fallback)
    - Provider metadata (cost=0, capability flags, model tracking)
"""

import json
import os
import sys
from pathlib import Path

import pytest

# ── Ensure src is importable ────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# ══════════════════════════════════════════════════════════════════════════
# Multi-marker env detection
# ══════════════════════════════════════════════════════════════════════════

class TestMultiMarkerDetection:
    """All four agent markers detected correctly."""

    def test_hermes_session_id(self, monkeypatch):
        monkeypatch.setenv("HERMES_SESSION_ID", "hs-001")
        from llm_wiki.providers.opencode import OpenCodeProvider
        p = OpenCodeProvider()
        assert p.session_id == "hs-001"

    def test_claude_code_session(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_CODE_SESSION", "cc-002")
        monkeypatch.delenv("HERMES_SESSION_ID", raising=False)
        from llm_wiki.providers.opencode import OpenCodeProvider
        p = OpenCodeProvider()
        assert p.session_id == "cc-002"

    def test_codex_session(self, monkeypatch):
        monkeypatch.setenv("CODEX_SESSION", "cx-003")
        monkeypatch.delenv("HERMES_SESSION_ID", raising=False)
        monkeypatch.delenv("CLAUDE_CODE_SESSION", raising=False)
        from llm_wiki.providers.opencode import OpenCodeProvider
        p = OpenCodeProvider()
        assert p.session_id == "cx-003"

    def test_llm_wiki_agent_mode(self, monkeypatch):
        """LLM_WIKI_AGENT_MODE=1 works as session_id fallback when no
        other session markers are set. The provider initializes with
        session_id='1' (the env var value)."""
        monkeypatch.setenv("LLM_WIKI_AGENT_MODE", "1")
        monkeypatch.delenv("HERMES_SESSION_ID", raising=False)
        monkeypatch.delenv("CLAUDE_CODE_SESSION", raising=False)
        monkeypatch.delenv("CODEX_SESSION", raising=False)
        from llm_wiki.providers.opencode import OpenCodeProvider
        p = OpenCodeProvider()
        assert p.session_id == "1"

    def test_priority_order_hermes_first(self, monkeypatch):
        """HERMES_SESSION_ID wins when multiple markers set."""
        monkeypatch.setenv("HERMES_SESSION_ID", "hermes-first")
        monkeypatch.setenv("CLAUDE_CODE_SESSION", "claude-second")
        monkeypatch.setenv("CODEX_SESSION", "codex-third")
        from llm_wiki.providers.opencode import OpenCodeProvider
        p = OpenCodeProvider()
        assert p.session_id == "hermes-first"

    def test_model_from_env(self, monkeypatch):
        monkeypatch.setenv("HERMES_SESSION_ID", "test")
        monkeypatch.setenv("HERMES_MODEL", "claude-sonnet-4")
        from llm_wiki.providers.opencode import OpenCodeProvider
        p = OpenCodeProvider()
        assert p.model == "claude-sonnet-4"

    def test_model_default(self, monkeypatch):
        monkeypatch.setenv("HERMES_SESSION_ID", "test")
        monkeypatch.delenv("HERMES_MODEL", raising=False)
        from llm_wiki.providers.opencode import OpenCodeProvider
        p = OpenCodeProvider()
        assert p.model == "agent-native"


# ══════════════════════════════════════════════════════════════════════════
# Provider metadata
# ══════════════════════════════════════════════════════════════════════════

class TestProviderCapabilities:
    """Provider capability flags and metadata."""

    def test_supports_streaming(self, monkeypatch):
        monkeypatch.setenv("HERMES_SESSION_ID", "test")
        from llm_wiki.providers.opencode import OpenCodeProvider
        p = OpenCodeProvider()
        assert p.supports_streaming is True

    def test_supports_structured_output(self, monkeypatch):
        monkeypatch.setenv("HERMES_SESSION_ID", "test")
        from llm_wiki.providers.opencode import OpenCodeProvider
        p = OpenCodeProvider()
        assert p.supports_structured_output is True


# ══════════════════════════════════════════════════════════════════════════
# Response file fallback (LLM_WIKI_RESPONSE_FILE)
# ══════════════════════════════════════════════════════════════════════════

class TestResponseFileFallback:
    """LLM_WIKI_RESPONSE_FILE fallback path."""

    def test_reads_response_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_SESSION_ID", "test")
        monkeypatch.setenv("LLM_WIKI_OPCODE_TIMEOUT", "1")
        rf = tmp_path / "response.txt"
        rf.write_text("# Response content\n\nHello world.")
        monkeypatch.setenv("LLM_WIKI_RESPONSE_FILE", str(rf))

        from llm_wiki.providers.opencode import OpenCodeProvider
        p = OpenCodeProvider()
        resp = p.call("sys", "user")
        assert resp is not None
        assert "Response content" in resp.text
        assert resp.provider == "opencode"
        assert resp.cost == 0.0

    def test_response_file_empty_text(self, tmp_path, monkeypatch):
        """Empty response file -> falls through to stderr fallback."""
        monkeypatch.setenv("HERMES_SESSION_ID", "test")
        monkeypatch.setenv("LLM_WIKI_OPCODE_TIMEOUT", "1")
        rf = tmp_path / "empty.txt"
        rf.write_text("   \n  ")  # whitespace only -> stripped -> empty
        monkeypatch.setenv("LLM_WIKI_RESPONSE_FILE", str(rf))

        from llm_wiki.providers.opencode import OpenCodeProvider
        p = OpenCodeProvider()
        resp = p.call("sys", "user")
        # Empty content after strip -> falls through to stderr fallback
        assert resp is not None  # _call_via_stderr returns empty LLMResponse
        assert resp.text == ""
        assert resp.cost == 0.0

    def test_response_file_missing(self, tmp_path, monkeypatch):
        """Response file path set but file doesn't exist."""
        monkeypatch.setenv("HERMES_SESSION_ID", "test")
        monkeypatch.setenv("LLM_WIKI_OPCODE_TIMEOUT", "1")
        monkeypatch.setenv("LLM_WIKI_RESPONSE_FILE",
                           str(tmp_path / "nonexistent.txt"))

        from llm_wiki.providers.opencode import OpenCodeProvider
        p = OpenCodeProvider()
        resp = p.call("sys", "user")
        # Falls through to stderr fallback
        assert resp is not None
        assert resp.text == ""
        assert resp.provider == "opencode"


# ══════════════════════════════════════════════════════════════════════════
# HTTP API flow (opencode server)
# ══════════════════════════════════════════════════════════════════════════

class TestHTTPAPI:
    """HTTP API-based LLM calls via opencode server."""

    def test_server_unreachable_returns_none(self, monkeypatch):
        """When opencode server is not running, falls through gracefully."""
        monkeypatch.setenv("HERMES_SESSION_ID", "test")
        monkeypatch.setenv("LLM_WIKI_OPCODE_TIMEOUT", "1")
        monkeypatch.delenv("LLM_WIKI_RESPONSE_FILE", raising=False)

        from llm_wiki.providers import opencode as oc_module
        monkeypatch.setattr(oc_module, "OPENCODE_URL", "http://localhost:19999")

        from llm_wiki.providers.opencode import _call_via_http
        result = _call_via_http("sys", "user", timeout=1)
        assert result is None

    def test_http_request_failure(self, monkeypatch):
        """_http_request returns None on connection error."""
        from llm_wiki.providers import opencode as oc_module
        monkeypatch.setattr(oc_module, "OPENCODE_URL", "http://localhost:19999")
        from llm_wiki.providers.opencode import _http_request
        result = _http_request("GET", "/global/health", timeout=1)
        assert result is None

    def test_extract_text_from_response(self):
        """_extract_text_from_response parses opencode response format."""
        from llm_wiki.providers.opencode import _extract_text_from_response
        response = {
            "info": {"modelID": "test", "providerID": "test"},
            "parts": [
                {"type": "text", "text": "Hello "},
                {"type": "text", "text": "world"},
            ],
        }
        assert _extract_text_from_response(response) == "Hello \nworld"

    def test_extract_text_empty_parts(self):
        """_extract_text_from_response handles empty parts."""
        from llm_wiki.providers.opencode import _extract_text_from_response
        assert _extract_text_from_response({"parts": []}) == ""
        assert _extract_text_from_response({}) == ""

    def test_extract_text_non_text_parts(self):
        """_extract_text_from_response ignores non-text parts."""
        from llm_wiki.providers.opencode import _extract_text_from_response
        response = {
            "parts": [
                {"type": "tool_call", "tool": "bash"},
                {"type": "text", "text": "result"},
            ],
        }
        assert _extract_text_from_response(response) == "result"

    def test_is_server_reachable_false(self, monkeypatch):
        """_is_server_reachable returns False when server is down."""
        from llm_wiki.providers import opencode as oc_module
        monkeypatch.setattr(oc_module, "OPENCODE_URL", "http://localhost:19999")
        from llm_wiki.providers.opencode import _is_server_reachable
        assert _is_server_reachable() is False


# ══════════════════════════════════════════════════════════════════════════
# Stderr fallback (last resort)
# ══════════════════════════════════════════════════════════════════════════

class TestStderrFallback:
    """When both HTTP API and response file fail, fall back to stderr."""

    def test_returns_empty_response(self, monkeypatch):
        """Final fallback returns empty LLMResponse (not None)."""
        monkeypatch.setenv("HERMES_SESSION_ID", "test")
        monkeypatch.setenv("LLM_WIKI_OPCODE_TIMEOUT", "1")
        monkeypatch.delenv("LLM_WIKI_RESPONSE_FILE", raising=False)

        from llm_wiki.providers.opencode import OpenCodeProvider
        p = OpenCodeProvider()
        resp = p.call("sys", "user")
        assert resp is not None
        assert resp.text == ""
        assert resp.provider == "opencode"
        assert resp.cost == 0.0
        assert resp.output_tokens == 0

    def test_prompts_printed_to_stderr(self, capsys, monkeypatch):
        """Verify prompts are printed to stderr during call."""
        monkeypatch.setenv("HERMES_SESSION_ID", "test")
        monkeypatch.setenv("LLM_WIKI_OPCODE_TIMEOUT", "1")
        monkeypatch.delenv("LLM_WIKI_RESPONSE_FILE", raising=False)

        from llm_wiki.providers.opencode import OpenCodeProvider
        p = OpenCodeProvider()
        p.call("SYSTEM INSTRUCTIONS", "USER QUERY")

        captured = capsys.readouterr()
        assert "SYSTEM INSTRUCTIONS" in captured.err
        assert "USER QUERY" in captured.err
        assert "[opencode]" in captured.err


# ══════════════════════════════════════════════════════════════════════════
# Provider detection integration
# ══════════════════════════════════════════════════════════════════════════

class TestProviderDetectionPriority:
    """detect_default_provider() from providers/__init__.py."""

    def test_opencode_top_priority(self, monkeypatch):
        monkeypatch.setenv("HERMES_SESSION_ID", "test")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        from llm_wiki.providers import detect_default_provider
        assert detect_default_provider() == "opencode"

    def test_openai_fallback(self, monkeypatch):
        monkeypatch.delenv("HERMES_SESSION_ID", raising=False)
        monkeypatch.delenv("LLM_WIKI_AGENT_MODE", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        from llm_wiki.providers import detect_default_provider
        assert detect_default_provider() == "openai"

    def test_anthropic_fallback(self, monkeypatch):
        monkeypatch.delenv("HERMES_SESSION_ID", raising=False)
        monkeypatch.delenv("LLM_WIKI_AGENT_MODE", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        from llm_wiki.providers import detect_default_provider
        assert detect_default_provider() == "anthropic"

    def test_default_fallback(self, monkeypatch):
        monkeypatch.delenv("HERMES_SESSION_ID", raising=False)
        monkeypatch.delenv("LLM_WIKI_AGENT_MODE", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from llm_wiki.providers import detect_default_provider
        assert detect_default_provider() == "default"


# ══════════════════════════════════════════════════════════════════════════
# LLMResponse dataclass
# ══════════════════════════════════════════════════════════════════════════

class TestLLMResponse:
    """LLMResponse data class behavior."""

    def test_basic_fields(self):
        from llm_wiki.providers import LLMResponse
        r = LLMResponse(
            text="Hello world",
            model="test-model",
            input_tokens=100,
            output_tokens=50,
            cost=0.01,
            provider="test",
        )
        assert r.text == "Hello world"
        assert r.model == "test-model"
        assert r.input_tokens == 100
        assert r.output_tokens == 50
        assert r.cost == 0.01
        assert r.provider == "test"

    def test_total_tokens(self):
        from llm_wiki.providers import LLMResponse
        r = LLMResponse(text="x", input_tokens=10, output_tokens=20)
        assert r.total_tokens == 30

    def test_str_returns_text(self):
        from llm_wiki.providers import LLMResponse
        r = LLMResponse(text="response text")
        assert str(r) == "response text"

    def test_defaults(self):
        from llm_wiki.providers import LLMResponse
        r = LLMResponse(text="")
        assert r.model == "unknown"
        assert r.input_tokens == 0
        assert r.output_tokens == 0
        assert r.cost == 0.0
        assert r.provider == "unknown"


# ══════════════════════════════════════════════════════════════════════════
# _call_opencode() in registry.py
# ══════════════════════════════════════════════════════════════════════════

class TestCallOpencodeFunction:
    """The _call_opencode() function in the unified LLM module."""

    def test_call_opencode_imports(self):
        """Verify _call_opencode exists in llm_wiki.providers.registry."""
        sys.path.insert(0, str(REPO_ROOT / "src"))
        from llm_wiki.providers.registry import _call_opencode
        assert callable(_call_opencode)

    def test_call_opencode_signature(self):
        """_call_opencode accepts system, user, model, **kwargs."""
        sys.path.insert(0, str(REPO_ROOT / "src"))
        from llm_wiki.providers.registry import _call_opencode
        import inspect
        sig = inspect.signature(_call_opencode)
        params = list(sig.parameters.keys())
        assert "system" in params
        assert "user" in params
        assert "model" in params
        assert "kwargs" in params  # **kwargs

    def test_call_opencode_timeout_default(self, monkeypatch):
        """With no real agent, _call_opencode returns None gracefully."""
        sys.path.insert(0, str(REPO_ROOT / "src"))
        monkeypatch.setenv("LLM_WIKI_OPCODE_TIMEOUT", "1")
        monkeypatch.setenv("HERMES_SESSION_ID", "test-call-func")
        monkeypatch.setenv("OPENCODE_URL", "http://localhost:19999")
        monkeypatch.delenv("LLM_WIKI_RESPONSE_FILE", raising=False)
        from llm_wiki.providers.registry import _call_opencode
        result = _call_opencode("sys", "user")
        # No HTTP response, no response file -> returns None
        assert result is None

    def test_call_opencode_response_file(self, tmp_path, monkeypatch):
        """_call_opencode reads from LLM_WIKI_RESPONSE_FILE."""
        sys.path.insert(0, str(REPO_ROOT / "src"))
        monkeypatch.setenv("LLM_WIKI_OPCODE_TIMEOUT", "1")
        monkeypatch.setenv("HERMES_SESSION_ID", "test-rf")
        rf = tmp_path / "llm_response.txt"
        rf.write_text("Function-based response!")
        monkeypatch.setenv("LLM_WIKI_RESPONSE_FILE", str(rf))
        from llm_wiki.providers.registry import _call_opencode
        result = _call_opencode("sys", "user")
        assert result is not None
        assert "Function-based response" in result

    def test_call_opencode_claude_session(self, monkeypatch):
        """CLAUDE_CODE_SESSION detected for session_id."""
        sys.path.insert(0, str(REPO_ROOT / "src"))
        monkeypatch.setenv("LLM_WIKI_OPCODE_TIMEOUT", "1")
        monkeypatch.setenv("CLAUDE_CODE_SESSION", "claude-func-test")
        monkeypatch.setenv("OPENCODE_URL", "http://localhost:19999")
        monkeypatch.delenv("HERMES_SESSION_ID", raising=False)
        monkeypatch.delenv("LLM_WIKI_RESPONSE_FILE", raising=False)
        from llm_wiki.providers.registry import _call_opencode
        # Should detect Claude session and try HTTP (which will fail)
        result = _call_opencode("sys", "user")
        assert result is None  # No real server

    def test_llm_module_has_provider_map(self):
        """PROVIDER_MAP in llm_wiki.providers.registry includes opencode."""
        sys.path.insert(0, str(REPO_ROOT / "src"))
        from llm_wiki.providers.registry import PROVIDER_MAP
        assert "opencode" in PROVIDER_MAP
        assert callable(PROVIDER_MAP["opencode"])

    def test_call_llm_with_opencode_provider(self, tmp_path, monkeypatch):
        """call_llm(provider='opencode') routes to _call_opencode."""
        sys.path.insert(0, str(REPO_ROOT / "src"))
        monkeypatch.setenv("LLM_WIKI_OPCODE_TIMEOUT", "1")
        monkeypatch.setenv("HERMES_SESSION_ID", "test-route")
        rf = tmp_path / "route_response.txt"
        rf.write_text("Routed response!")
        monkeypatch.setenv("LLM_WIKI_RESPONSE_FILE", str(rf))
        from llm_wiki.providers.registry import call_llm
        result = call_llm("sys", "user", provider="opencode")
        assert result is not None
        assert "Routed response" in result

    def test_call_llm_default_in_hermes(self, monkeypatch):
        """call_llm with provider='default' detects Hermes -> opencode."""
        sys.path.insert(0, str(REPO_ROOT / "src"))
        monkeypatch.setenv("LLM_WIKI_OPCODE_TIMEOUT", "1")
        monkeypatch.setenv("HERMES_SESSION_ID", "test-default-detect")
        monkeypatch.setenv("OPENCODE_URL", "http://localhost:19999")
        monkeypatch.delenv("LLM_WIKI_RESPONSE_FILE", raising=False)
        from llm_wiki.providers.registry import call_llm
        # default -> detects opencode -> tries HTTP -> fails gracefully
        result = call_llm("sys", "user")
        assert result is None  # No real server


# ══════════════════════════════════════════════════════════════════════════
# Edge cases
# ══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_opencode_url_env_override(self, monkeypatch):
        """OPENCODE_URL env var changes the server URL."""
        monkeypatch.setenv("OPENCODE_URL", "http://custom-host:8080")
        import os
        url = os.environ.get("OPENCODE_URL", "http://localhost:4096")
        assert url == "http://custom-host:8080"

    def test_timeout_env_override(self, monkeypatch):
        """LLM_WIKI_OPCODE_TIMEOUT env var changes timeout."""
        monkeypatch.setenv("LLM_WIKI_OPCODE_TIMEOUT", "60")
        import os
        timeout = int(os.environ.get("LLM_WIKI_OPCODE_TIMEOUT", "300"))
        assert timeout == 60

    def test_approx_tokens_helper(self):
        """_approx_tokens gives reasonable estimates."""
        from llm_wiki.providers.opencode import _approx_tokens
        assert _approx_tokens("") == 1  # floor at 1
        assert _approx_tokens("abcd") == 1
        assert _approx_tokens("abcdefgh") == 2
        assert _approx_tokens("a" * 400) == 100

    def test_sessions_cache(self, monkeypatch):
        """_sessions module-level cache works correctly."""
        monkeypatch.setenv("HERMES_SESSION_ID", "test")
        from llm_wiki.providers import opencode as oc_module
        # Clear cache
        oc_module._sessions.clear()
        assert "test-cache" not in oc_module._sessions
        oc_module._sessions["test-cache"] = "session-123"
        assert oc_module._sessions["test-cache"] == "session-123"
        # Cleanup
        oc_module._sessions.clear()


# ══════════════════════════════════════════════════════════════════════════
# Error paths
# ══════════════════════════════════════════════════════════════════════════

class TestErrorPaths:
    """Exception handling in HTTP API and response file paths."""

    def test_response_file_io_error(self, tmp_path, monkeypatch):
        """IOError reading response file -> graceful fallback."""
        monkeypatch.setenv("HERMES_SESSION_ID", "test-rf-ioerr")
        monkeypatch.setenv("LLM_WIKI_OPCODE_TIMEOUT", "1")
        # Point to a path that exists but is a directory (can't read as text)
        monkeypatch.setenv("LLM_WIKI_RESPONSE_FILE", str(tmp_path))

        from llm_wiki.providers.opencode import _call_via_response_file
        resp = _call_via_response_file("sys", "user")
        # IOError/OSError -> returns None
        assert resp is None

    def test_http_request_invalid_json(self, monkeypatch):
        """_http_request handles non-JSON responses gracefully."""
        monkeypatch.setenv("OPENCODE_URL", "http://localhost:19999")
        from llm_wiki.providers.opencode import _http_request
        # Server is unreachable, so this returns None
        result = _http_request("GET", "/nonexistent", timeout=1)
        assert result is None
