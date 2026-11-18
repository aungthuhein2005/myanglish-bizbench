# Myanglish Message Analyzer

A small, production-shaped service that applies the Myanglish-BizBench findings: an existing LLM
reads a Myanglish customer message and returns what the customer wants, the order details, what
is still missing, and whether a person should handle it.

```
"sis black L size 1 khu yuu mal, yankin ko deli kha bl lout lal"
        │
        ▼  LLM (default GPT), benchmark v0.2 prompt + JSON schema
intents   place_order, delivery_inquiry
entities  color: black · size: L · quantity: 1 · location: Yankin
        │
        ▼  plain Python rules (testable, no API)
missing   nothing
route     auto
```

## Why it is built this way

| Benchmark finding (`reports/final_report.md`) | Design choice |
|---|---|
| Frontier models reach 91–93% intent Macro F1 zero-shot; no fine-tuning needed | Use an existing API model with the benchmark prompt, unchanged |
| GPT is in the top tier at the lowest frontier cost ($2.88 / 1K messages) and 3.4 s p90 | `GPT` is the default; `--model Claude` (highest accuracy) or `--model Gemma` ($0.22 / 1K, 1.8 s) are one flag away |
| Writing the labelling rules into the prompt raised entity F1 ~10 points | The v0.2 prompt (with the written rules) is the one used |
| `unknown`, complaints and refunds are where mistakes are costly | These always route to a person |
| Models drop secondary intents in multi-intent messages | 3+ requests in one message route to a person |
| Short messages need earlier chat (`yout pyi lar` = "has *it* arrived?") | Optional `context` is passed to the model |

## Run

Needs the API key for the chosen model in `.env` at the project root (`OPENAI_API_KEY` for GPT;
see the main README).

Command line:

```powershell
python -m app "kbz pay lo pay loh ya ma lr"
```

```powershell
python -m app --model Claude "yout pyi lar" --context "Customer ordered a handbag on Monday"
```

Web demo and JSON API on http://127.0.0.1:8000:

```powershell
python -m app.server
```

```powershell
curl -X POST http://127.0.0.1:8000/api/analyze -H "Content-Type: application/json" -d '{\"message\": \"yout pyi lar\"}'
```

From Python:

```python
from app.analyzer import Analyzer
result = Analyzer("GPT").analyze("size M shi lar sis, bl lout lal")
result.intents, result.entities, result.missing_info, result.route
```

## Output

| Field | Meaning |
|---|---|
| `intents` | 1+ of the 12 benchmark intents |
| `entities` | `{type: [values]}` over the 15 benchmark entity types |
| `missing_info` | What to ask the customer before acting (e.g. delivery address for an order) |
| `route` | `auto` = safe to draft an automatic reply; `human` = hand to a person |
| `reasons` | Why it was routed to a person |
| `latency_s`, `input_tokens`, `output_tokens` | For cost and speed monitoring |
| `error` | Set when the model call failed; the message is then routed to a person |

## Tests

Offline (a fake model; no API calls or cost):

```powershell
python -m unittest discover tests
```

## Limits

- Expected accuracy is the benchmark's: about 92% intent Macro F1 and 83% entity F1 for GPT on
  synthetic, human-corrected messages. Real customer messages are likely harder, especially pure
  Myanglish without English words (7–29 points lower in the benchmark). Measure on your own
  messages before automating replies.
- It understands messages; it does not write replies or look up stock, prices or orders.
- The server binds to localhost and has no authentication. Each request spends API credit.
- Messages are sent to the model provider; tell customers and follow the provider's data terms.
