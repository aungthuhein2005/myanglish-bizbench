"""Validate the merged Myanglish-BizBench dataset.

Usage:
    python scripts/validate_dataset.py [path/to/data/interim/merged.json]

Prints the dataset report summary and exits with code 1 if the status is FAIL.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT / "data" / "interim" / "merged.json"

REQUIRED_FIELDS = [
    "id", "source_model", "text", "normalized_burmese", "english_meaning",
    "intents", "entities", "writing_style", "difficulty", "context",
    "requires_clarification",
]
SOURCE_MODELS = {"chatgpt", "claude", "deepseek", "gemini"}
WRITING_STYLES = {"myanglish", "myanglish_english"}
DIFFICULTIES = {"easy", "medium", "hard"}
INTENTS = {
    "greeting", "price_inquiry", "product_inquiry", "stock_availability",
    "place_order", "payment_inquiry", "delivery_inquiry", "discount_inquiry",
    "order_cancellation", "refund_exchange", "customer_complaint", "unknown",
}
# Labels that mean the same thing as a canonical intent but are spelled differently.
INTENT_ALIASES = {
    "refund_and_exchange": "refund_exchange",
    "unknown_intent": "unknown",
}
ENTITY_KEYS = {
    "product", "brand", "quantity", "size", "color", "variant", "price", "currency",
    "location", "payment_method", "delivery_method", "delivery_fee", "order_id",
    "date_time", "issue",
}
INTEGER_ENTITIES = {"quantity", "price", "delivery_fee"}
ID_PATTERN =re.compile(r"^mbb_\d{4}$")
MYANMAR_CHARS = re.compile(r"[က-႟]")


def norm_text(s):
    return " ".join(s.lower().split())


def check_entities(entities, issue_types=None):
    """Entities must use the standard keys; each value is a scalar or a non-empty list of scalars."""
    errors = []
    for k, v in entities.items():
        if k not in ENTITY_KEYS:
            errors.append(f"non-standard entity key '{k}'")
            continue
        values = v if isinstance(v, list) else [v]
        if not values:
            errors.append(f"entity '{k}' is an empty list")
        for x in values:
            if k in INTEGER_ENTITIES:
                if not (isinstance(x, int) and not isinstance(x, bool)):
                    errors.append(f"entity '{k}' value {x!r} must be an integer")
            elif not (isinstance(x, str) and x.strip()):
                errors.append(f"entity '{k}' value {x!r} must be a non-empty string")
            elif k == "issue" and issue_types is not None and x not in issue_types:
                errors.append(f"issue value {x!r} is not an allowed issue type")
    return errors


def check_record(rec, issue_types=None):
    """Return a list of error strings for one record (empty list = valid)."""
    errors = []
    missing = [f for f in REQUIRED_FIELDS if f not in rec]
    errors += [f"missing field '{f}'" for f in missing]
    extra = [f for f in rec if f not in REQUIRED_FIELDS]
    errors += [f"unexpected field '{f}'" for f in extra]

    def has(f):
        return f in rec

    if has("id") and not (isinstance(rec["id"], str) and ID_PATTERN.match(rec["id"])):
        errors.append(f"bad id format: {rec['id']!r}")
    if has("source_model") and rec["source_model"] not in SOURCE_MODELS:
        errors.append(f"unknown source_model: {rec['source_model']!r}")
    for f in ("text", "english_meaning"):
        if has(f) and not (isinstance(rec[f], str) and rec[f].strip()):
            errors.append(f"'{f}' must be a non-empty string")
    # Emoji-only / slang messages labelled 'unknown' may have no real Burmese form,
    # so they only need normalized_burmese to be a string (it may be empty).
    unknown_only = rec.get("intents") == ["unknown"]
    if has("normalized_burmese"):
        v = rec["normalized_burmese"]
        if unknown_only:
            if not isinstance(v, str):
                errors.append("'normalized_burmese' must be a string")
        elif not (isinstance(v, str) and v.strip()):
            errors.append("'normalized_burmese' must be a non-empty string")
        elif not MYANMAR_CHARS.search(v):
            errors.append("'normalized_burmese' contains no Myanmar script")
    if has("intents"):
        v = rec["intents"]
        if not (isinstance(v, list) and v and all(isinstance(i, str) for i in v)):
            errors.append("'intents' must be a non-empty list of strings")
        else:
            for i in v:
                if i in INTENT_ALIASES:
                    errors.append(f"non-canonical intent '{i}' (use '{INTENT_ALIASES[i]}')")
                elif i not in INTENTS:
                    errors.append(f"unknown intent '{i}'")
            if len(set(v)) != len(v):
                errors.append("duplicate intent in list")
    if has("entities"):
        if not isinstance(rec["entities"], dict):
            errors.append("'entities' must be an object")
        else:
            errors += check_entities(rec["entities"], issue_types)
    if has("writing_style") and rec["writing_style"] not in WRITING_STYLES:
        errors.append(f"invalid writing_style: {rec['writing_style']!r}")
    if has("difficulty") and rec["difficulty"] not in DIFFICULTIES:
        errors.append(f"invalid difficulty: {rec['difficulty']!r}")
    if has("context") and rec["context"] is not None and not (
        isinstance(rec["context"], str) and rec["context"].strip()
    ):
        errors.append("'context' must be null or a non-empty string")
    if has("requires_clarification") and not isinstance(rec["requires_clarification"], bool):
        errors.append("'requires_clarification' must be true/false")
    return errors


def validate(records, issue_types=None):
    """Validate all records and return a summary dict."""
    per_record = {}
    for idx, rec in enumerate(records):
        key = rec.get("id", f"<index {idx}>")
        errs = check_record(rec, issue_types)
        if errs:
            per_record[key] = errs

    ids = Counter(r.get("id") for r in records)
    dup_ids = sorted(k for k, v in ids.items() if v > 1)
    for k in dup_ids:
        per_record.setdefault(k, []).append("duplicate id")

    texts = Counter(norm_text(r["text"]) for r in records if isinstance(r.get("text"), str))
    dup_texts = sorted(k for k, v in texts.items() if v > 1)
    duplicate_messages = sum(texts[k] - 1 for k in dup_texts)

    missing_fields = sum(1 for r in records for f in REQUIRED_FIELDS if f not in r)
    intent_lists = [r["intents"] for r in records if isinstance(r.get("intents"), list)]
    unique_intents = sorted({i for lst in intent_lists for i in lst})

    total = len(records)
    invalid = len(per_record)
    status = "PASS" if invalid == 0 and duplicate_messages == 0 and missing_fields == 0 else "FAIL"
    return {
        "total": total,
        "valid": total - invalid,
        "invalid": invalid,
        "duplicate_messages": duplicate_messages,
        "duplicate_texts": dup_texts,
        "missing_fields": missing_fields,
        "unique_intents": unique_intents,
        "multi_intent": sum(1 for lst in intent_lists if len(lst) > 1),
        "context_dependent": sum(1 for r in records if r.get("context") is not None),
        "status": status,
        "errors": per_record,
    }


def format_summary(s):
    return "\n".join([
        "=== Myanglish-BizBench Dataset Report ===",
        "",
        f"Total samples: {s['total']}",
        f"Valid samples: {s['valid']}",
        f"Invalid samples: {s['invalid']}",
        f"Duplicate messages: {s['duplicate_messages']}",
        f"Missing fields: {s['missing_fields']}",
        f"Unique intents: {len(s['unique_intents'])}",
        f"Multi-intent samples: {s['multi_intent']}",
        f"Context-dependent samples: {s['context_dependent']}",
        "",
        f"Status: {s['status']}",
    ])


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = Path(args[0]) if args else DEFAULT_DATA
    issue_types = None
    if "--issue-types" in sys.argv:  # v0.2+: issue values must come from the fixed list
        sys.path.insert(0, str(ROOT))
        from src.schemas import ISSUE_TYPES
        issue_types = set(ISSUE_TYPES)
    summary = validate(load(path), issue_types)
    print(format_summary(summary))
    if summary["errors"]:
        print("\nErrors:")
        for rid, errs in summary["errors"].items():
            for e in errs:
                print(f"  {rid}: {e}")
    if summary["duplicate_texts"]:
        print("\nDuplicate texts:")
        for t in summary["duplicate_texts"]:
            print(f"  {t!r}")
    sys.exit(0 if summary["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
