"""Gemini via the Google GenAI SDK, with JSON-schema structured output."""
from __future__ import annotations

import os
import time

from google import genai
from google.genai import errors, types

from src.adapters import Adapter
from src.schemas import ModelResponse

RETRYABLE = {429, 500, 502, 503, 504}


class GeminiAdapter(Adapter):
    def __init__(self, model_id: str, max_output_tokens: int = 16000):
        super().__init__(model_id, max_output_tokens)
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    def generate(self, system: str, user: str, schema: dict) -> ModelResponse:
        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=self.max_output_tokens,
            response_mime_type="application/json",
            response_json_schema=schema,
        )
        for attempt in range(5):
            try:
                response = self.client.models.generate_content(
                    model=self.model_id, contents=user, config=config)
                break
            except errors.APIError as e:
                if e.code in RETRYABLE and attempt < 4:
                    time.sleep(2 ** attempt * 2)
                    continue
                raise
        usage = response.usage_metadata
        output = (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)
        finish = response.candidates[0].finish_reason if response.candidates else None
        return ModelResponse(
            text=response.text or "",
            input_tokens=usage.prompt_token_count or 0,
            output_tokens=output,
            stop_reason=str(finish) if finish else None,
        )
