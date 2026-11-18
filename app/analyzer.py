"""Myanglish customer-message analyzer for online shops.

Turns one customer message into: intents, entities grouped by type, what information is still
missing to act on it, and whether a person should handle it. The LLM call reuses the benchmark's
v0.2 prompt and JSON schema, so the model behaves exactly as it was measured in
reports/final_report.md. Routing and missing-information rules are plain Python, so they are
predictable and testable without API calls.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

from src.adapters import Adapter, get_adapter
from src.evaluator import MODELS, parse_output
from src.schemas import OUTPUT_SCHEMA, PROMPTS, user_prompt

# Benchmark recommendation (final_report.md §7): GPT gives frontier accuracy at the lowest
# frontier cost and ~3 s p90 latency. Any model in src.evaluator.MODELS can be used instead.
DEFAULT_MODEL = "GPT"
PROMPT = PROMPTS["v0.2"]

# Intents that always go to a person: money or an unhappy customer is involved.
HUMAN_INTENTS = {"customer_complaint", "refund_exchange", "order_cancellation"}

# Information a shop needs before it can act on an intent: (any of these entity keys, what to ask).
PRODUCT = ({"product", "variant", "color", "size"}, "which product (name, colour, size or a photo)")
ADDRESS = ({"location"}, "delivery address (township and city)")
# Delivery questions are about a new order (needs a place) or an existing one (needs a reference).
DELIVERY = ({"location", "order_id", "date_time", "product", "delivery_method"},
            "delivery township, or order number if already ordered")
REQUIRED = {
    "place_order": [PRODUCT, ADDRESS],
    "price_inquiry": [PRODUCT],
    "stock_availability": [PRODUCT],
    "delivery_inquiry": [DELIVERY],
}

@dataclass
class Analysis:
    message: str
    intents: list[str] = field(default_factory=list)
    entities: dict[str, list] = field(default_factory=dict)
    missing_info: list[str] = field(default_factory=list)
    route: str = "auto"            # "auto" = safe to draft an automatic reply; "human" = needs a person
    reasons: list[str] = field(default_factory=list)
    model: str = DEFAULT_MODEL
    latency_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def group_entities(entities: list[dict]) -> dict[str, list]:
    out: dict[str, list] = {}
    for e in entities:
        values = out.setdefault(e["key"], [])
        if e["value"] not in values:
            values.append(e["value"])
    return out


def missing_info(intents: list[str], entities: dict[str, list]) -> list[str]:
    asks = []
    for intent in intents:
        for keys, ask in REQUIRED.get(intent, []):
            if not keys & entities.keys() and ask not in asks:
                asks.append(ask)
    return asks


def decide_route(intents: list[str]) -> tuple[str, list[str]]:
    reasons = []
    if not intents or "unknown" in intents:
        reasons.append("intent unclear")
    if hits := sorted(HUMAN_INTENTS & set(intents)):
        reasons.append("sensitive intent: " + ", ".join(hits))
    if len([i for i in intents if i != "greeting"]) >= 3:
        reasons.append("3+ requests in one message")
    return ("human" if reasons else "auto"), reasons


class Analyzer:
    """Reusable analyzer. Pass an adapter to use a custom or fake model (for tests)."""

    def __init__(self, model: str = DEFAULT_MODEL, adapter: Adapter | None = None):
        if adapter is None:
            if model not in MODELS:
                raise ValueError(f"unknown model {model!r}; choose from {', '.join(MODELS)}")
            provider, model_id, _ = MODELS[model]
            adapter = get_adapter(provider, model_id)
        self.model, self.adapter = model, adapter

    def analyze(self, message: str, context: str | None = None) -> Analysis:
        message = message.strip()
        result = Analysis(message=message, model=self.model)
        if not message:
            result.route, result.reasons, result.error = "human", ["empty message"], "empty message"
            return result
        text = f"Earlier in the chat: {context}\nCustomer message: {message}" if context else message
        t0 = time.perf_counter()
        try:
            resp = self.adapter.generate(PROMPT, user_prompt(text), OUTPUT_SCHEMA)
            result.input_tokens, result.output_tokens = resp.input_tokens, resp.output_tokens
            if not resp.text:
                raise ValueError(f"empty model response (stop_reason={resp.stop_reason})")
            intents, entities = parse_output(resp.text)
        except Exception as e:  # never crash the chat: hand the message to a person
            result.latency_s = round(time.perf_counter() - t0, 2)
            result.route, result.reasons = "human", ["model error"]
            result.error = f"{type(e).__name__}: {str(e)[:200]}"
            return result
        result.latency_s = round(time.perf_counter() - t0, 2)
        result.intents = intents
        result.entities = group_entities(entities)
        result.missing_info = missing_info(intents, result.entities)
        result.route, result.reasons = decide_route(intents)
        return result
