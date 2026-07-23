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


from llm_wiki.providers.registry import call_llm, detect_default_provider
