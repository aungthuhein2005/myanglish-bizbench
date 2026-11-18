"""Model adapters. Each adapter sends one system + user prompt and returns a ModelResponse."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.schemas import ModelResponse


class Adapter(ABC):
    def __init__(self, model_id: str, max_output_tokens: int = 16000):
        self.model_id = model_id
        self.max_output_tokens = max_output_tokens

    @abstractmethod
    def generate(self, system: str, user: str, schema: dict) -> ModelResponse:
        """Return the model's JSON text answer plus token usage."""


def get_adapter(provider: str, model_id: str) -> Adapter:
    if provider == "openai":
        from src.adapters.openai import OpenAIAdapter
        return OpenAIAdapter(model_id)
    if provider == "gemini":
        from src.adapters.gemini import GeminiAdapter
        return GeminiAdapter(model_id)
    if provider == "anthropic":
        from src.adapters.anthropic import AnthropicAdapter
        return AnthropicAdapter(model_id)
    if provider == "local":
        from src.adapters.local import OpenRouterAdapter
        return OpenRouterAdapter(model_id)
    raise ValueError(f"unknown provider {provider!r}")
