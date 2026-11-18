"""Offline tests for the analyzer (fake model, no API calls) and the benchmark metrics.

    python -m unittest discover tests
"""
import json
import unittest

from app.analyzer import Analyzer, decide_route, group_entities, missing_info
from src.adapters import Adapter
from src.metrics import entity_scores, intent_scores
from src.schemas import ModelResponse


class FakeAdapter(Adapter):
    def __init__(self, answer, fail=False):
        super().__init__("fake")
        self.answer, self.fail, self.calls = answer, fail, []

    def generate(self, system, user, schema):
        self.calls.append(user)
        if self.fail:
            raise ConnectionError("network down")
        text = self.answer if isinstance(self.answer, str) else json.dumps(self.answer)
        return ModelResponse(text=text, input_tokens=10, output_tokens=5)


def analyze(answer, message="msg", context=None, fail=False):
    return Analyzer("fake", adapter=FakeAdapter(answer, fail)).analyze(message, context)


class AnalyzerTests(unittest.TestCase):
    def test_complete_order_is_auto(self):
        a = analyze({"intents": ["place_order"], "entities": [
            {"key": "color", "value": "black"}, {"key": "size", "value": "L"},
            {"key": "location", "value": "Yankin"}]})
        self.assertEqual(a.route, "auto")
        self.assertEqual(a.missing_info, [])
        self.assertEqual(a.entities, {"color": ["black"], "size": ["L"], "location": ["Yankin"]})

    def test_order_without_address_asks_for_it(self):
        a = analyze({"intents": ["place_order"], "entities": [{"key": "size", "value": "M"}]})
        self.assertEqual(a.missing_info, ["delivery address (township and city)"])

    def test_sensitive_intents_go_to_human(self):
        a = analyze({"intents": ["customer_complaint", "refund_exchange"], "entities": []})
        self.assertEqual(a.route, "human")
        self.assertIn("sensitive intent: customer_complaint, refund_exchange", a.reasons)

    def test_unknown_goes_to_human(self):
        self.assertEqual(analyze({"intents": ["unknown"], "entities": []}).route, "human")

    def test_invalid_labels_are_dropped(self):
        a = analyze({"intents": ["greeting", "made_up"], "entities": [{"key": "mood", "value": "x"}]})
        self.assertEqual(a.intents, ["greeting"])
        self.assertEqual(a.entities, {})

    def test_model_error_routes_to_human(self):
        a = analyze({}, fail=True)
        self.assertEqual(a.route, "human")
        self.assertIn("ConnectionError", a.error)

    def test_bad_json_routes_to_human(self):
        a = analyze("not json at all")
        self.assertEqual((a.route, a.reasons), ("human", ["model error"]))

    def test_empty_message_skips_model(self):
        adapter = FakeAdapter({"intents": ["greeting"], "entities": []})
        a = Analyzer("fake", adapter=adapter).analyze("   ")
        self.assertEqual(a.route, "human")
        self.assertEqual(adapter.calls, [])

    def test_context_is_sent_to_model(self):
        adapter = FakeAdapter({"intents": ["delivery_inquiry"], "entities": []})
        Analyzer("fake", adapter=adapter).analyze("yout pyi lar", context="ordered a bag Monday")
        self.assertIn("ordered a bag Monday", adapter.calls[0])

    def test_helpers(self):
        self.assertEqual(group_entities([{"key": "color", "value": "red"}, {"key": "color", "value": "red"}]),
                         {"color": ["red"]})
        self.assertEqual(missing_info(["greeting"], {}), [])
        self.assertEqual(decide_route(["greeting", "price_inquiry"]), ("auto", []))
        self.assertEqual(decide_route(["price_inquiry", "stock_availability", "place_order"])[0], "human")


class MetricTests(unittest.TestCase):
    def test_intent_perfect_and_exact_match(self):
        s = intent_scores([["greeting", "price_inquiry"], ["unknown"]],
                          [["price_inquiry", "greeting"], ["greeting"]])
        self.assertEqual(s["exact_match"], 0.5)

    def test_entity_value_normalisation(self):
        s = entity_scores([{"price": 20000, "color": "Black"}],
                          [[{"key": "price", "value": "20000"}, {"key": "color", "value": "black "}]])
        self.assertEqual(s["entity_f1"], 1.0)


if __name__ == "__main__":
    unittest.main()
