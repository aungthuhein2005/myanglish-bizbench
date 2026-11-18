"""Exploratory analysis of the Myanglish-BizBench dataset.

Usage:
    python scripts/analyze_dataset.py [path/to/data/interim/merged.json]

Runs validation (validate_dataset.py) and writes reports/dataset_report.md.
"""
import re
import statistics
import sys
from collections import Counter
from datetime import date
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_dataset import DEFAULT_DATA, ROOT, format_summary, load, validate  # noqa: E402

REPORT = ROOT / "reports" / "dataset_report.md"
FIGURES = ROOT / "reports" / "figures"
INTENT_CHART = FIGURES / "intent_distribution.png"
MULTI_INTENT_CHART = FIGURES / "multi_intent_distribution.png"
LENGTH_CHART = FIGURES / "message_length_distribution.png"
ENTITY_CHART = FIGURES / "entity_type_distribution.png"
WORD_BUCKETS = [(1, 5), (6, 10), (11, 15), (16, 20), (21, 30), (31, None)]

# Chart colors (light surface).
SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
BAR = "#2a78d6"


def pretty_intent(name):
    if name == "refund_exchange":
        return "Refund / exchange"
    return name.replace("_", " ").capitalize()


def plot_bar_chart(items, title, xlabel, path):
    """Horizontal bar chart; `items` is a list of (label, value) drawn top to bottom."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    items = list(items)[::-1]  # barh draws bottom-up
    labels = [k for k, _ in items]
    values = [v for _, v in items]

    fig, ax = plt.subplots(figsize=(9, 0.42 * len(items) + 1.2), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    bars = ax.barh(labels, values, height=0.72, color=BAR, edgecolor=SURFACE, linewidth=2, zorder=2)
    for bar, v in zip(bars, values):
        ax.text(bar.get_width() + max(values) * 0.01, bar.get_y() + bar.get_height() / 2, str(v),
                va="center", ha="left", fontsize=9, color=TEXT_SECONDARY)

    ax.set_title(title, loc="left", fontsize=12, color=TEXT_PRIMARY, pad=12)
    ax.set_xlabel(xlabel, fontsize=9, color=TEXT_SECONDARY)
    ax.set_xlim(0, max(values) * 1.1)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8, zorder=0)
    ax.tick_params(axis="both", length=0, labelsize=9, colors=TEXT_SECONDARY)
    ax.tick_params(axis="y", labelcolor=TEXT_PRIMARY)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)

    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


# Standard entity schema (same keys as ENTITY_KEYS in validate_dataset.py), in report order.
STANDARD_ENTITY_KEYS = [
    "product", "brand", "quantity", "size", "color", "variant", "price", "currency",
    "location", "payment_method", "delivery_method", "delivery_fee", "order_id",
    "date_time", "issue",
]


def count_values(v):
    """Number of entity values: a list counts each element, a scalar counts once."""
    return len(v) if isinstance(v, list) else 1


EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


def pct(n, total):
    return f"{n / total * 100:.1f}%" if total else "0.0%"


def table(headers, rows):
    lines = ["| " + " | ".join(str(h) for h in headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def count_table(counter, total, label):
    rows = [(k, v, pct(v, total)) for k, v in counter.most_common()]
    return table([label, "Count", "Share"], rows)


def crosstab(records, row_key, col_key):
    rows_vals = sorted({r[row_key] for r in records})
    cols_vals = sorted({r[col_key] for r in records})
    c = Counter((r[row_key], r[col_key]) for r in records)
    rows = [[rv] + [c[(rv, cv)] for cv in cols_vals] + [sum(c[(rv, cv)] for cv in cols_vals)]
            for rv in rows_vals]
    return table([row_key] + cols_vals + ["total"], rows)


def length_stats(values):
    return (min(values), f"{statistics.mean(values):.1f}", statistics.median(values), max(values))


def img(path, alt):
    return f"![{alt}]({path.relative_to(REPORT.parent).as_posix()})"


def bucket_label(lo, hi):
    return f"{lo}+ words" if hi is None else f"{lo}–{hi} words"


def word_bucket(n_words):
    for lo, hi in WORD_BUCKETS:
        if n_words >= lo and (hi is None or n_words <= hi):
            return bucket_label(lo, hi)
    return "0 words"


def build_report(records, summary):
    n = len(records)
    models = sorted({r["source_model"] for r in records})
    out = [
        "# Myanglish-BizBench Dataset Report",
        "",
        f"Generated {date.today().isoformat()} from `merged.json` by `scripts/analyze_dataset.py`.",
        "",
        "## 1. Validation summary",
        "",
        "```",
        format_summary(summary),
        "```",
        "",
        "Definitions: a sample is **invalid** if it fails any check in `scripts/validate_dataset.py` "
        "(missing/extra fields, wrong types, values outside the allowed sets, non-canonical intent labels, "
        "duplicate id). Samples whose only intent is `unknown` (emoji-only or slang messages) may have an empty "
        "or non-Burmese `normalized_burmese`. **Duplicate messages** compares `text` after lower-casing and collapsing spaces. "
        "**Context-dependent** means `context` is not null.",
        "",
    ]

    if summary["errors"]:
        out += ["### Validation errors", ""]
        rows = [(rid, "; ".join(errs)) for rid, errs in summary["errors"].items()]
        out += [table(["id", "problem"], rows), ""]
    if summary["duplicate_texts"]:
        out += ["### Duplicate messages", ""]
        out += [f"- `{t}`" for t in summary["duplicate_texts"]] + [""]

    # 2. Composition
    out += ["## 2. Dataset composition", "", "### By source model", ""]
    out += [count_table(Counter(r["source_model"] for r in records), n, "source_model"), ""]
    out += ["### By writing style", ""]
    out += [count_table(Counter(r["writing_style"] for r in records), n, "writing_style"), ""]
    out += ["### By difficulty", ""]
    out += [count_table(Counter(r["difficulty"] for r in records), n, "difficulty"), ""]
    out += ["### Difficulty by source model", "", crosstab(records, "source_model", "difficulty"), ""]
    out += ["### Writing style by source model", "", crosstab(records, "source_model", "writing_style"), ""]

    # 3. Intents
    intent_counts = Counter(i for r in records for i in r["intents"])
    total_labels = sum(intent_counts.values())
    out += ["## 3. Intents", "",
            f"{total_labels} intent labels across {n} samples "
            f"({total_labels / n:.2f} per sample on average).", "",
            "### Intent frequency", "",
            img(INTENT_CHART, "Samples per intent"), "",
            table(["intent", "samples", "share of samples"],
                  [(k, v, pct(v, n)) for k, v in intent_counts.most_common()]), ""]
    plot_bar_chart([(pretty_intent(k), v) for k, v in intent_counts.most_common()],
                   "Samples per intent", "Samples", INTENT_CHART)

    # A. Multi-intent distribution
    def intent_bucket(r):
        k = len(r["intents"])
        return {1: "1 intent", 2: "2 intents"}.get(k, "3+ intents")

    bucket_names = ["1 intent", "2 intents", "3+ intents"]
    buckets = Counter(intent_bucket(r) for r in records)
    exact = Counter(len(r["intents"]) for r in records)
    multi = n - buckets["1 intent"]
    out += ["### A. Multi-intent distribution", "",
            f"{multi} of {n} messages ({pct(multi, n)}) carry more than one intent.", "",
            img(MULTI_INTENT_CHART, "Messages by number of intents"), "",
            table(["intents per message", "messages", "share"],
                  [(b, buckets[b], pct(buckets[b], n)) for b in bucket_names]), "",
            "Exact counts: " + ", ".join(f"{k} intent{'s' if k > 1 else ''} = {exact[k]}"
                                         for k in sorted(exact)) + ".", ""]
    by_model_bucket = Counter((r["source_model"], intent_bucket(r)) for r in records)
    out += ["#### By source model", "",
            table(["source_model"] + bucket_names + ["multi-intent share"],
                  [[m] + [by_model_bucket[(m, b)] for b in bucket_names]
                   + [pct(sum(by_model_bucket[(m, b)] for b in bucket_names[1:]),
                          sum(by_model_bucket[(m, b)] for b in bucket_names))]
                   for m in models]), ""]
    plot_bar_chart([(b, buckets[b]) for b in bucket_names],
                   "Messages by number of intents", "Messages", MULTI_INTENT_CHART)
    pairs = Counter(p for r in records for p in combinations(sorted(set(r["intents"])), 2))
    if pairs:
        out += ["#### Most common intent pairs", "",
                table(["intent A", "intent B", "count"],
                      [(a, b, c) for (a, b), c in pairs.most_common(10)]), ""]
    by_model = {m: Counter(i for r in records if r["source_model"] == m for i in r["intents"]) for m in models}
    out += ["### Intent coverage by source model", "",
            table(["intent"] + models,
                  [[i] + [by_model[m][i] for m in models] for i, _ in intent_counts.most_common()]), ""]

    # 4. Text
    words = [len(r["text"].split()) for r in records]
    chars = [len(r["text"]) for r in records]
    shortest = min(records, key=lambda r: len(r["text"]))
    longest = max(records, key=lambda r: len(r["text"]))
    out += ["## 4. Message text", "",
            "### B. Message length distribution", "",
            "Length is measured on `text` in words (space-separated tokens) and in characters "
            "(including spaces and emoji).", "",
            table(["unit", "min", "mean", "median", "max"],
                  [("words", *length_stats(words)), ("characters", *length_stats(chars))]), "",
            f"- Shortest: `{shortest['id']}` `{shortest['text']}` ({len(shortest['text'])} chars)",
            f"- Longest (by characters): `{longest['id']}` ({len(longest['text'].split())} words, "
            f"{len(longest['text'])} chars)", ""]
    length_buckets = Counter(word_bucket(w) for w in words)
    bucket_order = [bucket_label(lo, hi) for lo, hi in WORD_BUCKETS]
    out += [img(LENGTH_CHART, "Messages by length in words"), "",
            table(["length", "messages", "share"],
                  [(b, length_buckets[b], pct(length_buckets[b], n)) for b in bucket_order]), ""]
    plot_bar_chart([(b, length_buckets[b]) for b in bucket_order],
                   "Messages by length in words", "Messages", LENGTH_CHART)
    rows = []
    groups = [(m, lambda r, m=m: r["source_model"] == m) for m in models]
    groups += [(f"difficulty={d}", lambda r, d=d: r["difficulty"] == d) for d in ("easy", "medium", "hard")]
    groups += [(f"style={s}", lambda r, s=s: r["writing_style"] == s) for s in ("myanglish", "myanglish_english")]
    for name, pred in groups:
        sel = [r for r in records if pred(r)]
        if sel:
            w = [len(r["text"].split()) for r in sel]
            c = [len(r["text"]) for r in sel]
            rows.append((name, len(sel), *length_stats(w), f"{statistics.mean(c):.1f}",
                         statistics.median(c)))
    out += ["#### Length by group", "",
            table(["group", "n", "min words", "mean words", "median words", "max words",
                   "mean chars", "median chars"], rows), ""]
    with_digits = sum(1 for r in records if re.search(r"\d", r["text"]))
    with_emoji = sum(1 for r in records if EMOJI.search(r["text"]))
    vocab = Counter(w for r in records for w in r["text"].lower().split())
    out += [f"- Messages containing digits: {with_digits} ({pct(with_digits, n)})",
            f"- Messages containing emoji: {with_emoji} ({pct(with_emoji, n)})",
            f"- Distinct tokens (lower-cased, space-split): {len(vocab)}",
            "",
            "### Top 20 tokens", "",
            table(["token", "count"], vocab.most_common(20)), ""]

    # 5. Entities
    with_ent = [r for r in records if r["entities"]]
    keys = Counter(k for r in records for k in r["entities"])
    nonstandard = sorted(k for k in keys if k not in STANDARD_ENTITY_KEYS)
    all_keys = STANDARD_ENTITY_KEYS + nonstandard
    key_values = Counter()
    examples = {}
    for r in records:
        for k, v in r["entities"].items():
            key_values[k] += count_values(v)
            for x in (v if isinstance(v, list) else [v]):
                ex = examples.setdefault(k, [])
                if str(x) not in ex:
                    ex.append(str(x))
    ordered = sorted(all_keys, key=lambda k: (-keys[k], all_keys.index(k)))
    unused = [k for k in STANDARD_ENTITY_KEYS if not keys[k]]
    out += ["## 5. Entities", "",
            f"- Samples with at least one entity: {len(with_ent)} ({pct(len(with_ent), n)})",
            f"- Samples with no entities: {n - len(with_ent)} ({pct(n - len(with_ent), n)})",
            f"- Entity keys in use: {len(keys)} of the {len(STANDARD_ENTITY_KEYS)} standard keys"
            + (f"; non-standard keys: {', '.join(f'`{k}`' for k in nonstandard)}" if nonstandard else ""),
            f"- Standard keys with no annotations: {', '.join(f'`{k}`' for k in unused) or 'none'}",
            "",
            "### C. Entity distribution", "",
            "Entities follow the standard schema (15 keys, enforced by `scripts/validate_dataset.py`; "
            "the mapping from the original keys is in `scripts/standardize_entities.py`). "
            "**Samples** counts messages with that key; **values** counts every annotated value "
            "(a list of two colours counts as 2).", "",
            img(ENTITY_CHART, "Messages per entity type"), "",
            table(["entity key", "samples", "share of samples", "values", "example values"],
                  [(f"`{k}`", keys[k], pct(keys[k], n), key_values[k],
                    "; ".join(examples.get(k, [])[:4]) or "—")
                   for k in ordered]), ""]
    plot_bar_chart([(k, keys[k]) for k in ordered],
                   "Messages per entity type", "Messages", ENTITY_CHART)
    by_model_key = Counter((r["source_model"], k) for r in records for k in r["entities"])
    used = [k for k in ordered if keys[k]]
    out += ["#### Entity keys by source model", "",
            table(["entity key"] + models,
                  [[f"`{k}`"] + [by_model_key[(m, k)] for m in models] for k in used]
                  + [["no entities"] + [sum(1 for r in records if r["source_model"] == m and not r["entities"])
                                        for m in models]]), ""]

    # 6. Clarification and context
    clar = [r for r in records if r["requires_clarification"]]
    out += ["## 6. Clarification and context", "",
            f"- Samples requiring clarification: {len(clar)} ({pct(len(clar), n)})",
            f"- Context-dependent samples: {summary['context_dependent']} "
            f"({pct(summary['context_dependent'], n)})", "",
            "### Requires clarification by difficulty", "",
            crosstab(records, "difficulty", "requires_clarification"), ""]
    ctx = [r for r in records if r["context"] is not None]
    if ctx:
        out += ["### Context-dependent samples", "",
                table(["id", "text", "context"], [(r["id"], r["text"], r["context"]) for r in ctx]), ""]

    # 7. Observations
    obs = []
    aliases = [e for errs in summary["errors"].values() for e in errs if "non-canonical intent" in e]
    if aliases:
        obs.append(f"{len(aliases)} intent labels use non-canonical spellings "
                   "(`refund_and_exchange`, `unknown_intent`); these should be merged into the canonical labels.")
    top_style, top_style_n = Counter(r["writing_style"] for r in records).most_common(1)[0]
    obs.append(f"`{top_style}` is the dominant writing style ({pct(top_style_n, n)}).")
    least_intent, least_n = intent_counts.most_common()[-1]
    obs.append(f"Intent balance is uneven: `{intent_counts.most_common(1)[0][0]}` appears in "
               f"{intent_counts.most_common(1)[0][1]} samples, `{least_intent}` in {least_n}.")
    if unused:
        obs.append(f"Standard entity keys never annotated: {', '.join(f'`{k}`' for k in unused)}.")
    obs.append(f"{n - len(with_ent)} of {n} samples have no entities, so entity coverage is sparse.")
    if summary["context_dependent"] < 10:
        obs.append(f"Only {summary['context_dependent']} samples carry context, so multi-turn behaviour is barely covered.")
    out += ["## 7. Observations", ""] + [f"- {o}" for o in obs] + [""]
    return "\n".join(out)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DATA
    records = load(path)
    summary = validate(records)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(build_report(records, summary), encoding="utf-8")
    print(format_summary(summary))
    print(f"\nReport written to {REPORT}")


if __name__ == "__main__":
    main()
