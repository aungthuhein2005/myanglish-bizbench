"""GPT models via the OpenAI SDK (Chat Completions + strict JSON schema)."""
from __future__ import annotations

import os

from openai import OpenAI

from src.adapters import Adapter
from src.schemas import ModelResponse


class OpenAICompatibleAdapter(Adapter):
    """Shared by the OpenAI and OpenRouter adapters (same request shape)."""

    extra_body: dict | None = None

    def __init__(self, model_id: str, client: OpenAI, max_output_tokens: int = 16000):
        super().__init__(model_id, max_output_tokens)
        self.client = client

    def generate(self, system: str, user: str, schema: dict) -> ModelResponse:
        kwargs = {}
        if self.extra_body:
            kwargs["extra_body"] = self.extra_body
        response = self.client.chat.completions.create(
            model=self.model_id,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_completion_tokens=self.max_output_tokens,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "annotation", "strict": True, "schema": schema},
            },
            **kwargs,
        )
        choice = response.choices[0]
        usage = response.usage
        return ModelResponse(
            text=choice.message.content or "",
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            stop_reason=choice.finish_reason,
        )


class OpenAIAdapter(OpenAICompatibleAdapter):
    def __init__(self, model_id: str, max_output_tokens: int = 16000):
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], max_retries=4)
        super().__init__(model_id, client, max_output_tokens)
