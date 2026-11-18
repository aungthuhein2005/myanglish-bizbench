# Myanglish-BizBench annotation guidelines — v0.2

These rules define the gold labels for v0.2. They apply to **every** sample, and the review is
done **without looking at model predictions** (the review sheet does not contain them).

> **Why v0.2 exists.** The v0.1 failure analysis found that most errors were caused by unclear or
> inconsistent gold labels, not by the models. v0.2 writes the labelling rules down and re-reviews
> all 100 samples against them. v0.1 stays frozen and both versions are reported, so readers can
> see the effect of the relabelling. The rules were written after seeing v0.1 results; this is
> disclosed in the report.

Every message is read as a **customer writing to an online shop**.

## Intents

1. **Label every intent that the message itself expresses** — a question, request or statement
   in the text. Do not add intents that are only implied or likely to follow.
2. **A secondary intent needs its own words.** Add `price_inquiry` only when the customer asks for
   a price or total (e.g. *bl lout lal*, *zay bal lout*). Asking for a lower price
   (*shrot pay lar*, *discount shi lar*) is `discount_inquiry` only.
3. **`greeting` combines with other intents.** "hi sis, how much is this?" = `greeting` +
   `price_inquiry`. Honorifics alone (*sis*, *bro*, *admin*) are not a greeting.
4. **Availability vs product questions.**
   - "Do you have size M / colour red / is it in stock?" = `stock_availability` only.
   - Questions about what the product is like (material, quality, fit, which colours or sizes it
     comes in, suitability) = `product_inquiry`.
5. **Complaints.** A complaint about a delay, the item or the service = `customer_complaint`.
   Add `delivery_inquiry` only if the customer also asks about delivery (when / where / status).
   Add `refund_exchange` only if they ask for a refund, return or exchange.
6. **Order changes.** Cancelling all or part of an order = `order_cancellation`. Add `place_order`
   only if the customer orders something new or extra (keeping part of an existing order is not a
   new order).
7. **`unknown`** is only for messages with no determinable business intent (emoji, insults, a
   reference to something earlier that cannot be resolved). A short but clear question such as
   *yout pyi lar* ("has it arrived?") is `delivery_inquiry`.

## Entities

Extract **every business entity explicitly mentioned** in the message, one key/value pair per
value. Do not extract anything that is not written in the message.

| Key | Rule | Examples |
|---|---|---|
| `product` | Product type, English, singular, lowercase | `sneaker`, `phone case`, `serum` |
| `brand` | Brand name as written | `Samsung` |
| `quantity` | Integer | `2` |
| `size` | As written, uppercase letters | `M`, `XL`, `38` |
| `color` | English, lowercase | `black` |
| `variant` | Material, feature or model of the product | `genuine leather`, `waterproof`, `iPhone 13` |
| `price` | Integer kyat; *thaung* = 10,000, *thein* = 100,000 | `100000` |
| `currency` | **Only if written** (MMK, kyat, ks, $) | `MMK` |
| `location` | **One value per place name**; township and city are separate values | `Yankin`, `Yangon` |
| `payment_method` | Canonical names | `KBZPay`, `CB Pay`, `WavePay`, `AYA Pay`, `COD`, `bank transfer` |
| `delivery_method` | How the item is delivered | `highway bus gate`, `express` |
| `delivery_fee` | Integer kyat, only an amount | `3000` |
| `order_id` | As written | `ORD-123` |
| `date_time` | Dates, days, durations and events; **not** "now" | `today`, `yesterday`, `3 days`, `11.11` |
| `issue` | **One value from the issue list below** | `damaged_item` |

### Issue types

| Value | Use for |
|---|---|
| `wrong_size` | Size too small / too big / does not fit |
| `damaged_item` | Broken, cracked, torn, defective on arrival |
| `wrong_item` | Received a different item, size or colour than ordered |
| `color_mismatch` | Colour differs from the photo |
| `not_as_described` | Item differs from the photo or description (other than colour) |
| `poor_quality` | Low quality, thin, cheap material |
| `late_delivery` | Delivery slower than promised |
| `not_received` | Order or refund not received |
| `missing_tracking` | No tracking number / status update |
| `slow_response` | Shop does not reply |
| `out_of_stock` | Item no longer available |
| `payment_issue` | Payment problem (failed, charged twice, refund of payment) |
| `other` | Any other problem |

## Review workflow

1. Open `data/v0.2/review_sheet.csv` in Excel (or any spreadsheet). It has all 100 samples and no
   model predictions. Issue values and multi-place locations are already converted to the v0.2
   format (column `auto_changes` says what changed).
2. For each row, check `intents` (space-separated) and `entities` (JSON object, e.g.
   `{"payment_method": ["KBZPay", "CB Pay"]}`) against these guidelines and edit them if needed.
   Do not edit `id` or `text`.
3. Set `review_status` to `ok` (no change) or `changed`, and write the reason for any change in
   `reviewer_notes`. Save as CSV (UTF-8).
4. Run `python scripts/apply_review.py`: it checks every row, validates the labels and writes
   `data/v0.2/reviewed.json` plus `reports/v0.2_changelog.md` (every change, with your notes).
5. Freeze: `python scripts/freeze_dataset.py --version v0.2`.
6. Evaluate: `python -m src.evaluator --version v0.2` (uses the v0.2 prompt; results go to
   `results/v0.2/`). v0.1 results in `results/` are not touched.

## Other fields

- `requires_clarification`: true when a shop assistant could not act without asking a question back.
- `context`: only when the message refers to earlier conversation that is needed to understand it.
- `difficulty`, `writing_style`, `normalized_burmese`, `english_meaning`: review for correctness
  but keep the v0.1 definitions.
