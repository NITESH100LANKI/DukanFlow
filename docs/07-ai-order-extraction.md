# 07 — AI Order Extraction and SKU Matching Workflow

## 1. Objectives

- Accept a free-text message in Hindi, Hinglish, or English.
- Identify each product intent and quantity in the message.
- Map each intent to a SKU in the product catalogue.
- Flag ambiguities, unmatched items, and unit uncertainties explicitly.
- Never place an order automatically; always produce a draft for human review.

---

## 2. High-Level Flow

```
                    Retailer submits raw_text
                             │
                             ▼
              ┌──────────────────────────────┐
              │  1. Pre-processing           │
              │     • Lowercase + strip      │
              │     • Language detection     │
              │       (Devanagari / Roman)   │
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │  2. Context Assembly         │
              │     • Load retailer aliases  │
              │     • Load purchase history  │
              │       (last 90 days SKUs)    │
              │     • Load active catalogue  │
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │  3. Gemini API Call          │
              │     (structured prompt)      │
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │  4. Response Parsing         │
              │     • Pydantic validation    │
              │     • Fallback on failure    │
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │  5. SKU Resolution +         │
              │     Confidence Assignment    │
              │     • Alias match → confirmed│
              │       confidence_level: high │
              │     • Exact name → confirmed │
              │       confidence_level: high │
              │     • Single ilike match →   │
              │       confidence_level: medium│
              │     • Weak/broad fuzzy →     │
              │       confidence_level: low  │
              │       (requires confirmation)│
              │     • 2+ candidates →        │
              │         ambiguous (≤2 shown) │
              │     • 0 candidates →         │
              │         unmatched            │
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │  6. Quantity + Unit Check    │
              │     • If unit is peti/case   │
              │       → qty_cases confirmed  │
              │     • If unit is piece/pcs   │
              │       → flag unit_unclear    │
              │       (piece-level not MVP)  │
              │     • If no unit → flag      │
              │       unit_unclear           │
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │  7. Stock Check              │
              │     • stock_cases == 0 →     │
              │       warning OUT_OF_STOCK   │
              │     • stock_cases < fulfilmnt│
              │       → warning LOW_STOCK    │
              └──────────────┬───────────────┘
                             │
                             ▼
                   Return AIDraft to Frontend
```

---

## 3. Gemini Prompt Structure

The prompt is a **structured system + user message pair** sent to the Gemini API.

### 3.1 System Instruction (sent once per session / baked into service)

```
You are a product ordering assistant for an FMCG distributor in India.
Your only job is to extract product names and quantities from an order message.

Rules:
1. Return ONLY valid JSON. No explanations, no markdown.
2. For each product mentioned, return: raw_fragment, product_hint, qty_value, qty_unit.
3. qty_unit must be one of: "case", "piece", "unknown".
4. If you cannot determine a quantity, set qty_value to null.
5. If you cannot identify a product at all, set product_hint to null.
6. Do not guess prices or SKUs — only extract names and quantities.
7. Translate Hindi/Hinglish product terms to their most likely English equivalent in product_hint.
```

### 3.2 User Message Template

```
Product catalogue (name | sku | pack_size | case_qty | availability):
{catalogue_lines}

Retailer aliases (raw_term → sku):
{alias_lines}

Retailer recently purchased (last 90 days):
{purchase_history_lines}

Order message:
"{raw_text}"

Extract all product intents as JSON array:
[
  {
    "raw_fragment": "<exact substring from message>",
    "product_hint": "<best-guess English product name or null>",
    "qty_value": <integer or null>,
    "qty_unit": "case|piece|unknown"
  }
]
```

**Purchase history format** (SKU + name only; no quantities or prices sent to AI):
```
Retailer recently purchased: Glucose Biscuit 75g (SKU-BS-075), Detergent Powder 1kg (SKU-DT-1KG)
```

### 3.3 Catalogue Context Format

Only active, in-stock and near-out-of-stock products are included to keep the prompt token count manageable. Out-of-stock products are included with a flag so the AI can still recognise them.

```
Glucose Biscuit 75g | SKU-BS-075 | 75g | 96 pcs/case | AVAILABLE
Detergent Powder 1kg | SKU-DT-1KG | 1kg | 20 pcs/case | AVAILABLE
Tea Leaf 250g | SKU-TE-250 | 250g | 40 pcs/case | OUT_OF_STOCK
```

**Token budget:** Keep the catalogue block under 2,000 tokens (~1,500 characters). For large catalogues (>500 SKUs), pre-filter by category or top-selling products.

---

## 4. Gemini Response Parsing

### 4.1 Expected Raw Response

```json
[
  {
    "raw_fragment": "5 peti biscuit chhota",
    "product_hint": "glucose biscuit small",
    "qty_value": 5,
    "qty_unit": "case"
  },
  {
    "raw_fragment": "2 peti washing powder 1 kilo",
    "product_hint": "detergent powder 1kg",
    "qty_value": 2,
    "qty_unit": "case"
  },
  {
    "raw_fragment": "chai patti 250 wala 1 peti",
    "product_hint": "tea leaf 250g",
    "qty_value": 1,
    "qty_unit": "case"
  }
]
```

### 4.2 Pydantic Validation Schema

```python
class GeminiLineItem(BaseModel):
    raw_fragment: str
    product_hint: Optional[str] = None
    qty_value: Optional[int] = None
    qty_unit: Literal["case", "piece", "unknown"]

class GeminiResponse(BaseModel):
    items: List[GeminiLineItem]
```

### 4.3 Backend AIDraft Line Schema (after resolution)

```python
class AIDraftLine(BaseModel):
    raw_fragment: str                    # preserved from Gemini output
    match_status: Literal["confirmed", "ambiguous", "unmatched"]
    confidence_level: Optional[Literal["high", "medium", "low"]] = None
    # confidence_level is only set when match_status == "confirmed"
    # high  = alias or exact name/SKU match
    # medium = single unambiguous ilike match
    # low   = weak/broad fuzzy match (treated like "ambiguous" — requires confirmation)
    product: Optional[ProductSummary] = None
    alternatives: List[ProductSummary] = []   # max 2 items
    qty_cases: Optional[int] = None
    unit_unclear: bool = False
    warning: Optional[Literal["OUT_OF_STOCK", "INSUFFICIENT_STOCK"]] = None
```

### 4.4 Failure Handling

| Failure Mode | Action |
|-------------|--------|
| Gemini returns non-JSON | Retry once; if still fails, return `503` to frontend |
| Pydantic validation error | Log the raw response; return `503` with a descriptive error |
| Gemini API timeout (> 10 s) | Return `503` |
| Gemini API quota exceeded | Return `503` with code `AI_QUOTA_EXCEEDED` |
| `product_hint` is null | Mark line as `unmatched` without further lookup |
| `qty_value` is null | Mark line `unit_unclear`; still attempt SKU resolution |

---

## 5. SKU Resolution Algorithm

After receiving validated Gemini output, each line is resolved by `AIOrderService`:

```python
def resolve_sku(product_hint: str, retailer_id: UUID, db: Session) -> Resolution:

    # Step 1 — Alias table lookup (highest priority → confidence: high)
    normalised = normalise(product_hint)  # lowercase, strip punctuation
    alias = db.query(RetailerAlias).filter_by(
        retailer_id=retailer_id, raw_term=normalised
    ).first()
    if alias:
        return Resolution(status="confirmed", confidence_level="high", product=alias.product)

    # Step 2 — Exact SKU match (confidence: high)
    product = db.query(Product).filter_by(sku=product_hint.upper()).first()
    if product:
        return Resolution(status="confirmed", confidence_level="high", product=product)

    # Step 3 — Exact name match, case-insensitive (confidence: high)
    products = db.query(Product).filter(
        func.lower(Product.name) == normalised
    ).all()
    if len(products) == 1:
        return Resolution(status="confirmed", confidence_level="high", product=products[0])

    # Step 4 — Substring ilike search (single result → confidence: medium)
    products = db.query(Product).filter(
        Product.name.ilike(f"%{normalised}%")
    ).limit(5).all()

    if len(products) == 1:
        return Resolution(status="confirmed", confidence_level="medium", product=products[0])
    elif 2 <= len(products):
        # Return at most 2 alternatives (not 3)
        return Resolution(status="ambiguous", confidence_level=None, alternatives=products[:2])
    else:
        # Step 5 — Weak fuzzy (pg_trgm similarity, threshold 0.3)
        # A single weak match gets confidence "low" and is treated like ambiguous at UI level
        fuzzy = fuzzy_search(normalised, db, limit=2)
        if len(fuzzy) == 1:
            return Resolution(status="confirmed", confidence_level="low", product=fuzzy[0])
        elif len(fuzzy) >= 2:
            return Resolution(status="ambiguous", confidence_level=None, alternatives=fuzzy[:2])
        return Resolution(status="unmatched")
```

**Confidence summary table:**

| Resolution Path | `match_status` | `confidence_level` | UI behaviour |
|-----------------|----------------|-------------------|--------------|
| Alias match | `confirmed` | `high` | Auto-added; no confirmation needed |
| Exact SKU or name | `confirmed` | `high` | Auto-added |
| Single ilike substring | `confirmed` | `medium` | Auto-added with info badge |
| Single weak fuzzy | `confirmed` | `low` | Shown like `ambiguous`; retailer must confirm |
| 2 candidates (any path) | `ambiguous` | `null` | Retailer picks from ≤2 options |
| No match | `unmatched` | `null` | Retailer searches catalogue manually |

---

## 6. Unit Resolution Rules

| Extracted `qty_unit` | MVP Decision |
|----------------------|-------------|
| `"case"` | Accept as `qty_cases = qty_value` |
| `"piece"` | Flag `unit_unclear = True`. Display: "Is this N pieces or N cases?" |
| `"unknown"` | Flag `unit_unclear = True`. Display: "What unit did you mean?" |

Retailers must resolve all `unit_unclear` flags before sending the draft to cart.

---

## 7. Alias Storage

### 7.1 Retailer-Triggered (AI Draft Review Screen)

When a retailer manually selects the correct product for an `ambiguous`, `unmatched`, or `low`-confidence line:

```python
def save_alias(retailer_id: UUID, raw_term: str, product_id: UUID,
               source: str = "retailer", db: Session):
    normalised = normalise(raw_term)
    existing = db.query(RetailerAlias).filter_by(
        retailer_id=retailer_id, raw_term=normalised
    ).first()
    if existing:
        existing.product_id = product_id
        existing.source = source
        existing.updated_at = datetime.utcnow()
    else:
        db.add(RetailerAlias(
            retailer_id=retailer_id,
            raw_term=normalised,
            product_id=product_id,
            source=source,
        ))
    db.commit()
```

### 7.2 Order Desk-Triggered (Product Correction on Submitted Order)

When Order Desk corrects a product match on a `pending_review` order, the system must:
1. Update the `order_line.product_id` and re-snapshot the new product's details.
2. Recalculate totals for the affected line and the order.
3. **Save the alias** using the `order_line.raw_fragment` as the `raw_term`, the corrected SKU as `product_id`, and `source = "desk"`.

**API endpoint:**
```
POST /api/v1/orders/{order_id}/lines/{line_id}/correct-product
Body: { "product_id": "uuid-of-correct-product" }
Auth: Order Desk only
```

This endpoint triggers `save_alias(retailer_id, raw_fragment, new_product_id, source="desk")` automatically.

---

## 8. Sample Extraction Walkthrough

**Input:** `"bhaiya 5 peti biscuit chhota, 2 peti washing powder 1 kilo, chai patti 250 wala 1 peti"`

| Fragment | Gemini `product_hint` | Gemini `qty_unit` | SKU Resolution | `match_status` | Stock Check |
|----------|-----------------------|-------------------|----------------|----------------|-------------|
| `5 peti biscuit chhota` | `glucose biscuit small` | `case` | ilike `biscuit` → 1 match: SKU-BS-075 | `confirmed` | ✅ 340 cases |
| `2 peti washing powder 1 kilo` | `detergent powder 1kg` | `case` | ilike `detergent` → 1 match: SKU-DT-1KG | `confirmed` | ✅ 85 cases |
| `chai patti 250 wala 1 peti` | `tea leaf 250g` | `case` | ilike `tea` → 1 match: SKU-TE-250 | `confirmed` | ❌ 0 cases → `warning: OUT_OF_STOCK` |

**Result:** 2 items can go to cart; 1 item (tea) is blocked due to zero stock.

---

## 9. Prompt Engineering Principles

1. **No hallucination of SKUs or prices** — The AI is explicitly told not to guess SKUs or prices.
2. **Structured output only** — JSON output enforced by system instruction; no free-text responses.
3. **Catalogue in context** — Including the catalogue in the prompt is safer than relying on training data for product names.
4. **Alias priority** — Retailer-specific aliases are injected into the prompt context so the AI can use them as hints, but the backend also runs its own alias lookup independently (defence in depth).
5. **Retry on malformed JSON** — One automatic retry before returning an error prevents transient failures.

