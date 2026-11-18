"""Shared data structures, label sets and the prompt/output schema for the benchmark."""
from __future__ import annotations

from dataclasses import dataclass, field

INTENTS = [
    "greeting", "price_inquiry", "product_inquiry", "stock_availability",
    "place_order", "payment_inquiry", "delivery_inquiry", "discount_inquiry",
    "order_cancellation", "refund_exchange", "customer_complaint", "unknown",
]

ENTITY_KEYS = [
    "product", "brand", "quantity", "size", "color", "variant", "price", "currency",
    "location", "payment_method", "delivery_method", "delivery_fee", "order_id",
    "date_time", "issue",
]

INTENT_DESCRIPTIONS = {
    "greeting": "hello / hi / are you there, with no other request",
    "price_inquiry": "asks how much something costs or the total price",
    "product_inquiry": "asks about product details, material, quality, fit or suitability",
    "stock_availability": "asks whether an item, size or colour is in stock",
    "place_order": "wants to buy / confirms an order / gives order details",
    "payment_inquiry": "asks about payment methods or reports a payment",
    "delivery_inquiry": "asks about delivery, shipping fee, delivery time or order status",
    "discount_inquiry": "asks for a discount, promotion or lower price",
    "order_cancellation": "wants to cancel or change part of an order",
    "refund_exchange": "wants a refund, exchange or return",
    "customer_complaint": "complains about a product, delay, service or wrong item",
    "unknown": "no clear business intent (emoji only, slang, unclear)",
}

ENTITY_DESCRIPTIONS = {
    "product": "product type, in English (e.g. bag, shirt, serum, phone case)",
    "brand": "brand name",
    "quantity": "number of items, digits only",
    "size": "size as written (e.g. M, XL, 38)",
    "color": "colour in English, lowercase",
    "variant": "material, feature or model variant (e.g. genuine leather, iPhone 13)",
    "price": "a price or budget amount, digits only in kyat (e.g. 30000)",
    "currency": "currency code (e.g. MMK)",
    "location": "city / township / delivery destination",
    "payment_method": "payment method (e.g. KBZPay, WavePay, COD)",
    "delivery_method": "how it is delivered (e.g. highway bus gate, express)",
    "delivery_fee": "a delivery fee amount, digits only",
    "order_id": "order or tracking number",
    "date_time": "time expression in English (e.g. today, yesterday, 3 days)",
    "issue": "the problem the customer reports, short English phrase",
}

SYSTEM_PROMPT = (
    "You annotate customer messages sent to Myanmar online shops. Messages are written in "
    "Myanglish (Burmese written in Latin letters), often mixed with English words.\n\n"
    "For each message return:\n"
    "1. intents: every intent the message expresses (one or more) from this list:\n"
    + "\n".join(f"   - {k}: {v}" for k, v in INTENT_DESCRIPTIONS.items())
    + "\n2. entities: business entities explicitly mentioned in the message, as key/value pairs. "
    "Allowed keys:\n"
    + "\n".join(f"   - {k}: {v}" for k, v in ENTITY_DESCRIPTIONS.items())
    + "\n\nRules: only extract entities that are stated in the message; do not guess. Use one "
    "key/value pair per value (two colours = two pairs). Return an empty entities list when "
    "there are none. Do not include honorifics (sis, bro, admin) as entities."
)

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "intents": {"type": "array", "items": {"type": "string", "enum": INTENTS}},
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "enum": ENTITY_KEYS},
                    "value": {"type": "string"},
                },
                "required": ["key", "value"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["intents", "entities"],
    "additionalProperties": False,
}


SYSTEM_PROMPT_V01 = SYSTEM_PROMPT  # frozen: used to reproduce v0.1 results

# ---- v0.2: prompt aligned with reports/annotation_guidelines_v0.2.md -------------------

ISSUE_TYPES = {
    "wrong_size": "size too small / too big / does not fit",
    "damaged_item": "broken, cracked, torn or defective on arrival",
    "wrong_item": "received a different item, size or colour than ordered",
    "color_mismatch": "colour differs from the photo",
    "not_as_described": "item differs from the photo or description (other than colour)",
    "poor_quality": "low quality, thin or cheap material",
    "late_delivery": "delivery slower than promised",
    "not_received": "order or refund not received",
    "missing_tracking": "no tracking number or status update",
    "slow_response": "shop does not reply",
    "out_of_stock": "item no longer available",
    "payment_issue": "payment problem (failed, charged twice, payment refund)",
    "other": "any other problem",
}

INTENT_DESCRIPTIONS_V02 = {
    **INTENT_DESCRIPTIONS,
    "greeting": "hello / hi / mingalarpar; can appear together with other intents "
                "(honorifics like sis or bro alone are not a greeting)",
    "price_inquiry": "asks for a price or total amount (asking for a lower price is discount_inquiry)",
    "product_inquiry": "asks what the product is like: material, quality, fit, suitability, "
                       "which colours or sizes it comes in",
    "stock_availability": "asks whether an item, size or colour is available / in stock",
    "order_cancellation": "cancels all or part of an order",
    "place_order": "orders something new or extra (keeping part of an existing order is not a new order)",
    "customer_complaint": "complains about a product, delay, service or wrong item",
    "unknown": "no determinable business intent (emoji only, insults, unresolvable reference)",
}

ENTITY_DESCRIPTIONS_V02 = {
    **ENTITY_DESCRIPTIONS,
    "product": "product type, English, singular, lowercase (e.g. sneaker, phone case)",
    "price": "price or budget as an integer in kyat; thaung = 10000, thein = 100000",
    "currency": "only if a currency is written (MMK, kyat, ks, $)",
    "location": "place name; one value per place (township and city are separate values)",
    "payment_method": "canonical name: KBZPay, CB Pay, WavePay, AYA Pay, COD, bank transfer",
    "date_time": "dates, days, durations or events in English (today, yesterday, 3 days, 11.11); not 'now'",
    "issue": "one of: " + ", ".join(ISSUE_TYPES),
}

SYSTEM_PROMPT_V02 = (
    "You annotate customer messages sent to Myanmar online shops. Messages are written in "
    "Myanglish (Burmese written in Latin letters), often mixed with English words. Read every "
    "message as a customer writing to the shop.\n\n"
    "For each message return:\n"
    "1. intents: every intent the message itself expresses (one or more). Only add an intent "
    "that has its own words in the message; do not add intents that are merely implied. Intents:\n"
    + "\n".join(f"   - {k}: {v}" for k, v in INTENT_DESCRIPTIONS_V02.items())
    + "\n2. entities: every business entity explicitly mentioned in the message, as key/value "
    "pairs. Allowed keys:\n"
    + "\n".join(f"   - {k}: {v}" for k, v in ENTITY_DESCRIPTIONS_V02.items())
    + "\n   Issue values:\n"
    + "\n".join(f"   - {k}: {v}" for k, v in ISSUE_TYPES.items())
    + "\n\nRules: only extract entities that are stated in the message; do not guess. Use one "
    "key/value pair per value (two colours = two pairs). Return an empty entities list when "
    "there are none. Do not include honorifics (sis, bro, admin) as entities."
)

PROMPTS = {"v0.1": SYSTEM_PROMPT_V01, "v0.2": SYSTEM_PROMPT_V02}


def user_prompt(text: str) -> str:
    return f"Customer message:\n{text}\n\nReturn the JSON annotation."


@dataclass
class Sample:
    id: str
    text: str
    intents: list[str]
    entities: dict
    source_model: str
    difficulty: str
    writing_style: str
    context: str | None = None

    @classmethod
    def from_record(cls, r: dict) -> "Sample":
        return cls(id=r["id"], text=r["text"], intents=r["intents"], entities=r["entities"],
                   source_model=r["source_model"], difficulty=r["difficulty"],
                   writing_style=r["writing_style"], context=r.get("context"))


@dataclass
class ModelResponse:
    """What an adapter returns for one request."""
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str | None = None


@dataclass
class Prediction:
    id: str
    model: str
    intents: list[str] = field(default_factory=list)
    entities: list[dict] = field(default_factory=list)  # [{"key": ..., "value": ...}]
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0
    error: str | None = None
    raw: str = ""
