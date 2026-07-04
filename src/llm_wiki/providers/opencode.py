"""opencode provider — Routes LLM calls through the Hermes agent's own model.

When running inside a Hermes agent session, this provider uses the agent's
existing model instead of requiring external API keys. Communication happens
via pipe-based IPC (filesystem-based) so the agent can pick up prompts and
return responses without the script needing network access.

Protocol:
    1. Write prompt to /tmp/llm-wiki-opencode/{session_id}/{request_id}/prompt.json
    2. Signal readiness by creating a .ready marker file
    3. Poll for response at {request_id}/response.json (up to timeout)
    4. Return the response text

Fallback: If the pipe-based IPC times out, falls through to the existing
LLM_WIKI_RESPONSE_FILE mechanism.
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import (
    LLMResponse,
    ProviderNotAvailableError,
)


# Well-known base directory for opencode IPC files
OPCODE_DIR = Path(os.environ.get(
    "LLM_WIKI_OPCODE_DIR",
    "/tmp/llm-wiki-opencode",
))

# Default poll timeout in seconds
DEFAULT_TIMEOUT = int(os.environ.get("LLM_WIKI_OPCODE_TIMEOUT", "300"))


def _ts() -> str:
    """Timestamp for unique request IDs."""
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def _approx_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English text."""
    return max(1, len(text) // 4)


class OpenCodeProvider:
    """Routes LLM calls through the Hermes agent's own model context.

    Detection: Auto-initialized when detect_default_provider() returns
    'opencode' — i.e., when HERMES_SESSION_ID, CLAUDE_CODE_SESSION,
    CODEX_SESSION, or LLM_WIKI_AGENT_MODE=1 is set in the environment.

    Two operational modes:
        - Subprocess mode (default): pipe-based IPC via filesystem files.
          Writes prompt, signals parent, waits for response.
        - Library mode: direct model access via Hermes SDK (future).
    """

    def __init__(self):
        self.session_id = (
            os.environ.get("HERMES_SESSION_ID")
            or os.environ.get("CLAUDE_CODE_SESSION")
            or os.environ.get("CODEX_SESSION")
            or "unknown"
        )
        self.model = os.environ.get("HERMES_MODEL", "agent-native")
        if not self.session_id or self.session_id == "unknown":
            raise ProviderNotAvailableError(
                "opencode provider requires running inside an AI agent session "
                "(set HERMES_SESSION_ID, CLAUDE_CODE_SESSION, CODEX_SESSION, "
                "or LLM_WIKI_AGENT_MODE=1)"
            )
        self._request_counter = 0

    @property
    def supports_streaming(self) -> bool:
        return True

    @property
    def supports_structured_output(self) -> bool:
        return True

    def call(self, system: str, user: str, **kwargs) -> LLMResponse:
        """Route the LLM call through the agent's model.

        Args:
            system: System prompt / instructions.
            user: User message / content to process.
            **kwargs: Additional params (timeout, temperature, etc.).

        Returns:
            LLMResponse with the model's output text.
        """
        # Read timeout at call time so tests can monkeypatch the env
        timeout = kwargs.get("timeout") or int(
            os.environ.get("LLM_WIKI_OPCODE_TIMEOUT", "300")
        )

        # Try LLM_WIKI_RESPONSE_FILE first (fast path if already set)
        response = self._call_via_response_file(system, user)
        if response is not None:
            return response

        # Try pipe-based IPC
        response = self._call_via_pipe(system, user, timeout)
        if response is not None:
            return response

        # Neither worked — print prompts so a human can respond
        return self._call_via_stderr(system, user)

    def _call_via_pipe(self, system: str, user: str,
                       timeout: int) -> Optional[LLMResponse]:
        """Pipe-based IPC: write prompt, signal parent, wait for response.

        The parent agent (Hermes runtime or compatible watcher) monitors
        the opcode directory for .ready files, processes them, and writes
        .response files. This is the fast path when infrastructure exists.
        """
        try:
            self._request_counter += 1
            request_id = f"{_ts()}-{self._request_counter:04d}"
            req_dir = OPCODE_DIR / self.session_id / request_id
            req_dir.mkdir(parents=True, exist_ok=True)

            # Write prompt
            prompt_path = req_dir / "prompt.json"
            prompt_data = {
                "request_id": request_id,
                "session_id": self.session_id,
                "model": self.model,
                "system": system,
                "user": user,
                "timestamp": datetime.now().isoformat(),
            }
            prompt_path.write_text(json.dumps(prompt_data, indent=2))

            # Signal readiness
            ready_path = req_dir / ".ready"
            ready_path.touch()

            # Also print to stderr so parent can see it immediately
            sep = "=" * 70
            print(f"\n{sep}\n  SYSTEM PROMPT [opencode]:\n{sep}\n{system}",
                  file=sys.stderr)
            print(f"\n{sep}\n  USER PROMPT [opencode]:\n{sep}\n{user}",
                  file=sys.stderr)

            # Poll for response
            response_path = req_dir / "response.json"
            deadline = time.time() + timeout
            while time.time() < deadline:
                if response_path.exists():
                    try:
                        resp_data = json.loads(response_path.read_text())
                        text = resp_data.get("response", "")
                        model_used = resp_data.get("model", self.model)
                        return LLMResponse(
                            text=text,
                            model=model_used,
                            input_tokens=_approx_tokens(system + user),
                            output_tokens=_approx_tokens(text),
                            cost=0.0,  # agent-native, no per-call cost
                            provider="opencode",
                        )
                    except (json.JSONDecodeError, IOError) as e:
                        print(f"  ⚠  opencode: response parse error: {e}",
                              file=sys.stderr)
                        return None
                time.sleep(1)

            # Timeout — signal that we gave up
            print(f"  ⚠  opencode: timeout after {timeout}s waiting for "
                  f"response at {response_path}", file=sys.stderr)
            return None

        except (IOError, OSError) as e:
            print(f"  ⚠  opencode: pipe IPC failed: {e}", file=sys.stderr)
            return None

    def _call_via_response_file(self, system: str,
                                user: str) -> Optional[LLMResponse]:
        """Fallback: use LLM_WIKI_RESPONSE_FILE if set.

        This is the existing manual/offline path. The user or agent sets
        LLM_WIKI_RESPONSE_FILE to a path, pastes/writes the LLM response
        there, and the script reads it back.
        """
        rf = os.environ.get("LLM_WIKI_RESPONSE_FILE")
        if not rf:
            return None

        try:
            response_path = Path(rf)
            if not response_path.exists():
                return None

            text = response_path.read_text(encoding="utf-8").strip()
            if not text:
                return None

            return LLMResponse(
                text=text,
                model=self.model,
                input_tokens=_approx_tokens(system + user),
                output_tokens=_approx_tokens(text),
                cost=0.0,
                provider="opencode",
            )
        except (IOError, OSError):
            return None

    def _call_via_stderr(self, system: str, user: str) -> LLMResponse:
        """Last resort: print prompts to stderr, return empty response.

        The prompts were already printed above. This returns an empty
        LLMResponse so the caller can detect the failure.
        """
        return LLMResponse(
            text="",
            model=self.model,
            input_tokens=_approx_tokens(system + user),
            output_tokens=0,
            cost=0.0,
            provider="opencode",
        )
