"""Standardize the `entities` field of merged.json to the 15-key entity schema.

Usage:
    python scripts/standardize_entities.py [path/to/data/interim/merged.json]

Rewrites the file in place. Before the first run it saves a copy of the original to
`merged.before_entity_std.json`. Running it again on standardized data changes nothing.

Value format: a single value is stored as a scalar, several values as a list (deduplicated,
in order of first appearance). Quantities and prices are integers.
"""
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT / "data" / "interim" / "merged.json"

STANDARD_KEYS = [
    "product", "brand", "quantity", "size", "color", "variant", "price", "currency",
    "location", "payment_method", "delivery_method", "delivery_fee", "order_id",
    "date_time", "issue",
]

# old key -> standard key, or None to drop the key.
KEY_MAP = {**{k: k for k in STANDARD_KEYS},
    # product
    "product_type": "product", "item_type": "product",
    # quantity / size / color (order details and changes)
    "retained_quantity": "quantity",
    "preferred_size": "size", "alternative_size": "size", "ordered_size": "size", "received_size": "size",
    "retained_color": "color", "cancelled_color": "color",
    # variant: material, feature or compatible model the customer asks about
    "materials": "variant", "feature": "variant",
    "required_compatible_model": "variant", "excluded_compatible_model": "variant",
    # price
    "price_amounts": "price", "mentioned_price": "price", "budget": "price",
    # location / payment / delivery
    "delivery_city": "location", "destination": "location",
    "payment_methods": "payment_method",
    "shipping_method": "delivery_method",
    # date_time
    "order_date": "date_time", "order_date_relative": "date_time", "order_day": "date_time",
    "reference_time": "date_time", "time_reference": "date_time", "delay_duration": "date_time",
    "expected_arrival": "date_time", "promised_delivery_relative": "date_time",
    "promotion_period": "date_time", "event": "date_time",
    # issue
    "issues": "issue", "defect": "issue", "reason": "issue", "tracking_status": "issue",
    # dropped: not a business entity in this schema, or already covered by the intent label
    "honorific": None, "item_reference": None, "reference": None, "purpose": None,
    "attribute": None, "product_attribute": None, "skin_type": None, "preference": None,
    "stock_type": None, "tag_status": None, "customer_name": None, "phone": None,
    "fee_type": None, "requested_resolution": None, "cancellation_condition": None,
    "payment_status": None, "payment_proof": None, "attachment": None, "follow_up_count": None,
}

PAYMENT_NAMES = {"kpay": "KBZPay", "kbzpay": "KBZPay", "cod": "COD", "cash_on_delivery": "COD",
                 "wavepay": "WavePay"}
ISSUE_NAMES = {"tracking_status:not_provided": "tracking not provided"}


def as_list(v):
    return list(v) if isinstance(v, list) else [v]


def to_int(v):
    if isinstance(v, int):
        return v
    digits = re.sub(r"[^\d]", "", str(v))
    return int(digits) if digits else v


def clean_value(std_key, old_key, v):
    if std_key in ("quantity", "price", "delivery_fee"):
        return to_int(v)
    if std_key == "payment_method":
        return PAYMENT_NAMES.get(str(v).lower(), v)
    if std_key == "issue":
        v = ISSUE_NAMES.get(f"{old_key}:{v}", v)
        return str(v).replace("_", " ")
    return v


def standardize(entities):
    out = {}

    def add(key, value):
        lst = out.setdefault(key, [])
        if value not in lst:
            lst.append(value)

    for old_key, value in entities.items():
        if old_key == "items":  # order lines: [{"color": ..., "quantity": ...}, ...]
            for line in value:
                for k, v in line.items():
                    add(KEY_MAP[k], clean_value(KEY_MAP[k], k, v))
            continue
        if old_key not in KEY_MAP:
            raise KeyError(f"no mapping for entity key {old_key!r}")
        std_key = KEY_MAP[old_key]
        if std_key is None:
            continue
        for v in as_list(value):
            add(std_key, clean_value(std_key, old_key, v))
        if old_key == "mentioned_price" and "MMK" in str(value):
            add("currency", "MMK")

    ordered = {k: out[k] for k in STANDARD_KEYS if k in out}
    return {k: v[0] if len(v) == 1 else v for k, v in ordered.items()}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DATA
    backup = path.with_name(path.stem + ".before_entity_std.json")
    if not backup.exists():
        shutil.copyfile(path, backup)
        print(f"Backup written to {backup}")
    with open(path, encoding="utf-8") as fh:
        records = json.load(fh)
    changed = 0
    for r in records:
        new = standardize(r["entities"])
        if new != r["entities"]:
            changed += 1
            r["entities"] = new
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)
    print(f"Standardized entities in {changed} of {len(records)} records.")


if __name__ == "__main__":
    main()
