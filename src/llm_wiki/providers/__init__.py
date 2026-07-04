"""providers — LLM provider abstraction layer for llm-wiki.

Each provider implements a consistent interface:
    __init__() — initialize, raise ProviderNotAvailableError if unavailable
    call(system, user, **kwargs) -> LLMResponse — make the LLM call
    supports_streaming: bool
    supports_structured_output: bool

Auto-detection via detect_default_provider() determines the best provider
based on the runtime environment (Hermes session, API keys, etc.).

Providers:
    opencode  — Hermes-native (no API key needed, agent's own model)
    openai    — OpenAI SDK (OPENAI_API_KEY)
    anthropic — Anthropic SDK (ANTHROPIC_API_KEY)
    deepseek  — DeepSeek API (DEEPSEEK_API_KEY)
    together  — Together AI API (TOGETHER_API_KEY)
    litellm   — LiteLLM unified interface
"""

import os
from typing import Optional


class LLMResponse:
    """Standardized response from any LLM provider."""

    def __init__(self, text: str, model: str = "unknown",
                 input_tokens: int = 0, output_tokens: int = 0,
                 cost: float = 0.0, provider: str = "unknown"):
        self.text = text
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cost = cost
        self.provider = provider

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __str__(self) -> str:
        return self.text


class ProviderNotAvailableError(Exception):
    """Raised when a provider cannot be initialized (missing keys, wrong env)."""
    pass


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
        6. litellm (if any API key is set — LiteLLM reads from env)
        7. default (offline mode — prompts to stderr)
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
    # LiteLLM works with any key — check last
    if (
        os.environ.get("OPENAI_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
    ):
        return "litellm"

    # No provider available — fall back to offline mode
    return "default"
