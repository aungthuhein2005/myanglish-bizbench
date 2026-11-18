---
license: cc-by-4.0
language:
  - my
  - en
pretty_name: Myanglish-BizBench
size_categories:
  - n<1K
task_categories:
  - text-classification
  - token-classification
task_ids:
  - multi-label-classification
  - intent-classification
tags:
  - myanglish
  - burmese
  - romanized
  - code-mixing
  - e-commerce
  - customer-service
  - llm-evaluation
  - benchmark
configs:
  - config_name: v0.2
    default: true
    data_files:
      - split: test
        path: v0.2/test.jsonl
  - config_name: v0.1
    data_files:
      - split: test
        path: v0.1/test.jsonl
---

# Myanglish-BizBench

A test set of 100 **Myanglish** e-commerce customer messages for evaluating how well LLMs
understand them. Myanglish is Burmese written in Latin letters, often mixed with English. Each
message is labelled with **business intents** (12, multi-label) and **entities** (15 types).

```python
from datasets import load_dataset
ds = load_dataset("aungthuhein-dev/myanglish-bizbench", "v0.2", split="test")
```

> `sis black L size 1 khu yuu mal, yankin ko deli kha bl lout lal`
> → `place_order`, `delivery_inquiry` · color `black`, size `L`, quantity `1`, location `Yankin`

## Leaderboard (v0.2, zero-shot)

| Model | Intent Macro F1 | Exact match | Entity F1 | Cost / 1K msgs |
|---|---|---|---|---|
| Claude (`claude-opus-5-5`) | 93.2 | 84.0 | 81.4 | $10.82 |
| GPT (`gpt-6.2-sol`) | 91.7 | 81.0 | 82.7 | $2.88 |
| Gemini (`gemini-4-carbon`) | 90.6 | 79.0 | 86.5 | $5.48 |
| Qwen (`qwen4-max`) | 88.0 | 75.0 | 82.3 | $3.35 |
| Gemma (`gemma-4-31b-it`) | 78.1 | 62.0 | 72.4 | $0.22 |
| DeepSeek (`deepseek-v4-pro`) | 73.5 | 53.0 | 63.6 | $2.37 |

95% bootstrap CIs are ±4–8 points. Code, every prediction, and the full report:
**https://github.com/aungthuhein2005/myanglish-bizbench**.

## Fields

| Field | Type | Description |
|---|---|---|
| `id` | str | `mbb_0001` … `mbb_0100` |
| `source_model` | str | LLM that drafted the message (`chatgpt`, `claude`, `deepseek`, `gemini`; 25 each) |
| `text` | str | The Myanglish message (model input) |
| `normalized_burmese` | str | The message in Myanmar script |
| `english_meaning` | str | English translation |
| `intents` | list[str] | Gold intents (see below) |
| `entities` | dict | Gold entities: `{type: value or [values]}`; `quantity`, `price`, `delivery_fee` are integers |
| `writing_style` | str | `myanglish` (36) or `myanglish_english` (64) |
| `difficulty` | str | Annotator's estimate: `easy` / `medium` / `hard` |
| `context` | str or null | Earlier conversation needed to understand the message (4 messages) |
| `requires_clarification` | bool | A shop assistant would need to ask a question back |

**Intents:** `greeting`, `price_inquiry`, `product_inquiry`, `stock_availability`,
`place_order`, `payment_inquiry`, `delivery_inquiry`, `discount_inquiry`,
`order_cancellation`, `refund_exchange`, `customer_complaint`, `unknown`.
39 messages have more than one intent.

**Entities:** `product`, `brand`, `quantity`, `size`, `color`, `variant`, `price`, `currency`,
`location`, `payment_method`, `delivery_method`, `delivery_fee`, `order_id`, `date_time`,
`issue` (13 fixed values in v0.2).

## Versions

- **v0.2 (default).** Same messages and intent labels as v0.1, with entities relabelled under
  written guidelines (`annotation_guidelines_v0.2.md`): a fixed issue list, one value per place,
  and 7 entities added in a blind human review.
- **v0.1.** The first freeze.

Both versions are frozen and never edited. The v0.2 rules were written after seeing v0.1
results; both versions are published so the effect is visible.

## How it was made

Four LLMs each drafted 25 shop messages with labels from a common brief. A native Burmese
speaker rewrote unnatural messages and corrected labels. The entity schema was then
standardised, and the data validated and frozen. v0.2 was reviewed without showing model
predictions to the reviewer.

## Intended use and limitations

- **For evaluation only.** Please don't train or fine-tune on it, so the scores stay meaningful.
- **Not real customer messages.** The messages are synthetic and human-corrected, contain no
  personal data, and are probably cleaner than real chats. Scores are likely an upper bound.
- **Small.** 7–21 samples per intent. `brand`, `delivery_fee` and `order_id` never appear in the
  gold labels.
- **One annotator.** About 9 v0.2 intent labels conflict with the written guidelines. They are
  listed in the report as v0.3 work.

## License

CC BY 4.0. Evaluation code: MIT.
