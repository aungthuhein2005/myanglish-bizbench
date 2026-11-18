"""Open-weight models (DeepSeek, Qwen, Gemma, ...) served through OpenRouter.

OpenRouter exposes an OpenAI-compatible API, so this reuses the OpenAI request shape.
`require_parameters` makes OpenRouter route only to hosts that honour the JSON schema.
"""
from __future__ import annotations

import os

from openai import OpenAI

from src.adapters.openai import OpenAICompatibleAdapter

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterAdapter(OpenAICompatibleAdapter):
    extra_body = {"provider": {"require_parameters": True}}

    # 8000 (not 16000): OpenRouter reserves credit for max_tokens up front.
    def __init__(self, model_id: str, max_output_tokens: int = 8000):
        client = OpenAI(
            api_key=os.environ["OPEN_ROUTER_API_KEY"],
            base_url=OPENROUTER_BASE_URL,
            max_retries=4,
        )
        super().__init__(model_id, client, max_output_tokens)
