"""Final validation and freeze of a Myanglish-BizBench release.

Usage:
    python scripts/freeze_dataset.py            # check merged.json and freeze it as data/v0.1/test.jsonl
    python scripts/freeze_dataset.py --verify   # check the frozen file is unchanged (checksum + checks)
    python scripts/freeze_dataset.py --version v0.2 [--verify]
                                                # freeze/verify data/v0.2 from data/v0.2/reviewed.json

Freezing writes:
    data/v0.1/test.jsonl      one record per line, UTF-8
    data/v0.1/MANIFEST.json   counts, SHA-256 checksum and freeze policy
and marks both files read-only. An existing frozen version is never overwritten.
"""
import hashlib
import json
import os
import stat
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_dataset import ENTITY_KEYS, INTENTS, REQUIRED_FIELDS, norm_text, validate  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# Per-version settings. v0.2 also requires `issue` values from the fixed issue list, and its
# intent annotation total is not fixed in advance (the review may add or remove labels).
VERSIONS = {
    "v0.1": {"source": ROOT / "data" / "interim" / "merged.json", "intent_annotations": 148, "issue_types": False},
    "v0.2": {"source": ROOT / "data" / "v0.2" / "reviewed.json", "intent_annotations": None,
             "issue_types": True},
}
VERSION = sys.argv[sys.argv.index("--version") + 1] if "--version" in sys.argv else "v0.1"
if VERSION not in VERSIONS:
    sys.exit(f"unknown version {VERSION!r}; choose from {', '.join(VERSIONS)}")
CONFIG = VERSIONS[VERSION]
SOURCE = CONFIG["source"]
OUT_DIR = ROOT / "data" / VERSION
OUT_FILE = OUT_DIR / "test.jsonl"
MANIFEST = OUT_DIR / "MANIFEST.json"

EXPECTED_TOTAL = 100
EXPECTED_INTENT_ANNOTATIONS = CONFIG["intent_annotations"]
POLICY = ("Frozen test set. Do not modify this version based on model performance, "
          "and do not use it for training or fine-tuning. Changes go into a new version.")


def final_checks(records):
    """Return a list of (check, expected, actual, passed) rows."""
    ids = [r.get("id") for r in records]
    texts = Counter(norm_text(r["text"]) for r in records if isinstance(r.get("text"), str))
    bad_intents = sum(1 for r in records for i in r.get("intents", []) if i not in INTENTS)
    bad_keys = sum(1 for r in records for k in r.get("entities", {}) if k not in ENTITY_KEYS)
    missing = sum(1 for r in records for f in REQUIRED_FIELDS if f not in r)
    annotations = sum(len(r.get("intents", [])) for r in records)
    ctx = [r for r in records if r.get("context") is not None]
    ctx_ok = all(isinstance(r["context"], str) and r["context"].strip() for r in ctx)
    issue_types = None
    if CONFIG["issue_types"]:
        sys.path.insert(0, str(ROOT))
        from src.schemas import ISSUE_TYPES
        issue_types = set(ISSUE_TYPES)
    summary = validate(records, issue_types)

    return [
        ("Total samples", EXPECTED_TOTAL, len(records), len(records) == EXPECTED_TOTAL),
        ("Unique IDs", EXPECTED_TOTAL, len(set(ids)), len(set(ids)) == len(records) == EXPECTED_TOTAL),
        ("Duplicate messages", 0, sum(v - 1 for v in texts.values()), all(v == 1 for v in texts.values())),
        ("Invalid intent labels", 0, bad_intents, bad_intents == 0),
        ("Invalid entity keys", 0, bad_keys, bad_keys == 0),
        ("Missing required fields", 0, missing, missing == 0),
        ("Total intent annotations", EXPECTED_INTENT_ANNOTATIONS or "(reported)", annotations,
         EXPECTED_INTENT_ANNOTATIONS is None or annotations == EXPECTED_INTENT_ANNOTATIONS),
        ("Context-dependent messages", "Context provided",
         f"{len(ctx)} messages, context {'provided' if ctx_ok else 'MISSING'}", ctx_ok),
        ("Full schema validation (validate_dataset.py)", "PASS", summary["status"], summary["status"] == "PASS"),
    ]


def print_checks(rows):
    w = max(len(r[0]) for r in rows)
    print(f"{'Validation'.ljust(w)}  {'Expected':<18} {'Actual':<30} Result")
    for name, exp, act, ok in rows:
        print(f"{name.ljust(w)}  {str(exp):<18} {str(act):<30} {'PASS' if ok else 'FAIL'}")
    passed = all(r[3] for r in rows)
    print(f"\nFinal status: {'PASS' if passed else 'FAIL'}")
    return passed


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def make_read_only(path):
    os.chmod(path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)


def freeze():
    if OUT_FILE.exists() or MANIFEST.exists():
        sys.exit(f"{OUT_DIR} is already frozen; it will not be overwritten. "
                 "Create a new version instead, or run with --verify.")
    with open(SOURCE, encoding="utf-8") as fh:
        records = json.load(fh)
    if not print_checks(final_checks(records)):
        sys.exit("Checks failed; nothing was written.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8", newline="\n") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Re-read what was written and check it round-trips exactly.
    if read_jsonl(OUT_FILE) != records:
        OUT_FILE.unlink()
        sys.exit("Written file does not match the source; removed it.")

    manifest = {
        "name": "Myanglish-BizBench",
        "version": VERSION,
        "split": "test",
        "file": OUT_FILE.name,
        "format": "jsonl",
        "frozen_on": date.today().isoformat(),
        "samples": len(records),
        "intent_annotations": sum(len(r["intents"]) for r in records),
        "source_models": dict(Counter(r["source_model"] for r in records)),
        "sha256": sha256(OUT_FILE),
        "policy": POLICY,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    make_read_only(OUT_FILE)
    make_read_only(MANIFEST)
    print(f"\nFrozen {len(records)} samples to {OUT_FILE}")
    print(f"SHA-256: {manifest['sha256']}")


def verify():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    actual = sha256(OUT_FILE)
    ok_hash = actual == manifest["sha256"]
    print(f"Checksum: {'PASS' if ok_hash else 'FAIL'} ({actual})\n")
    ok_checks = print_checks(final_checks(read_jsonl(OUT_FILE)))
    sys.exit(0 if ok_hash and ok_checks else 1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    verify() if "--verify" in sys.argv else freeze()
