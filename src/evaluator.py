"""Run the Myanglish-BizBench evaluation.

Usage (from the project root):
    python -m src.evaluator                         # all models, full test set
    python -m src.evaluator --models claude gpt     # selected models
    python -m src.evaluator --limit 5               # first 5 samples (smoke test)
    python -m src.evaluator --summary-only          # rebuild the results table from saved predictions

Predictions are cached in results/predictions/<model>.jsonl; re-running skips samples that
already have a successful prediction, so an interrupted run can be resumed.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

from src.adapters import get_adapter
from src.metrics import cost_usd, entity_scores, intent_scores
from src.schemas import (ENTITY_KEYS, INTENTS, OUTPUT_SCHEMA, PROMPTS, Prediction, Sample,
                         user_prompt)

ROOT = Path(__file__).resolve().parent.parent
PRICING_CACHE = ROOT / "results" / "pricing.json"

# Benchmark version: selects the test set, the system prompt and the results folder.
# v0.1 keeps its original paths (results/) so its published numbers stay reproducible.
VERSION = "v0.1"
DATA = ROOT / "data" / "v0.1" / "test.jsonl"
RESULTS = ROOT / "results"
PRED_DIR = RESULTS / "predictions"
SCORE_CHART = RESULTS / "figures" / "model_scores.png"


def set_version(version: str) -> None:
    global VERSION, DATA, RESULTS, PRED_DIR, SCORE_CHART
    VERSION = version
    DATA = ROOT / "data" / version / "test.jsonl"
    RESULTS = ROOT / "results" if version == "v0.1" else ROOT / "results" / version
    PRED_DIR = RESULTS / "predictions"
    SCORE_CHART = RESULTS / "figures" / "model_scores.png"

# name -> (adapter, provider model id, OpenRouter catalog id used for pricing)
MODELS = {
    "GPT":      ("openai",    "gpt-6.2-sol",             "openai/gpt-6.2-sol"),
    "Gemini":   ("gemini",    "gemini-4-carbon",         "google/gemini-4-carbon"),
    "Claude":   ("anthropic", "claude-opus-5-5",         "anthropic/claude-opus-5.5"),
    "DeepSeek": ("local",     "deepseek/deepseek-v4-pro", "deepseek/deepseek-v4-pro"),
    "Qwen":     ("local",     "qwen/qwen4-max",          "qwen/qwen4-max"),
    "Gemma":    ("local",     "google/gemma-4-31b-it",   "google/gemma-4-31b-it"),
}


def load_samples(path: Path | None = None) -> list[Sample]:
    path = path or DATA
    with open(path, encoding="utf-8") as fh:
        return [Sample.from_record(json.loads(line)) for line in fh if line.strip()]


def load_pricing(refresh: bool = False) -> dict:
    """$/token prices from the OpenRouter model catalog, cached in results/pricing.json."""
    if PRICING_CACHE.exists() and not refresh:
        return json.loads(PRICING_CACHE.read_text(encoding="utf-8"))
    wanted = {m[2] for m in MODELS.values()}
    data = requests.get("https://openrouter.ai/api/v1/models", timeout=60).json()["data"]
    prices = {m["id"]: {"input": float(m["pricing"]["prompt"]), "output": float(m["pricing"]["completion"])}
              for m in data if m["id"] in wanted}
    out = {"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "source": "https://openrouter.ai/api/v1/models", "prices": prices}
    RESULTS.mkdir(parents=True, exist_ok=True)
    PRICING_CACHE.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def parse_output(text: str) -> tuple[list[str], list[dict]]:
    """Parse the model's JSON; tolerate surrounding prose by taking the outermost {...}."""
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise
        obj = json.loads(text[start:end + 1])
    intents = [i for i in obj.get("intents", []) if i in INTENTS]
    entities = [e for e in obj.get("entities", [])
                if isinstance(e, dict) and e.get("key") in ENTITY_KEYS and "value" in e]
    return list(dict.fromkeys(intents)), entities


def predict_one(adapter, name: str, sample: Sample) -> Prediction:
    pred = Prediction(id=sample.id, model=name)
    t0 = time.perf_counter()
    try:
        resp = adapter.generate(PROMPTS[VERSION], user_prompt(sample.text), OUTPUT_SCHEMA)
        pred.raw = resp.text
        pred.input_tokens, pred.output_tokens = resp.input_tokens, resp.output_tokens
        if not resp.text:
            pred.error = f"empty response (stop_reason={resp.stop_reason})"
        else:
            pred.intents, pred.entities = parse_output(resp.text)
    except json.JSONDecodeError as e:
        pred.error = f"invalid JSON: {e}"
    except Exception as e:  # provider/network errors are recorded and retried on the next run
        pred.error = f"{type(e).__name__}: {str(e)[:300]}"
    pred.latency_s = round(time.perf_counter() - t0, 2)
    return pred


def pred_path(name: str) -> Path:
    return PRED_DIR / f"{name.lower()}.jsonl"


def load_predictions(name: str) -> dict[str, dict]:
    path = pred_path(name)
    if not path.exists():
        return {}
    preds = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                p = json.loads(line)
                preds[p["id"]] = p  # later lines win, so retries overwrite failures
    return preds


def run_model(name: str, samples: list[Sample], workers: int) -> None:
    provider, model_id, _ = MODELS[name]
    # Only API/network errors are retried; a bad answer is a final result, not a retry.
    done = {i for i, p in load_predictions(name).items() if not p.get("error") or is_model_failure(p)}
    todo = [s for s in samples if s.id not in done]
    print(f"[{name}] {model_id}: {len(samples) - len(todo)} cached, {len(todo)} to run")
    if not todo:
        return
    adapter = get_adapter(provider, model_id)
    PRED_DIR.mkdir(parents=True, exist_ok=True)
    errors = 0
    with open(pred_path(name), "a", encoding="utf-8") as fh, ThreadPoolExecutor(workers) as pool:
        futures = [pool.submit(predict_one, adapter, name, s) for s in todo]
        for i, fut in enumerate(as_completed(futures), 1):
            p = fut.result()
            rec = asdict(p) | {"model_id": model_id}
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            if p.error:
                errors += 1
                print(f"  ! {p.id}: {p.error}")
            if i % 20 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} done, {errors} errors")


def is_model_failure(p: dict) -> bool:
    """A failure the model is accountable for (bad/empty answer), as opposed to an API/network error."""
    err = p.get("error") or ""
    return err.startswith(("invalid JSON", "empty response"))


def score_model(name: str, samples: list[Sample], pricing: dict) -> dict | None:
    """Score one model. API/network errors are left out (reported as missing); bad answers count as wrong."""
    all_preds = load_predictions(name)
    preds = {i: p for i, p in all_preds.items() if not p.get("error") or is_model_failure(p)}
    missing = sum(1 for s in samples if s.id not in preds)
    if not preds:
        return None
    gold_s = [s for s in samples if s.id in preds]
    p_list = [preds[s.id] for s in gold_s]
    ok = [p for p in p_list if not p.get("error")]
    intents = intent_scores([s.intents for s in gold_s], [p["intents"] for p in p_list])
    ents = entity_scores([s.entities for s in gold_s], [p["entities"] for p in p_list])
    price = pricing["prices"].get(MODELS[name][2])
    in_tok = sum(p["input_tokens"] for p in ok)
    out_tok = sum(p["output_tokens"] for p in ok)
    cost = cost_usd(in_tok, out_tok, price)
    by_source = {}
    for src in sorted({s.source_model for s in gold_s}):
        idx = [i for i, s in enumerate(gold_s) if s.source_model == src]
        by_source[src] = intent_scores([gold_s[i].intents for i in idx],
                                       [p_list[i]["intents"] for i in idx])["micro_f1"]
    return {
        "model": name,
        "model_id": p_list[0].get("model_id", MODELS[name][1]),
        "n_scored": len(p_list),
        "n_errors": len(p_list) - len(ok),
        "n_missing": missing,
        **{k: intents[k] for k in ("macro_f1", "micro_f1", "exact_match")},
        **ents,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cost_usd": cost,
        "cost_per_1k": cost / len(ok) * 1000 if cost is not None and ok else None,
        "mean_latency_s": sum(p["latency_s"] for p in ok) / len(ok) if ok else None,
        "per_intent_f1": intents["per_intent_f1"],
        "micro_f1_by_source": by_source,
    }


def plot_scores(rows: list[dict], path: Path | None = None) -> None:
    """Grouped bars: intent macro F1 and entity F1 per model, best macro F1 first."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    surface, text, muted, grid = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
    series = [("macro_f1", "Intent Macro F1", "#2a78d6"), ("entity_f1", "Entity F1", "#008300")]
    path = path or SCORE_CHART
    rows = sorted(rows, key=lambda r: -r["macro_f1"])
    width = 0.38
    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=150)
    fig.patch.set_facecolor(surface)
    ax.set_facecolor(surface)
    for j, (key, label, color) in enumerate(series):
        xs = [i + (j - 0.5) * width for i in range(len(rows))]
        vals = [r[key] * 100 for r in rows]
        bars = ax.bar(xs, vals, width, label=label, color=color, edgecolor=surface, linewidth=2, zorder=2)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 1, f"{v:.1f}", ha="center", va="bottom",
                    fontsize=8, color=muted)
    ax.set_xticks(range(len(rows)))
    ax.set_xticklabels([r["model"] for r in rows], fontsize=10, color=text)
    ax.set_ylim(0, 105)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_yticklabels([f"{t}%" for t in (0, 25, 50, 75, 100)])
    ax.yaxis.grid(True, color=grid, linewidth=0.8, zorder=0)
    ax.tick_params(axis="both", length=0, labelsize=9, colors=muted)
    ax.tick_params(axis="x", labelcolor=text)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.set_title("Intent Macro F1 and Entity F1 by model", loc="left", fontsize=12, color=text, pad=14)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=2, frameon=False,
              fontsize=9, labelcolor=text)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=surface)
    plt.close(fig)


def fmt(x, pct=True):
    if x is None:
        return "—"
    return f"{x * 100:.1f}" if pct else f"${x:.2f}"


def write_summary(rows: list[dict], n_total: int, pricing: dict, not_run: list[str] = ()) -> None:
    lines = [
        f"# Myanglish-BizBench {VERSION} — model results", "",
        f"Test set: `data/{VERSION}/test.jsonl` ({n_total} samples). Generated "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by `python -m src.evaluator --version {VERSION}` (prompt version {VERSION}).", "",
        "| Model | Model ID | Macro F1 | Micro F1 | Exact match | Entity F1 | Cost/1K |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        label = r["model"] + (f" ⚠ {r['n_scored']}/{n_total}" if r["n_missing"] else "")
        lines.append(f"| {label} | `{r['model_id']}` | {fmt(r['macro_f1'])} | {fmt(r['micro_f1'])} | "
                     f"{fmt(r['exact_match'])} | {fmt(r['entity_f1'])} | {fmt(r['cost_per_1k'], pct=False)} |")
    for name in not_run:
        lines.append(f"| {name} ⚠ not run | `{MODELS[name][1]}` | — | — | — | — | — |")
    lines += [
        "",
        f"![Intent Macro F1 and Entity F1 by model]({SCORE_CHART.relative_to(RESULTS).as_posix()})", "",
        "F1 and exact match are percentages. **Cost/1K** is the US-dollar cost of annotating 1,000 "
        "messages, from measured token usage (including reasoning tokens) times list prices from the "
        f"OpenRouter catalog (fetched {pricing['fetched_at'][:10]}).", "",
        "⚠ marks an incomplete run: some samples have no prediction because the API request failed "
        "(not counted as wrong). Those scores are not comparable with complete runs until the missing "
        "samples are re-run (`python -m src.evaluator --models <name>`).", "",
        "## Run details", "",
        "| Model | Scored | Missing | Bad answers | Entity key F1 | Input tokens | Output tokens | Run cost | Mean latency (s) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lat = f"{r['mean_latency_s']:.1f}" if r["mean_latency_s"] is not None else "—"
        lines.append(f"| {r['model']} | {r['n_scored']} | {r['n_missing']} | {r['n_errors']} | {fmt(r['entity_key_f1'])} | "
                     f"{r['input_tokens']:,} | {r['output_tokens']:,} | {fmt(r['cost_usd'], pct=False)} | {lat} |")
    sources = sorted({s for r in rows for s in r["micro_f1_by_source"]})
    lines += ["", "## Intent micro F1 by the model that generated the sample", "",
              "The test messages were written by GPT, Claude, DeepSeek and Gemini. A model scoring "
              "higher on its own samples is a sign of self-preference bias.", "",
              "| Model | " + " | ".join(sources) + " |", "|---|" + "---|" * len(sources)]
    for r in rows:
        lines.append(f"| {r['model']} | " + " | ".join(fmt(r["micro_f1_by_source"].get(s)) for s in sources) + " |")
    lines += ["", "## Per-intent F1", "", "| Intent | " + " | ".join(r["model"] for r in rows) + " |",
              "|---|" + "---|" * len(rows)]
    for lab in INTENTS:
        lines.append(f"| {lab} | " + " | ".join(fmt(r["per_intent_f1"].get(lab)) for r in rows) + " |")
    lines += ["", "## Method", "",
              "- Zero-shot. Every model gets the same system prompt (`src/schemas.py`) listing the 12 "
              "intents and 15 entity keys, and must answer in a fixed JSON schema (provider structured-output "
              "mode where available).",
              "- Provider default settings: no temperature or reasoning-effort overrides.",
              "- **Macro F1**: mean of per-intent F1 (multi-label). **Micro F1**: F1 over all intent labels. "
              "**Exact match**: predicted intent set equals the gold set. **Entity F1**: micro F1 over "
              "(key, value) pairs after lenient normalisation (case, spacing, underscores; digits only for "
              "quantity, price and delivery fee).",
              "- Unparseable or empty answers count as empty predictions (no intents, no entities). "
              "Failed API requests are reported as missing instead.",
              ""]
    complete = [r for r in rows if not r["n_missing"]]
    if complete:
        plot_scores(complete)
    (RESULTS / "results.md").write_text("\n".join(lines), encoding="utf-8")
    (RESULTS / "results.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="+", default=list(MODELS), choices=list(MODELS))
    ap.add_argument("--limit", type=int, help="only the first N samples (smoke test)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--summary-only", action="store_true")
    ap.add_argument("--refresh-pricing", action="store_true")
    ap.add_argument("--version", default="v0.1", choices=list(PROMPTS))
    args = ap.parse_args()
    set_version(args.version)
    if not DATA.exists():
        sys.exit(f"{DATA} does not exist yet (freeze {args.version} first).")

    samples = load_samples()
    run_samples = samples[:args.limit] if args.limit else samples
    pricing = load_pricing(args.refresh_pricing)
    if not args.summary_only:
        for name in args.models:
            run_model(name, run_samples, args.workers)
    rows = [r for name in MODELS if (r := score_model(name, run_samples, pricing))]
    not_run = [name for name in MODELS if name not in {r["model"] for r in rows}]
    write_summary(rows, len(run_samples), pricing, not_run)
    print()
    for r in rows:
        print(f"{r['model']:<9} macroF1={fmt(r['macro_f1'])} microF1={fmt(r['micro_f1'])} "
              f"EM={fmt(r['exact_match'])} entF1={fmt(r['entity_f1'])} cost/1K={fmt(r['cost_per_1k'], False)} "
              f"bad={r['n_errors']} missing={r['n_missing']}")
    print(f"\nResults written to {RESULTS / 'results.md'}")


if __name__ == "__main__":
    main()
