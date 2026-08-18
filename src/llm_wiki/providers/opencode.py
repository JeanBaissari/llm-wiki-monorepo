"""opencode provider — Routes LLM calls through the opencode HTTP API.

When running inside an opencode session, this provider uses the opencode
server's HTTP API (default: http://localhost:4096) to make LLM calls.
This avoids the deadlock inherent in filesystem-based IPC by using the
server's /session/{id}/message endpoint.

Protocol:
    1. Check if opencode server is reachable (GET /global/health)
    2. Create a dedicated sidecar session (POST /session)
    3. Send prompt via POST /session/{id}/message (sync, blocks until done)
    4. Extract response text from the assistant message parts
    5. Return the response text

Fallback: If the HTTP API is unavailable, falls through to
LLM_WIKI_RESPONSE_FILE, then to stderr (print prompts).
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from typing import Optional

from . import (
    LLMResponse,
    ProviderNotAvailableError,
)


# opencode server URL (default: localhost:4096)
OPENCODE_URL = os.environ.get("OPENCODE_URL", "http://localhost:4096")

# Default timeout for LLM calls in seconds
DEFAULT_TIMEOUT = int(os.environ.get("LLM_WIKI_OPCODE_TIMEOUT", "300"))

# Module-level session cache: sidecar_name -> session_id
_sessions: dict[str, str] = {}


def _approx_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English text."""
    return max(1, len(text) // 4)


def _http_request(method: str, path: str, body: dict | None = None,
                  timeout: int = 30) -> dict | list | None:
    """Make an HTTP request to the opencode server.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        path: API path (e.g., /session)
        body: JSON body for POST/PUT requests
        timeout: Request timeout in seconds

    Returns:
        Parsed JSON response, or None on error.
    """
    url = f"{OPENCODE_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    headers = {"Content-Type": "application/json"} if data else {}

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 204:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError,
            OSError, TimeoutError) as e:
        print(f"  ⚠  opencode HTTP: {method} {path} failed: {e}",
              file=sys.stderr)
        return None


def _is_server_reachable() -> bool:
    """Check if the opencode server is running and reachable."""
    result = _http_request("GET", "/global/health", timeout=5)
    return result is not None and result.get("healthy", False)


def _get_or_create_session(sidecar_name: str = "llm-wiki-sidecar") -> str:
    """Get or create a dedicated session for sidecar LLM calls.

    Each sidecar gets its own session to avoid blocking the main
    agent conversation.
    """
    if sidecar_name in _sessions:
        return _sessions[sidecar_name]

    # Try to create a new session
    result = _http_request("POST", "/session", {
        "title": f"llm-wiki sidecar: {sidecar_name}",
    })

    if result and "id" in result:
        session_id = result["id"]
        _sessions[sidecar_name] = session_id
        print(f"  ✓ opencode: created sidecar session {session_id}",
              file=sys.stderr)
        return session_id

    # Fallback: try to find an existing session
    sessions = _http_request("GET", "/session")
    if sessions and isinstance(sessions, list) and len(sessions) > 0:
        # Use the first idle session
        for s in sessions:
            if s.get("id"):
                session_id = s["id"]
                _sessions[sidecar_name] = session_id
                return session_id

    raise ProviderNotAvailableError(
        "Cannot create opencode session. Is the opencode server running?"
    )


def _extract_text_from_response(response: dict) -> str:
    """Extract response text from an opencode message response.

    The response format is:
    {
        "info": AssistantMessage,
        "parts": [{type: "text", text: "..."}, ...]
    }
    """
    parts = response.get("parts", [])
    texts = []
    for part in parts:
        if part.get("type") == "text":
            texts.append(part.get("text", ""))
    return "\n".join(texts) if texts else ""


def _call_via_http(system: str, user: str, timeout: int = DEFAULT_TIMEOUT,
                   sidecar_name: str = "llm-wiki-sidecar") -> Optional[LLMResponse]:
    """Make an LLM call via the opencode HTTP API.

    Uses a dedicated session per sidecar to avoid blocking the main
    agent conversation. Sends the prompt synchronously and extracts
    the response text.
    """
    try:
        # Check server health first
        if not _is_server_reachable():
            print("  ⚠  opencode: server not reachable at "
                  f"{OPENCODE_URL}", file=sys.stderr)
            return None

        # Get or create sidecar session
        session_id = _get_or_create_session(sidecar_name)

        # Combine system + user into a single prompt
        # (opencode doesn't have a separate system message field in the HTTP API,
        #  so we prepend the system prompt to the user message)
        combined_prompt = f"{system}\n\n---\n\n{user}"

        # Send the prompt synchronously
        response = _http_request(
            "POST",
            f"/session/{session_id}/message",
            body={
                "parts": [{"type": "text", "text": combined_prompt}],
            },
            timeout=timeout,
        )

        if response is None:
            print("  ⚠  opencode: no response from /message endpoint",
                  file=sys.stderr)
            return None

        # Extract text from the response
        text = _extract_text_from_response(response)
        if not text:
            print("  ⚠  opencode: empty response text", file=sys.stderr)
            return None

        # Extract model info from the assistant message
        info = response.get("info", {})
        model_id = info.get("modelID", "unknown")
        provider_id = info.get("providerID", "unknown")
        cost = info.get("cost", 0.0)
        tokens = info.get("tokens", {})
        input_tokens = tokens.get("input", _approx_tokens(system + user))
        output_tokens = tokens.get("output", _approx_tokens(text))

        print(f"  ✓ opencode: {len(text)} chars from {provider_id}/{model_id}",
              file=sys.stderr)

        return LLMResponse(
            text=text,
            model=f"{provider_id}/{model_id}",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            provider="opencode",
        )

    except ProviderNotAvailableError:
        raise
    except Exception as e:
        print(f"  ⚠  opencode HTTP call failed: {e}", file=sys.stderr)
        return None


def _call_via_response_file(system: str, user: str) -> Optional[LLMResponse]:
    """Fallback: use LLM_WIKI_RESPONSE_FILE if set.

    This is the existing manual/offline path. The user or agent sets
    LLM_WIKI_RESPONSE_FILE to a path, pastes/writes the LLM response
    there, and the script reads it back.
    """
    rf = os.environ.get("LLM_WIKI_RESPONSE_FILE")
    if not rf:
        return None

    try:
        from pathlib import Path
        response_path = Path(rf)
        if not response_path.exists():
            return None

        text = response_path.read_text(encoding="utf-8").strip()
        if not text:
            return None

        return LLMResponse(
            text=text,
            model="agent-native",
            input_tokens=_approx_tokens(system + user),
            output_tokens=_approx_tokens(text),
            cost=0.0,
            provider="opencode",
        )
    except (IOError, OSError):
        return None


def _call_via_stderr(system: str, user: str) -> LLMResponse:
    """Last resort: print prompts to stderr, return empty response.

    The prompts are printed so a human can respond manually.
    """
    sep = "=" * 70
    print(f"\n{sep}\n  SYSTEM PROMPT [opencode]:\n{sep}\n{system}",
          file=sys.stderr)
    print(f"\n{sep}\n  USER PROMPT [opencode]:\n{sep}\n{user}",
          file=sys.stderr)
    print(f"  ⚠  opencode: no response available. "
          "Set LLM_WIKI_RESPONSE_FILE or ensure opencode server is running.",
          file=sys.stderr)

    return LLMResponse(
        text="",
        model="agent-native",
        input_tokens=_approx_tokens(system + user),
        output_tokens=0,
        cost=0.0,
        provider="opencode",
    )


class OpenCodeProvider:
    """Routes LLM calls through the opencode HTTP API.

    Detection: Auto-initialized when detect_default_provider() returns
    'opencode' — i.e., when HERMES_SESSION_ID, CLAUDE_CODE_SESSION,
    CODEX_SESSION, or LLM_WIKI_AGENT_MODE=1 is set in the environment.

    Communication: Uses the opencode server's HTTP API at
    http://localhost:4096 (configurable via OPENCODE_URL env var).
    Each sidecar gets a dedicated session to avoid blocking the main
    agent conversation.

    Fallback chain:
        1. HTTP API (opencode server)
        2. LLM_WIKI_RESPONSE_FILE (manual/offline)
        3. stderr (print prompts for human response)
    """

    def __init__(self):
        self.session_id = (
            os.environ.get("HERMES_SESSION_ID")
            or os.environ.get("CLAUDE_CODE_SESSION")
            or os.environ.get("CODEX_SESSION")
            or os.environ.get("LLM_WIKI_AGENT_MODE", "")  # fallback for agent mode
            or "unknown"
        )
        self.model = os.environ.get("HERMES_MODEL", "agent-native")
        if not self.session_id or self.session_id == "unknown":
            raise ProviderNotAvailableError(
                "opencode provider requires running inside an AI agent session "
                "(set HERMES_SESSION_ID, CLAUDE_CODE_SESSION, CODEX_SESSION, "
                "or LLM_WIKI_AGENT_MODE=1)"
            )

    @property
    def supports_streaming(self) -> bool:
        return True

    @property
    def supports_structured_output(self) -> bool:
        return True

    def call(self, system: str, user: str, **kwargs) -> LLMResponse:
        """Route the LLM call through the opencode HTTP API.

        Args:
            system: System prompt / instructions.
            user: User message / content to process.
            **kwargs: Additional params (timeout, temperature, sidecar_name).

        Returns:
            LLMResponse with the model's output text.
        """
        timeout = kwargs.get("timeout") or int(
            os.environ.get("LLM_WIKI_OPCODE_TIMEOUT", str(DEFAULT_TIMEOUT))
        )
        sidecar_name = kwargs.get("sidecar_name", "llm-wiki-sidecar")

        # Try LLM_WIKI_RESPONSE_FILE first (fast path if already set)
        response = _call_via_response_file(system, user)
        if response is not None:
            return response

        # Try HTTP API to opencode server
        response = _call_via_http(system, user, timeout=timeout,
                                  sidecar_name=sidecar_name)
        if response is not None:
            return response

        # Neither worked — print prompts so a human can respond
        return _call_via_stderr(system, user)
