#!/usr/bin/env python3
"""llm.py — Native SDK integration for LLM Wiki.

Replaces the old subprocess-based call_llm() with native OpenAI, Anthropic,
LiteLLM, and custom provider SDKs. Includes retry logic and structured
output support via instructor.

Providers supported:
    openai    — OpenAI SDK (gpt-4o, gpt-4o-mini, etc.)
    anthropic — Anthropic SDK (claude-sonnet-4-20250514, etc.)
    litellm   — LiteLLM unified interface (any provider LiteLLM supports)
    deepseek  — OpenAI-compatible endpoint (deepseek-chat)
    together  — OpenAI-compatible endpoint (meta-llama/Llama-3.3-70B-Instruct-Turbo, etc.)

API keys are read from environment variables:
    OPENAI_API_KEY, ANTHROPIC_API_KEY, DEEPSEEK_API_KEY, TOGETHER_API_KEY

Usage:
    from llm_wiki.llm import call_llm, call_llm_structured

    result = call_llm("You are helpful.", "Hello!", provider="openai")
    result = call_llm("You are helpful.", "Hello!", provider="anthropic", model="claude-sonnet-4-20250514")
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, Optional, Type, TypeVar

import tenacity

# ── Retry configuration ───────────────────────────────────────────────────

RETRY_EXCEPTIONS = (
    Exception,  # broad catch — tenacity will retry on transient failures
)

RETRY_KWARGS: dict[str, Any] = dict(
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=30),
    stop=tenacity.stop_after_attempt(3),
    retry=tenacity.retry_if_exception_type(RETRY_EXCEPTIONS),
    before_sleep=tenacity.before_log(tenacity.after_log(None, None), None),  # no-op logger
    reraise=True,
)


def _retry_decorator():
    """Create a tenacity retry decorator with sensible defaults."""
    return tenacity.retry(
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=30),
        stop=tenacity.stop_after_attempt(3),
        retry=tenacity.retry_if_exception_type(Exception),
        reraise=True,
    )


# ── Default models per provider ───────────────────────────────────────────

DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-4-20250514",
    "deepseek": "deepseek-chat",
    "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
}


# ── Environment variable helpers ──────────────────────────────────────────

def _require_key(env_var: str, provider: str) -> str:
    """Get an API key from env or raise a clear error."""
    key = os.environ.get(env_var)
    if not key:
        raise RuntimeError(
            f"{env_var} not set. Export it to use provider='{provider}' "
            f"or set LLM_WIKI_RESPONSE_FILE for offline mode."
        )
    return key


def detect_default_provider() -> str:
    """Detect the best available LLM provider based on environment.

    Multi-marker detection: any AI-managed terminal can opt in via
    the generic LLM_WIKI_AGENT_MODE env var, or platform-specific
    markers (HERMES_SESSION_ID, CLAUDE_CODE_SESSION, CODEX_SESSION).

    Priority order:
        1. opencode (if running inside an AI agent session)
        2. openai (if OPENAI_API_KEY is set)
        3. anthropic (if ANTHROPIC_API_KEY is set)
        4. deepseek (if DEEPSEEK_API_KEY is set)
        5. together (if TOGETHER_API_KEY is set)
        6. default (offline mode — prompts to stderr)
    """
    # Agent-native context: use the agent's own model
    if (
        os.environ.get("HERMES_SESSION_ID")
        or os.environ.get("CLAUDE_CODE_SESSION")
        or os.environ.get("CODEX_SESSION")
        or os.environ.get("LLM_WIKI_AGENT_MODE") == "1"
    ):
        return "opencode"

    # Check for configured API keys
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("DEEPSEEK_API_KEY"):
        return "deepseek"
    if os.environ.get("TOGETHER_API_KEY"):
        return "together"

    # No provider available — fall back to offline mode
    return "default"


# ── Provider implementations ──────────────────────────────────────────────

def _call_openai(
    system: str,
    user: str,
    model: Optional[str] = None,
    **kwargs: Any,
) -> Optional[str]:
    """Call OpenAI via the native SDK."""
    import openai  # lazy import — only when used

    client = openai.OpenAI(api_key=_require_key("OPENAI_API_KEY", "openai"))
    model = model or DEFAULT_MODELS["openai"]

    @_retry_decorator()
    def _call() -> str:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=kwargs.get("temperature", 0.3),
            max_tokens=kwargs.get("max_tokens", 4096),
        )
        content = response.choices[0].message.content
        return content or ""

    try:
        return _call()
    except Exception as e:
        print(f"  ⚠  OpenAI error after retries: {e}", file=sys.stderr)
        return None


def _call_anthropic(
    system: str,
    user: str,
    model: Optional[str] = None,
    **kwargs: Any,
) -> Optional[str]:
    """Call Anthropic via the native SDK."""
    import anthropic  # lazy import

    client = anthropic.Anthropic(api_key=_require_key("ANTHROPIC_API_KEY", "anthropic"))
    model = model or DEFAULT_MODELS["anthropic"]

    @_retry_decorator()
    def _call() -> str:
        response = client.messages.create(
            model=model,
            max_tokens=kwargs.get("max_tokens", 4096),
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        # Anthropic returns content blocks; extract text
        text_blocks = [b.text for b in response.content if b.type == "text"]
        return "\n".join(text_blocks)

    try:
        return _call()
    except Exception as e:
        print(f"  ⚠  Anthropic error after retries: {e}", file=sys.stderr)
        return None


def _call_litellm(
    system: str,
    user: str,
    model: Optional[str] = None,
    **kwargs: Any,
) -> Optional[str]:
    """Call via LiteLLM unified interface.

    Provider is specified in the model string, e.g.:
        model="openai/gpt-4o"
        model="anthropic/claude-sonnet-4-20250514"
        model="together_ai/meta-llama/Llama-3.3-70B-Instruct-Turbo"

    When no model is given, falls back to OPENAI_API_KEY with gpt-4o.
    """
    import litellm  # lazy import

    # LiteLLM reads keys from env automatically
    model = model or f"openai/{DEFAULT_MODELS['openai']}"

    @_retry_decorator()
    def _call() -> str:
        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=kwargs.get("temperature", 0.3),
            max_tokens=kwargs.get("max_tokens", 4096),
        )
        content = response.choices[0].message.content
        return content or ""

    try:
        return _call()
    except Exception as e:
        print(f"  ⚠  LiteLLM error after retries: {e}", file=sys.stderr)
        return None


def _call_deepseek(
    system: str,
    user: str,
    model: Optional[str] = None,
    **kwargs: Any,
) -> Optional[str]:
    """Call DeepSeek via OpenAI-compatible endpoint."""
    import openai  # lazy import

    client = openai.OpenAI(
        api_key=_require_key("DEEPSEEK_API_KEY", "deepseek"),
        base_url="https://api.deepseek.com",
    )
    model = model or DEFAULT_MODELS["deepseek"]

    @_retry_decorator()
    def _call() -> str:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=kwargs.get("temperature", 0.3),
            max_tokens=kwargs.get("max_tokens", 4096),
        )
        content = response.choices[0].message.content
        return content or ""

    try:
        return _call()
    except Exception as e:
        print(f"  ⚠  DeepSeek error after retries: {e}", file=sys.stderr)
        return None


def _call_together(
    system: str,
    user: str,
    model: Optional[str] = None,
    **kwargs: Any,
) -> Optional[str]:
    """Call Together AI via OpenAI-compatible endpoint."""
    import openai  # lazy import

    client = openai.OpenAI(
        api_key=_require_key("TOGETHER_API_KEY", "together"),
        base_url="https://api.together.xyz/v1",
    )
    model = model or DEFAULT_MODELS["together"]

    @_retry_decorator()
    def _call() -> str:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=kwargs.get("temperature", 0.3),
            max_tokens=kwargs.get("max_tokens", 4096),
        )
        content = response.choices[0].message.content
        return content or ""

    try:
        return _call()
    except Exception as e:
        print(f"  ⚠  Together AI error after retries: {e}", file=sys.stderr)
        return None


def _call_opencode(
    system: str,
    user: str,
    model: Optional[str] = None,
    **kwargs: Any,
) -> Optional[str]:
    """Call via the Hermes agent's native model (opencode provider).

    When running inside a Hermes agent session, routes the LLM call
    through pipe-based IPC: writes prompt to a known location, signals
    the parent agent, and polls for the response.

    Falls back to LLM_WIKI_RESPONSE_FILE if the pipe IPC times out.
    Prints prompts to stderr as a last resort (offline copy-paste mode).

    No API key required — the agent's existing model is used.
    Cost is always $0.00 (agent-native, included in agent runtime).
    """
    import json
    import time
    from datetime import datetime
    from pathlib import Path

    session_id = (
        os.environ.get("HERMES_SESSION_ID")
        or os.environ.get("CLAUDE_CODE_SESSION")
        or os.environ.get("CODEX_SESSION")
        or "unknown"
    )
    agent_model = os.environ.get("HERMES_MODEL", "agent-native")

    # Determine base directory for opencode IPC
    opcode_dir = Path(os.environ.get(
        "LLM_WIKI_OPCODE_DIR",
        "/tmp/llm-wiki-opencode",
    ))
    timeout = int(os.environ.get("LLM_WIKI_OPCODE_TIMEOUT", "300"))

    def _approx_tokens(text: str) -> int:
        return max(1, len(text) // 4)

    def _ts() -> str:
        return datetime.now().strftime("%Y%m%d-%H%M%S-%f")

    # ── Try pipe-based IPC ──
    try:
        request_dir = opcode_dir / session_id / _ts()
        request_dir.mkdir(parents=True, exist_ok=True)

        prompt_path = request_dir / "prompt.json"
        prompt_data = {
            "session_id": session_id,
            "model": agent_model,
            "system": system,
            "user": user,
            "timestamp": datetime.now().isoformat(),
        }
        prompt_path.write_text(json.dumps(prompt_data, indent=2))

        # Signal readiness
        ready_path = request_dir / ".ready"
        ready_path.touch()

        # Print prompts to stderr so parent agent can see them
        sep = "=" * 70
        print(
            f"\n{sep}\n  SYSTEM PROMPT [opencode]:\n{sep}\n{system}",
            file=sys.stderr,
        )
        print(
            f"\n{sep}\n  USER PROMPT [opencode]:\n{sep}\n{user}",
            file=sys.stderr,
        )
        print(
            f"  ⚡ opencode: prompt written to {prompt_path}\n"
            f"  Waiting for response (timeout: {timeout}s)...",
            file=sys.stderr,
        )

        # Poll for response
        response_path = request_dir / "response.json"
        deadline = time.time() + timeout
        while time.time() < deadline:
            if response_path.exists():
                try:
                    resp_data = json.loads(response_path.read_text())
                    response_text = resp_data.get("response", "")
                    response_model = resp_data.get("model", agent_model)
                    print(
                        f"  ✓ opencode: received {len(response_text)} chars "
                        f"from {response_model}",
                        file=sys.stderr,
                    )
                    print(
                        f"  $ cost=$0.00 (agent-native)",
                        file=sys.stderr,
                    )
                    return response_text
                except (json.JSONDecodeError, IOError) as e:
                    print(f"  ⚠  opencode: response parse error: {e}",
                          file=sys.stderr)
                    return None
            time.sleep(1)

        print(
            f"  ⚠  opencode: timeout after {timeout}s waiting for response",
            file=sys.stderr,
        )
    except (IOError, OSError) as e:
        print(f"  ⚠  opencode: pipe IPC failed: {e}", file=sys.stderr)

    # ── Fallback: LLM_WIKI_RESPONSE_FILE ──
    rf = os.environ.get("LLM_WIKI_RESPONSE_FILE")
    if rf:
        try:
            response_path = Path(rf)
            if response_path.exists():
                text = response_path.read_text(encoding="utf-8").strip()
                if text:
                    print(
                        f"  ✓ opencode: read {len(text)} chars from "
                        f"LLM_WIKI_RESPONSE_FILE",
                        file=sys.stderr,
                    )
                    print(f"  $ cost=$0.00 (agent-native)", file=sys.stderr)
                    return text
        except (IOError, OSError):
            pass

    # ── Last resort: prompts already printed above ──
    print(
        "  ⚠  opencode: no response received. "
        "Set LLM_WIKI_RESPONSE_FILE with LLM output.",
        file=sys.stderr,
    )
    return None


# ── Provider dispatch table ───────────────────────────────────────────────

PROVIDER_MAP: dict[str, Any] = {
    "opencode": _call_opencode,
    "openai": _call_openai,
    "anthropic": _call_anthropic,
    "litellm": _call_litellm,
    "deepseek": _call_deepseek,
    "together": _call_together,
}


# ── Main call_llm function ────────────────────────────────────────────────

def call_llm(
    system: str,
    user: str,
    provider: str = "default",
    model: Optional[str] = None,
    total_timeout: Optional[int] = None,
    **kwargs: Any,
) -> Optional[str]:
    """Call an LLM with the given system and user prompts.

    Args:
        system: System prompt (instructions for the model).
        user: User prompt (the task).
        provider: One of "opencode", "openai", "anthropic", "litellm",
                  "deepseek", "together", or "default".
                  "default" auto-detects: opencode in Hermes context,
                  then checks API keys.
        model: Override the default model for the provider.
        total_timeout: Total deadline in seconds spanning all retries.
                       When set, the entire call (including retries) is
                       aborted if it exceeds this duration. This is a
                       budget/cost control boundary — SDK-level timeouts
                       handle individual network issues. Default: None
                       (let retries exhaust normally).
        **kwargs: Passed through to provider (temperature, max_tokens, etc.).

    Returns:
        The model's text response, or None if all attempts failed.

    Environment:
        HERMES_SESSION_ID    — enables opencode provider (agent-native)
        LLM_WIKI_AGENT_MODE  — generic escape hatch for agent mode
        OPENAI_API_KEY       — required for openai
        ANTHROPIC_API_KEY    — required for anthropic
        DEEPSEEK_API_KEY     — required for deepseek
        TOGETHER_API_KEY     — required for together
        LLM_WIKI_RESPONSE_FILE — fallback file path (read by caller)
        LLM_WIKI_OPCODE_DIR  — opencode IPC directory (default: /tmp/llm-wiki-opencode)
        LLM_WIKI_OPCODE_TIMEOUT — opencode poll timeout in seconds (default: 300)
    """
    # ── "default" provider: auto-detect or fallback ────────────────────────
    if provider == "default":
        # Use the unified detection function (includes opencode for agent context)
        provider = detect_default_provider()
        if provider == "default":
            # Fallback: print prompts to stderr (offline/CLI-paste mode)
            _print_prompts(system, user)
            return None

    # ── Dispatch to the right provider ─────────────────────────────────────
    if provider not in PROVIDER_MAP:
        supported = ", ".join(sorted(PROVIDER_MAP.keys()))
        print(
            f"  ⚠  Unknown provider '{provider}'. Supported: {supported}",
            file=sys.stderr,
        )
        _print_prompts(system, user)
        return None

    # ── Wrap in total timeout if requested ─────────────────────────────────
    if total_timeout is not None:
        from concurrent.futures import (
            ThreadPoolExecutor,
            TimeoutError as FutureTimeoutError,
        )

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                PROVIDER_MAP[provider], system, user, model=model, **kwargs
            )
            try:
                return future.result(timeout=total_timeout)
            except FutureTimeoutError:
                print(
                    f"  ⚠  LLM call timed out after {total_timeout}s total "
                    f"(budget limit — all retries exhausted within deadline)",
                    file=sys.stderr,
                )
                return None

    return PROVIDER_MAP[provider](system, user, model=model, **kwargs)


def _print_prompts(system: str, user: str) -> None:
    """Print prompts to stderr for offline / copy-paste workflows."""
    sep = "=" * 70
    print(
        f"\n{sep}\n  SYSTEM PROMPT:\n{sep}\n{system}\n\n"
        f"{sep}\n  USER PROMPT:\n{sep}\n{user}",
        file=sys.stderr,
    )


# ── Read response from file (backward compat) ─────────────────────────────

def read_response() -> Optional[str]:
    """Read LLM response from LLM_WIKI_RESPONSE_FILE if set."""
    rf = os.environ.get("LLM_WIKI_RESPONSE_FILE")
    if not rf:
        return None
    try:
        with open(rf, "r", encoding="utf-8") as f:
            return f.read()
    except (FileNotFoundError, IOError):
        return None


# ── Structured output via instructor ──────────────────────────────────────

T = TypeVar("T")


def call_llm_structured(
    system: str,
    user: str,
    response_model: Type[T],
    provider: str = "openai",
    model: Optional[str] = None,
    total_timeout: Optional[int] = None,
    **kwargs: Any,
) -> Optional[T]:
    """Call an LLM and parse the response into a Pydantic model via instructor.

    Supports openai, anthropic, litellm, opencode, and auto-detection (default).

    For opencode (agent-native), uses JSON-mode prompting: injects the
    Pydantic model's JSON schema into the system prompt, calls the agent's
    model via pipe-based IPC, and parses the JSON response. No API key
    required — uses the agent's existing model.

    Args:
        system: System prompt.
        user: User prompt.
        response_model: A Pydantic BaseModel subclass defining the output schema.
        provider: Provider name (default: "openai"). Use "default" to auto-detect
                  in Hermes context, or "opencode" explicitly.
        model: Override default model.
        total_timeout: Total deadline in seconds spanning all retries.
                       Default: None (let retries exhaust normally).
        **kwargs: Passed to the provider.

    Returns:
        An instance of response_model, or None on failure.

    Example:
        from pydantic import BaseModel

        class Analysis(BaseModel):
            entities: list[str]
            concepts: list[str]
            summary: str

        result = call_llm_structured(
            "Extract entities from text.",
            "Python and PyTorch are popular.",
            response_model=Analysis,
        )
        if result:
            print(result.entities)
    """
    import json

    # ── Auto-detect provider if "default" ──
    if provider == "default":
        provider = detect_default_provider()
        if provider == "default":
            print(
                "  ⚠  No LLM provider available for structured output.",
                file=sys.stderr,
            )
            return None

    # ── opencode: JSON-mode prompting (agent-native, no API key) ──
    if provider == "opencode":
        def _do_call() -> Optional[T]:
            return _call_opencode_structured(
                system, user, response_model, model=model, **kwargs
            )
    else:
        # ── Native instructor providers ──
        import instructor  # lazy import

        if provider == "openai":
            import openai

            client = instructor.from_openai(
                openai.OpenAI(api_key=_require_key("OPENAI_API_KEY", "openai"))
            )
        elif provider == "anthropic":
            import anthropic

            client = instructor.from_anthropic(
                anthropic.Anthropic(
                    api_key=_require_key("ANTHROPIC_API_KEY", "anthropic")
                )
            )
        elif provider == "litellm":
            import litellm

            client = instructor.from_litellm(litellm.completion)
        else:
            print(
                f"  ⚠  Structured output not supported for provider '{provider}'. "
                f"Use openai, anthropic, litellm, or opencode.",
                file=sys.stderr,
            )
            return None

        model = model or DEFAULT_MODELS.get(provider, "gpt-4o")

        @_retry_decorator()
        def _do_call() -> T:
            return client.chat.completions.create(
                model=model,
                response_model=response_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=kwargs.get("temperature", 0.3),
                max_tokens=kwargs.get("max_tokens", 4096),
            )

    # ── Execute with optional total timeout ────────────────────────────────
    if total_timeout is not None:
        from concurrent.futures import (
            ThreadPoolExecutor,
            TimeoutError as FutureTimeoutError,
        )

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_do_call)
            try:
                return future.result(timeout=total_timeout)
            except FutureTimeoutError:
                print(
                    f"  ⚠  Structured LLM call timed out after {total_timeout}s "
                    f"total (budget limit)",
                    file=sys.stderr,
                )
                return None

    try:
        return _do_call()
    except Exception as e:
        print(f"  ⚠  Structured LLM error after retries: {e}", file=sys.stderr)
        return None


def _call_opencode_structured(
    system: str,
    user: str,
    response_model: Type[T],
    model: Optional[str] = None,
    **kwargs: Any,
) -> Optional[T]:
    """Structured output via opencode provider using JSON-mode prompting.

    Injects the Pydantic model's JSON schema into the prompt, calls the
    agent's model via _call_opencode(), and parses the JSON response.
    """
    import json as _json

    # Build JSON schema from the response model
    schema = response_model.model_json_schema()
    schema_json = _json.dumps(schema, indent=2)

    # Enhance the system prompt with schema instructions
    schema_instructions = (
        f"{system}\n\n"
        f"OUTPUT FORMAT: You MUST respond with ONLY valid JSON matching "
        f"this JSON Schema. Do NOT include any markdown fences, explanations, "
        f"or other text. Just the raw JSON object.\n\n"
        f"```json\n{schema_json}\n```"
    )

    @_retry_decorator()
    def _call_and_parse() -> T:
        raw = _call_opencode(schema_instructions, user, model=model)
        if raw is None:
            raise RuntimeError("opencode returned no response")

        # Strip possible markdown fences
        text = raw.strip()
        if text.startswith("```"):
            # Remove opening fence (```json or ```)
            text = text.split("\n", 1)[-1] if "\n" in text else ""
            # Remove closing fence
            if text.endswith("```"):
                text = text[:-3].strip()

        try:
            return response_model.model_validate_json(text)
        except Exception as parse_err:
            # Try extracting JSON from the text (model may have added prose)
            import re
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                try:
                    return response_model.model_validate_json(json_match.group(0))
                except Exception:
                    pass
            raise parse_err

    try:
        return _call_and_parse()
    except Exception as e:
        print(
            f"  ⚠  Structured opencode error after retries: {e}",
            file=sys.stderr,
        )
        return None
