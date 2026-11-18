"""Write or check SHA256SUMS.txt for every released data, prediction and result file.

Usage:
    python scripts/make_checksums.py           # (re)write SHA256SUMS.txt
    python scripts/make_checksums.py --check   # verify files against SHA256SUMS.txt

Covers data/ and results/ (datasets, review sheets, raw model outputs, predictions, scores, pricing).
The format is the same as `sha256sum`, so `sha256sum -c SHA256SUMS.txt` also works.
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUMS = ROOT / "SHA256SUMS.txt"
DIRS = ["data", "results"]


def files():
    for d in DIRS:
        for p in sorted((ROOT / d).rglob("*")):
            if p.is_file():
                yield p.relative_to(ROOT).as_posix()


def digest(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def main():
    if "--check" in sys.argv:
        bad = 0
        for line in SUMS.read_text(encoding="utf-8").splitlines():
            h, rel = line.split(maxsplit=1)
            rel = rel.lstrip("*")
            ok = (ROOT / rel).is_file() and digest(rel) == h
            bad += not ok
            if not ok:
                print(f"FAILED  {rel}")
        listed = {line.split(maxsplit=1)[1].lstrip("*") for line in SUMS.read_text(encoding="utf-8").splitlines()}
        extra = [f for f in files() if f not in listed]
        for f in extra:
            print(f"NOT LISTED  {f}")
        print("OK" if not bad and not extra else f"{bad} changed, {len(extra)} not listed")
        sys.exit(1 if bad or extra else 0)
    lines = [f"{digest(f)}  {f}" for f in files()]
    SUMS.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {SUMS.name} ({len(lines)} files)")


if __name__ == "__main__":
    main()
