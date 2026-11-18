"""Claude via the Anthropic SDK, with JSON-schema structured output."""
from __future__ import annotations

import anthropic

from src.adapters import Adapter
from src.schemas import ModelResponse


class AnthropicAdapter(Adapter):
    def __init__(self, model_id: str, max_output_tokens: int = 16000):
        super().__init__(model_id, max_output_tokens)
        # Reads ANTHROPIC_API_KEY from the environment; SDK retries 429/5xx itself.
        self.client = anthropic.Anthropic(max_retries=4)

    def generate(self, system: str, user: str, schema: dict) -> ModelResponse:
        # No refusal `fallbacks`: a benchmark must score the named model only.
        response = self.client.messages.create(
            model=self.model_id,
            max_tokens=self.max_output_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        text = ""
        if response.stop_reason != "refusal":
            text = next((b.text for b in response.content if b.type == "text"), "")
        return ModelResponse(
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            stop_reason=response.stop_reason,
        )
