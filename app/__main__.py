"""Command line: analyze Myanglish customer messages.

    python -m app "size M shi lar sis, bl lout lal"
    python -m app --model Claude "yout pyi lar" --context "Customer ordered a bag on Monday"
    echo "hello admin" | python -m app          # one message per line from stdin
"""
import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from app.analyzer import DEFAULT_MODEL, Analyzer
from src.evaluator import MODELS

ROOT = Path(__file__).resolve().parent.parent


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Analyze Myanglish customer messages.")
    ap.add_argument("message", nargs="?", help="message to analyze (default: read lines from stdin)")
    ap.add_argument("--model", default=DEFAULT_MODEL, choices=list(MODELS))
    ap.add_argument("--context", help="earlier conversation needed to understand the message")
    args = ap.parse_args()
    load_dotenv(ROOT / ".env")
    analyzer = Analyzer(args.model)
    messages = [args.message] if args.message else [l for l in sys.stdin if l.strip()]
    for m in messages:
        print(json.dumps(analyzer.analyze(m, args.context).to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
