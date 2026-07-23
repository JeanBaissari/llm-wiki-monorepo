#!/usr/bin/env python3
"""registry.py — Native SDK integration for LLM Wiki.

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
    from llm_wiki.providers.registry import call_llm, call_llm_structured

    result = call_llm("You are helpful.", "Hello!", provider="openai")
    result = call_llm("You are helpful.", "Hello!", provider="anthropic", model="claude-sonnet-4-20250514")
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, Optional, Type, TypeVar

import tenacity

RETRY_KWARGS: dict[str, Any] = dict(
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=30),
    stop=tenacity.stop_after_attempt(3),
    retry=tenacity.retry_if_exception_type(Exception),
    before_sleep=tenacity.before_log(tenacity.after_log(None, None), None),
    reraise=True,
)

def _retry_decorator():
    return tenacity.retry(
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=30),
        stop=tenacity.stop_after_attempt(3),
        retry=tenacity.retry_if_exception_type(Exception),
        reraise=True,
    )

DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-4-20250514",
    "deepseek": "deepseek-chat",
    "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
}

def _require_key(env_var: str, provider: str) -> str:
    key = os.environ.get(env_var)
    if not key:
        raise RuntimeError(
            f"{env_var} not set. Export it to use provider='{provider}' "
            f"or set LLM_WIKI_RESPONSE_FILE for offline mode."
        )
    return key

def detect_default_provider() -> str:
    if (
        os.environ.get("HERMES_SESSION_ID")
        or os.environ.get("CLAUDE_CODE_SESSION")
        or os.environ.get("CODEX_SESSION")
        or os.environ.get("LLM_WIKI_AGENT_MODE") == "1"
    ):
        return "opencode"

    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("DEEPSEEK_API_KEY"):
        return "deepseek"
    if os.environ.get("TOGETHER_API_KEY"):
        return "together"

    return "default"

def _call_openai(
    system: str,
    user: str,
    model: Optional[str] = None,
    **kwargs: Any,
) -> Optional[str]:
    import openai

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
        print(f"  \u26a0  OpenAI error after retries: {e}", file=sys.stderr)
        return None

def _call_anthropic(
    system: str,
    user: str,
    model: Optional[str] = None,
    **kwargs: Any,
) -> Optional[str]:
    import anthropic

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
        text_blocks = [b.text for b in response.content if b.type == "text"]
        return "\n".join(text_blocks)

    try:
        return _call()
    except Exception as e:
        print(f"  \u26a0  Anthropic error after retries: {e}", file=sys.stderr)
        return None

def _call_litellm(
    system: str,
    user: str,
    model: Optional[str] = None,
    **kwargs: Any,
) -> Optional[str]:
    import litellm

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
        print(f"  \u26a0  LiteLLM error after retries: {e}", file=sys.stderr)
        return None

def _call_deepseek(
    system: str,
    user: str,
    model: Optional[str] = None,
    **kwargs: Any,
) -> Optional[str]:
    import openai

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
        print(f"  \u26a0  DeepSeek error after retries: {e}", file=sys.stderr)
        return None

def _call_together(
    system: str,
    user: str,
    model: Optional[str] = None,
    **kwargs: Any,
) -> Optional[str]:
    import openai

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
        print(f"  \u26a0  Together AI error after retries: {e}", file=sys.stderr)
        return None

def _call_opencode(
    system: str,
    user: str,
    model: Optional[str] = None,
    **kwargs: Any,
) -> Optional[str]:
    import json
    from datetime import datetime
    from pathlib import Path

    session_id = (
        os.environ.get("HERMES_SESSION_ID")
        or os.environ.get("CLAUDE_CODE_SESSION")
        or os.environ.get("CODEX_SESSION")
        or "unknown"
    )
    agent_model = os.environ.get("HERMES_MODEL", "agent-native")

    opcode_dir = Path(os.environ.get(
        "LLM_WIKI_OPCODE_DIR",
        "/tmp/llm-wiki-opencode",
    ))
    timeout = int(os.environ.get("LLM_WIKI_OPCODE_TIMEOUT", "300"))

    def _approx_tokens(text: str) -> int:
        return max(1, len(text) // 4)

    def _ts() -> str:
        return datetime.now().strftime("%Y%m%d-%H%M%S-%f")

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

        ready_path = request_dir / ".ready"
        ready_path.touch()

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
            f"  \u26a1 opencode: prompt written to {prompt_path}\n"
            f"  Waiting for response (timeout: {timeout}s)...",
            file=sys.stderr,
        )

        response_path = request_dir / "response.json"
        deadline = time.time() + timeout
        while time.time() < deadline:
            if response_path.exists():
                try:
                    resp_data = json.loads(response_path.read_text())
                    response_text = resp_data.get("response", "")
                    response_model = resp_data.get("model", agent_model)
                    print(
                        f"  \u2713 opencode: received {len(response_text)} chars "
                        f"from {response_model}",
                        file=sys.stderr,
                    )
                    print(
                        f"  $ cost=$0.00 (agent-native)",
                        file=sys.stderr,
                    )
                    return response_text
                except (json.JSONDecodeError, IOError) as e:
                    print(f"  \u26a0  opencode: response parse error: {e}",
                          file=sys.stderr)
                    return None
            time.sleep(1)

        print(
            f"  \u26a0  opencode: timeout after {timeout}s waiting for response",
            file=sys.stderr,
        )
    except (IOError, OSError) as e:
        print(f"  \u26a0  opencode: pipe IPC failed: {e}", file=sys.stderr)

    rf = os.environ.get("LLM_WIKI_RESPONSE_FILE")
    if rf:
        try:
            response_path = Path(rf)
            if response_path.exists():
                text = response_path.read_text(encoding="utf-8").strip()
                if text:
                    print(
                        f"  \u2713 opencode: read {len(text)} chars from "
                        f"LLM_WIKI_RESPONSE_FILE",
                        file=sys.stderr,
                    )
                    print(f"  $ cost=$0.00 (agent-native)", file=sys.stderr)
                    return text
        except (IOError, OSError):
            pass

    print(
        "  \u26a0  opencode: no response received. "
        "Set LLM_WIKI_RESPONSE_FILE with LLM output.",
        file=sys.stderr,
    )
    return None

PROVIDER_MAP: dict[str, Any] = {
    "opencode": _call_opencode,
    "openai": _call_openai,
    "anthropic": _call_anthropic,
    "litellm": _call_litellm,
    "deepseek": _call_deepseek,
    "together": _call_together,
}

def call_llm(
    system: str,
    user: str,
    provider: str = "default",
    model: Optional[str] = None,
    total_timeout: Optional[int] = None,
    **kwargs: Any,
) -> Optional[str]:
    if provider == "default":
        provider = detect_default_provider()
        if provider == "default":
            _print_prompts(system, user)
            return None

    if provider not in PROVIDER_MAP:
        supported = ", ".join(sorted(PROVIDER_MAP.keys()))
        print(
            f"  \u26a0  Unknown provider '{provider}'. Supported: {supported}",
            file=sys.stderr,
        )
        _print_prompts(system, user)
        return None

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
                    f"  \u26a0  LLM call timed out after {total_timeout}s total "
                    f"(budget limit \u2014 all retries exhausted within deadline)",
                    file=sys.stderr,
                )
                return None

    return PROVIDER_MAP[provider](system, user, model=model, **kwargs)

def _print_prompts(system: str, user: str) -> None:
    sep = "=" * 70
    print(
        f"\n{sep}\n  SYSTEM PROMPT:\n{sep}\n{system}\n\n"
        f"{sep}\n  USER PROMPT:\n{sep}\n{user}",
        file=sys.stderr,
    )

def read_response() -> Optional[str]:
    rf = os.environ.get("LLM_WIKI_RESPONSE_FILE")
    if not rf:
        return None
    try:
        with open(rf, "r", encoding="utf-8") as f:
            return f.read()
    except (FileNotFoundError, IOError):
        return None

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
    import json

    if provider == "default":
        provider = detect_default_provider()
        if provider == "default":
            print(
                "  \u26a0  No LLM provider available for structured output.",
                file=sys.stderr,
            )
            return None

    if provider == "opencode":
        def _do_call() -> Optional[T]:
            return _call_opencode_structured(
                system, user, response_model, model=model, **kwargs
            )
    else:
        import instructor

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
                f"  \u26a0  Structured output not supported for provider '{provider}'. "
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
                    f"  \u26a0  Structured LLM call timed out after {total_timeout}s "
                    f"total (budget limit)",
                    file=sys.stderr,
                )
                return None

    try:
        return _do_call()
    except Exception as e:
        print(f"  \u26a0  Structured LLM error after retries: {e}", file=sys.stderr)
        return None

def _call_opencode_structured(
    system: str,
    user: str,
    response_model: Type[T],
    model: Optional[str] = None,
    **kwargs: Any,
) -> Optional[T]:
    import json as _json

    schema = response_model.model_json_schema()
    schema_json = _json.dumps(schema, indent=2)

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

        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1] if "\n" in text else ""
            if text.endswith("```"):
                text = text[:-3].strip()

        try:
            return response_model.model_validate_json(text)
        except Exception as parse_err:
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
            f"  \u26a0  Structured opencode error after retries: {e}",
            file=sys.stderr,
        )
        return None
