"""Scoring: multi-label intent F1 (macro / micro), exact match, entity F1 and cost."""
from __future__ import annotations

import re
from collections import Counter

from src.schemas import ENTITY_KEYS, INTENTS


def f1(tp: int, fp: int, fn: int) -> float:
    if tp == 0:
        return 0.0 if (fp or fn) else 1.0
    p, r = tp / (tp + fp), tp / (tp + fn)
    return 2 * p * r / (p + r)


def intent_scores(gold: list[list[str]], pred: list[list[str]]) -> dict:
    """Multi-label intent metrics. Macro F1 averages over labels present in gold or pred."""
    per = {lab: Counter() for lab in INTENTS}
    exact = 0
    for g, p in zip(gold, pred):
        g, p = set(g), set(p)
        exact += g == p
        for lab in INTENTS:
            if lab in g and lab in p:
                per[lab]["tp"] += 1
            elif lab in p:
                per[lab]["fp"] += 1
            elif lab in g:
                per[lab]["fn"] += 1
    used = [lab for lab in INTENTS if sum(per[lab].values())]
    per_label = {lab: f1(per[lab]["tp"], per[lab]["fp"], per[lab]["fn"]) for lab in used}
    tot = sum((per[lab] for lab in INTENTS), Counter())
    return {
        "macro_f1": sum(per_label.values()) / len(per_label) if per_label else 0.0,
        "micro_f1": f1(tot["tp"], tot["fp"], tot["fn"]),
        "exact_match": exact / len(gold) if gold else 0.0,
        "per_intent_f1": per_label,
    }


# ---- entities ------------------------------------------------------------

def norm_value(key: str, value) -> str:
    """Lenient normalisation so 'Phone_Case' == 'phone case' and '30,000 MMK' == 30000."""
    s = str(value).strip().lower()
    if key in ("quantity", "price", "delivery_fee"):
        digits = re.sub(r"[^\d]", "", s)
        return digits or s
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r"[^\w\s.]", " ", s)
    return " ".join(s.split())


def gold_pairs(entities: dict) -> set[tuple[str, str]]:
    pairs = set()
    for k, v in entities.items():
        for x in (v if isinstance(v, list) else [v]):
            pairs.add((k, norm_value(k, x)))
    return pairs


def pred_pairs(entities: list[dict]) -> set[tuple[str, str]]:
    return {(e["key"], norm_value(e["key"], e["value"]))
            for e in entities if e.get("key") in ENTITY_KEYS and str(e.get("value", "")).strip()}


def entity_scores(gold: list[dict], pred: list[list[dict]]) -> dict:
    """Micro F1 over (key, normalised value) pairs, plus a key-only variant."""
    c, ck = Counter(), Counter()
    for g, p in zip(gold, pred):
        gp, pp = gold_pairs(g), pred_pairs(p)
        c["tp"] += len(gp & pp); c["fp"] += len(pp - gp); c["fn"] += len(gp - pp)
        gk, pk = Counter(k for k, _ in gp), Counter(k for k, _ in pp)
        ck["tp"] += sum((gk & pk).values()); ck["fp"] += sum((pk - gk).values())
        ck["fn"] += sum((gk - pk).values())
    return {"entity_f1": f1(c["tp"], c["fp"], c["fn"]),
            "entity_key_f1": f1(ck["tp"], ck["fp"], ck["fn"])}


# ---- cost ----------------------------------------------------------------

def cost_usd(input_tokens: int, output_tokens: int, price: dict | None) -> float | None:
    """price = {"input": $/token, "output": $/token}."""
    if not price:
        return None
    return input_tokens * price["input"] + output_tokens * price["output"]
