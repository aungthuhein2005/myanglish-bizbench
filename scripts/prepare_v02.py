"""Create the v0.2 review sheet from the frozen v0.1 test set.

Usage:
    python scripts/prepare_v02.py           # refuses to overwrite an existing review sheet
    python scripts/prepare_v02.py --force   # regenerate it (discards review work in the sheet)

Writes data/v0.2/review_sheet.csv (UTF-8 with BOM, opens in Excel). It contains every sample
and its current labels, but no model predictions, so the review stays blind to model output.

Only purely mechanical schema changes from the v0.2 guidelines are pre-applied:
  * `issue` values mapped to the fixed issue types
  * `location` values like "Yankin, Yangon" split into one value per place
Everything else is left for the reviewer.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "v0.1" / "test.jsonl"
OUT_DIR = ROOT / "data" / "v0.2"
SHEET = OUT_DIR / "review_sheet.csv"

ISSUE_MAP = {
    "tracking not provided": "missing_tracking",
    "size too small": "wrong_size",
    "size too tight": "wrong_size",
    "color mismatch": "color_mismatch",
    "poor quality": "poor_quality",
    "slow response": "slow_response",
    "broken lid": "damaged_item",
    "out of stock": "out_of_stock",
}

COLUMNS = [
    "id", "source_model", "text", "english_meaning", "normalized_burmese",
    "intents", "entities", "requires_clarification", "context", "difficulty", "writing_style",
    "review_status", "reviewer_notes", "v01_intents", "v01_entities", "auto_changes",
]


def as_list(v):
    return v if isinstance(v, list) else [v]


def migrate_entities(entities):
    """Apply the mechanical v0.2 schema changes; return (new_entities, list_of_change_notes)."""
    new, notes = {}, []
    for k, v in entities.items():
        vals = as_list(v)
        if k == "issue":
            mapped = [ISSUE_MAP.get(x, x) for x in vals]
            if mapped != vals:
                notes.append(f"issue {vals} -> {mapped}")
            vals = mapped
        if k == "location":
            split = [p.strip() for x in vals for p in str(x).split(",") if p.strip()]
            if split != vals:
                notes.append(f"location {vals} -> {split}")
            vals = split
        vals = list(dict.fromkeys(vals))
        new[k] = vals[0] if len(vals) == 1 else vals
    return new, notes


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if SHEET.exists() and "--force" not in sys.argv:
        sys.exit(f"{SHEET} already exists (it may contain review work). Use --force to regenerate.")
    with open(SRC, encoding="utf-8") as fh:
        records = [json.loads(line) for line in fh if line.strip()]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    changed = 0
    with open(SHEET, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        for r in records:
            entities, notes = migrate_entities(r["entities"])
            changed += bool(notes)
            w.writerow({
                "id": r["id"], "source_model": r["source_model"], "text": r["text"],
                "english_meaning": r["english_meaning"], "normalized_burmese": r["normalized_burmese"],
                "intents": " ".join(r["intents"]),
                "entities": json.dumps(entities, ensure_ascii=False),
                "requires_clarification": str(r["requires_clarification"]).lower(),
                "context": r["context"] or "",
                "difficulty": r["difficulty"], "writing_style": r["writing_style"],
                "review_status": "", "reviewer_notes": "",
                "v01_intents": " ".join(r["intents"]),
                "v01_entities": json.dumps(r["entities"], ensure_ascii=False),
                "auto_changes": "; ".join(notes),
            })
    print(f"Wrote {SHEET}: {len(records)} samples, {changed} with mechanical schema changes.")


if __name__ == "__main__":
    main()
