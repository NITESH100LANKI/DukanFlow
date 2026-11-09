# 08 — Scheme Engine Calculation Rules

## 1. Design Principles

- The scheme engine is a **pure Python module** with no database or API calls.
- It is called by `CartService` and `OrderService` with product + quantity as input.
- It returns a `SchemeResult` object; it never mutates state.
- It is fully unit-testable in isolation.
- All monetary arithmetic uses Python's `Decimal` type (not `float`) to prevent rounding errors.
- Rounding rule throughout: **`ROUND_HALF_UP`** applied at two decimal places.

---

## 2. Supported Scheme Types (MVP)

| Type Enum | Name | Description |
|-----------|------|-------------|
| `BUY_N_GET_M_FREE` | Buy N Get M Free | Retailer pays for N cases; distributor physically ships N + M cases. No monetary deduction from payable. |
| `DISCOUNT_ON_MIN_QTY` | Percentage Discount on Minimum Quantity | A flat % discount on the entire paid line when quantity ≥ minimum. |

---

## 3. Data Contract

### Input to Scheme Engine

```python
@dataclass
class SchemeInput:
    scheme_type: str              # "BUY_N_GET_M_FREE" or "DISCOUNT_ON_MIN_QTY"
    min_qty: int                  # Minimum PAID cases to trigger scheme
    free_qty: Optional[int]       # Only for BUY_N_GET_M_FREE
    discount_pct: Optional[Decimal]  # Only for DISCOUNT_ON_MIN_QTY (e.g., Decimal("3.00"))
    valid_from: date
    valid_to: date
    is_active: bool

@dataclass
class LineInput:
    unit_price_per_case: Decimal  # dealer_price_per_pack × case_qty — computed before call
    qty_cases: int                # Paid cases only (retailer-entered quantity)
    scheme: Optional[SchemeInput]
    order_date: date              # To check scheme validity
```

### Output from Scheme Engine

```python
@dataclass
class SchemeResult:
    scheme_applied: bool
    scheme_type: Optional[str]
    qty_paid: int                 # Cases the retailer pays for (= input qty_cases)
    qty_free: int                 # Additional physical cases earned (0 if no free-goods scheme)
    qty_fulfilment: int           # qty_paid + qty_free — total cases to ship
    gross_line_total: Decimal     # unit_price_per_case × qty_paid
    benefit_value: Decimal        # Monetary value of free goods (informational; not deducted for BUY_N_GET_M_FREE)
    discount_amount: Decimal      # Monetary discount deducted (0 for BUY_N_GET_M_FREE)
    net_line_total: Decimal       # Amount retailer actually pays
    scheme_description: str       # Human-readable, e.g., "1 free case on 10 paid"
```

---

## 4. Calculation Rules

### 4.1 No Scheme (or Scheme Not Applicable)

Conditions: `scheme is None`, `is_active = False`, `order_date < valid_from`, `order_date > valid_to`, or `qty_cases < min_qty`.

```
qty_paid         = qty_cases
qty_free         = 0
qty_fulfilment   = qty_cases
gross_line_total = unit_price_per_case × qty_cases
benefit_value    = 0.00
discount_amount  = 0.00
net_line_total   = gross_line_total
scheme_applied   = False
```

**Example:** 3 cases of Glucose Biscuit at ₹777.60/case (₹8.10/pack × 96 packs, assumed):
```
gross = 777.60 × 3 = 2,332.80
net   = 2,332.80
```

---

### 4.2 BUY_N_GET_M_FREE

**Business rule:** Buy N paid cases → earn M additional free cases physically shipped.  
Retailer's payable amount is based on paid cases only. Free cases carry a `benefit_value` for reporting but are **not deducted from the payable**.

**Trigger:** `qty_paid >= min_qty`

```
sets_earned      = floor(qty_paid / min_qty)
qty_free         = sets_earned × free_qty
qty_fulfilment   = qty_paid + qty_free

gross_line_total = unit_price_per_case × qty_paid
benefit_value    = qty_free × unit_price_per_case    # informational only
discount_amount  = 0.00                              # no monetary deduction
net_line_total   = gross_line_total                  # retailer pays for paid cases
```

**Example:** 10 paid cases of Glucose Biscuit at ₹777.60/case, Buy 10 Get 1 Free:
```
sets_earned    = floor(10 / 10) = 1
qty_free       = 1 × 1 = 1
qty_fulfilment = 10 + 1 = 11
gross          = 777.60 × 10 = 7,776.00
benefit_value  = 1 × 777.60 = 777.60    (informational)
discount_amount = 0.00
net            = 7,776.00               (retailer pays for 10 cases)
```

**Fulfilment note:** When Order Desk approves the order, **11 cases** (qty_fulfilment) are deducted from `products.stock_cases`.

**Example:** 25 paid cases at ₹777.60/case, Buy 10 Get 1 Free:
```
sets_earned    = floor(25 / 10) = 2
qty_free       = 2 × 1 = 2
qty_fulfilment = 25 + 2 = 27
gross          = 777.60 × 25 = 19,440.00
benefit_value  = 2 × 777.60 = 1,555.20  (informational)
net            = 19,440.00
```

> **[OPEN QUESTION — Tally]** How should free cases appear on the Tally invoice? As a separate zero-value line? As a quantity adjustment? This is unconfirmed — the CSV export will include `qty_paid`, `qty_free`, and `qty_fulfilment` as separate columns so the client can decide.

---

### 4.3 DISCOUNT_ON_MIN_QTY

**Business rule:** A flat percentage discount is applied to the gross line total when the retailer orders at least `min_qty` paid cases.

**Trigger:** `qty_paid >= min_qty`

```
qty_free         = 0
qty_fulfilment   = qty_paid
gross_line_total = unit_price_per_case × qty_paid
discount_amount  = (gross_line_total × discount_pct / 100).quantize(TWO_PLACES, ROUND_HALF_UP)
benefit_value    = discount_amount   # for consistency; same as discount here
net_line_total   = gross_line_total − discount_amount
```

**Example:** 5 paid cases of Detergent Powder at ₹2,030.00/case (₹101.50/pack × 20 packs, assumed), 3% off ≥ 5 cases:
```
gross           = 2,030.00 × 5 = 10,150.00
discount_amount = round(10,150.00 × 0.03, 2) = round(304.50, 2) = 304.50
net             = 10,150.00 − 304.50 = 9,845.50
```

**Example:** 4 cases (scheme not triggered, min_qty = 5):
```
gross           = 2,030.00 × 4 = 8,120.00
discount_amount = 0.00
net             = 8,120.00
```

> **Note on rounding:** `307.50 × 0.03 = 9.225` → rounds to `9.23` with ROUND_HALF_UP. This is consistent across all discount calculations.

---

## 5. Price Derivation (Before Scheme Engine)

```python
# [ASSUMED] dealer_price_per_pack is what is stored in the DB (see assumption A-1)
unit_price_per_case = product.dealer_price_per_pack * product.case_qty
```

This derivation is performed in `CartService` / `OrderService` before passing data to the scheme engine. The scheme engine always receives `unit_price_per_case` as a `Decimal`.

---

## 6. Validity Date Check

```python
def is_scheme_valid(scheme: SchemeInput, order_date: date) -> bool:
    if not scheme.is_active:
        return False
    return scheme.valid_from <= order_date <= scheme.valid_to
```

---

## 7. Order-Level Totals

```python
gross_total   = sum(r.gross_line_total for r in results)
scheme_total  = sum(r.benefit_value for r in results)   # total informational benefit
net_total     = sum(r.net_line_total for r in results)  # actual payable
```

For `BUY_N_GET_M_FREE` lines, `benefit_value` feeds into `scheme_total` for reporting. The retailer's payable (`net_total`) correctly reflects only paid-case charges.

---

## 8. Edge Cases

| Edge Case | Rule |
|-----------|------|
| `qty_cases = 0` | Blocked by `CartService`; never reaches scheme engine |
| `scheme.min_qty = 0` | Data-entry error; treat as always qualifying. Admin alert needed. |
| `unit_price_per_case = 0` | Allowed; `benefit_value` will be ₹0 |
| Multiple active schemes on one product | **Not supported in MVP.** First scheme (by `valid_from` desc) is used. Must be resolved at data entry. |
| `discount_pct > 100` | Capped at 100% at application level |
| Free cases exceed available stock | Handled by stock revalidation during approval, not by scheme engine |

---

## 9. Python Implementation Sketch

```python
from decimal import Decimal, ROUND_HALF_UP
from math import floor

TWO_PLACES = Decimal("0.01")

def calculate_line(line: LineInput) -> SchemeResult:
    # Derive case price from pack price (assumption A-1)
    unit_price = line.unit_price_per_case  # already derived by caller

    gross = (unit_price * line.qty_cases).quantize(TWO_PLACES, ROUND_HALF_UP)

    no_scheme = (
        line.scheme is None
        or not line.scheme.is_active
        or not is_scheme_valid(line.scheme, line.order_date)
        or line.qty_cases < line.scheme.min_qty
    )

    if no_scheme:
        return SchemeResult(
            scheme_applied=False, scheme_type=None,
            qty_paid=line.qty_cases, qty_free=0,
            qty_fulfilment=line.qty_cases,
            gross_line_total=gross,
            benefit_value=Decimal("0.00"),
            discount_amount=Decimal("0.00"),
            net_line_total=gross,
            scheme_description="No scheme applied",
        )

    if line.scheme.scheme_type == "BUY_N_GET_M_FREE":
        sets     = floor(line.qty_cases / line.scheme.min_qty)
        qty_free = sets * line.scheme.free_qty
        benefit  = (qty_free * unit_price).quantize(TWO_PLACES, ROUND_HALF_UP)
        return SchemeResult(
            scheme_applied=True, scheme_type="BUY_N_GET_M_FREE",
            qty_paid=line.qty_cases, qty_free=qty_free,
            qty_fulfilment=line.qty_cases + qty_free,
            gross_line_total=gross,
            benefit_value=benefit,
            discount_amount=Decimal("0.00"),
            net_line_total=gross,  # retailer pays for paid cases
            scheme_description=f"{qty_free} case(s) free — Buy {line.scheme.min_qty} Get {line.scheme.free_qty}",
        )

    elif line.scheme.scheme_type == "DISCOUNT_ON_MIN_QTY":
        pct      = line.scheme.discount_pct / Decimal("100")
        discount = (gross * pct).quantize(TWO_PLACES, ROUND_HALF_UP)
        return SchemeResult(
            scheme_applied=True, scheme_type="DISCOUNT_ON_MIN_QTY",
            qty_paid=line.qty_cases, qty_free=0,
            qty_fulfilment=line.qty_cases,
            gross_line_total=gross,
            benefit_value=discount,
            discount_amount=discount,
            net_line_total=gross - discount,
            scheme_description=f"{line.scheme.discount_pct}% off — {line.qty_cases} cases",
        )
```


## 1. Design Principles

- The scheme engine is a **pure Python module** with no database or API calls.
- It is called by `CartService` and `OrderService` with product + quantity as input.
- It returns a `SchemeResult` object; it never mutates state.
- It is fully unit-testable in isolation.
- All monetary arithmetic uses Python's `Decimal` type (not `float`) to prevent rounding errors.

---

## 2. Supported Scheme Types (MVP)

| Type Enum | Name | Description |
|-----------|------|-------------|
| `BUY_N_GET_M_FREE` | Buy N Get M Free | Buy N cases, get M additional cases at no charge (reducing net payment) |
| `DISCOUNT_ON_MIN_QTY` | Percentage Discount on Minimum Quantity | A flat % discount on the entire line when quantity ≥ minimum |

---

## 3. Data Contract

### Input to Scheme Engine

```python
@dataclass
class SchemeInput:
    scheme_type: str              # "BUY_N_GET_M_FREE" or "DISCOUNT_ON_MIN_QTY"
    min_qty: int                  # Minimum cases to trigger scheme
    free_qty: Optional[int]       # Only for BUY_N_GET_M_FREE
    discount_pct: Optional[Decimal]  # Only for DISCOUNT_ON_MIN_QTY (e.g., Decimal("3.00"))
    valid_from: date
    valid_to: date
    is_active: bool

@dataclass
class LineInput:
    unit_price: Decimal           # Dealer price per case (Assumption A-1 pending)
    qty_cases: int
    scheme: Optional[SchemeInput]
    order_date: date              # To check scheme validity
```

### Output from Scheme Engine

```python
@dataclass
class SchemeResult:
    scheme_applied: bool
    scheme_type: Optional[str]
    gross_line_total: Decimal     # unit_price × qty_cases
    scheme_saving: Decimal        # Monetary saving from scheme (0 if none applied)
    net_line_total: Decimal       # gross_line_total − scheme_saving
    scheme_description: str       # Human-readable, e.g., "1 case free (Buy 10 Get 1)"
```

---

## 4. Calculation Rules

### 4.1 No Scheme (or Scheme Not Applicable)

Conditions: `scheme is None`, `is_active = False`, `order_date < valid_from`, `order_date > valid_to`, or `qty_cases < min_qty`.

```
gross_line_total = unit_price × qty_cases
scheme_saving    = 0
net_line_total   = gross_line_total
scheme_applied   = False
```

**Example:** 3 cases of Glucose Biscuit at ₹8.10 (Buy 10 Get 1 Free; min not met):
```
gross = 8.10 × 3 = 24.30
saving = 0.00
net = 24.30
```

---

### 4.2 BUY_N_GET_M_FREE

Scheme parameters: `min_qty = N`, `free_qty = M`.

**Trigger:** `qty_cases >= N`

**Calculation:**

```
# How many qualifying "sets" of N cases has the retailer ordered?
sets_earned   = floor(qty_cases / min_qty)

# Total free cases earned (not shipped extra; modelled as a price reduction)
# ASSUMPTION: Free cases are modelled as a monetary discount, not as extra physical cases.
# See open question below.
free_cases    = sets_earned × free_qty

scheme_saving = free_cases × unit_price

gross_line_total = unit_price × qty_cases
net_line_total   = gross_line_total − scheme_saving
```

> **[OPEN QUESTION]** Are free cases physically added to the invoice (e.g., "10 cases ordered + 1 free = 11 cases on delivery slip"), or modelled as a monetary discount on 10 cases? This affects the invoice quantity on the Tally export.  
> **[ASSUMED]** For MVP, free cases are modelled as a monetary discount on the ordered quantity. The invoice quantity is `qty_cases` (not `qty_cases + free_cases`).

**Example:** 10 cases of Glucose Biscuit at ₹8.10, Buy 10 Get 1 Free:
```
sets_earned   = floor(10 / 10) = 1
free_cases    = 1 × 1 = 1
scheme_saving = 1 × 8.10 = 8.10
gross         = 8.10 × 10 = 81.00
net           = 81.00 − 8.10 = 72.90
```

**Example:** 25 cases at ₹8.10, Buy 10 Get 1 Free:
```
sets_earned   = floor(25 / 10) = 2
free_cases    = 2 × 1 = 2
scheme_saving = 2 × 8.10 = 16.20
gross         = 8.10 × 25 = 202.50
net           = 202.50 − 16.20 = 186.30
```

---

### 4.3 DISCOUNT_ON_MIN_QTY

Scheme parameters: `min_qty = N`, `discount_pct = D%`

**Trigger:** `qty_cases >= N`

**Calculation:**

```
gross_line_total = unit_price × qty_cases
scheme_saving    = round(gross_line_total × (discount_pct / 100), 2)
net_line_total   = gross_line_total − scheme_saving
```

Rounding rule: **round half up** (Python `Decimal` with `ROUND_HALF_UP`).

**Example:** 5 cases of Detergent Powder at ₹101.50, 3% off on ≥ 5 cases:
```
gross    = 101.50 × 5 = 507.50
saving   = round(507.50 × 0.03, 2) = round(15.225, 2) = 15.23
net      = 507.50 − 15.23 = 492.27
```

**Example:** 4 cases (scheme not triggered, min_qty = 5):
```
gross    = 101.50 × 4 = 406.00
saving   = 0.00
net      = 406.00
```

---

## 5. Validity Date Check

```python
def is_scheme_valid(scheme: SchemeInput, order_date: date) -> bool:
    if not scheme.is_active:
        return False
    return scheme.valid_from <= order_date <= scheme.valid_to
```

A scheme that has expired is silently not applied; the retailer sees no scheme benefit on that product even if the UI showed the scheme badge at catalogue browse time (the badge would have expired too if dates are checked on the frontend).

---

## 6. Order-Level Totals

After all line-level `SchemeResult` objects are computed:

```python
gross_total  = sum(line.gross_line_total for line in results)
scheme_total = sum(line.scheme_saving for line in results)
net_total    = gross_total - scheme_total
# Equivalently: net_total = sum(line.net_line_total for line in results)
```

No cross-line or order-level schemes are defined for MVP. If order-level discounts (e.g., "5% off orders above ₹5,000") are introduced, they are applied after all line-level schemes.

---

## 7. Edge Cases

| Edge Case | Rule |
|-----------|------|
| `qty_cases = 0` | Should never reach scheme engine; `CartService` blocks 0-qty lines |
| Scheme `min_qty = 0` | Treated as always qualifying; this is a data-entry error — the admin should be notified |
| `unit_price = 0` | Not blocked by scheme engine; `scheme_saving` will be ₹0 regardless |
| Multiple active schemes on one product | **Not supported in MVP.** The query returns at most one active scheme; if data has two, the first one (by `valid_from` desc) is used. This must be resolved at data entry. |
| `discount_pct > 100` | Capped at 100%; a saving greater than the gross total is a data error |

---

## 8. Python Implementation Sketch

```python
from decimal import Decimal, ROUND_HALF_UP
from math import floor

TWO_PLACES = Decimal("0.01")

def calculate_line(line: LineInput) -> SchemeResult:
    gross = (line.unit_price * line.qty_cases).quantize(TWO_PLACES)

    if (
        line.scheme is None
        or not line.scheme.is_active
        or not is_scheme_valid(line.scheme, line.order_date)
        or line.qty_cases < line.scheme.min_qty
    ):
        return SchemeResult(
            scheme_applied=False,
            scheme_type=None,
            gross_line_total=gross,
            scheme_saving=Decimal("0.00"),
            net_line_total=gross,
            scheme_description="No scheme applied",
        )

    if line.scheme.scheme_type == "BUY_N_GET_M_FREE":
        sets = floor(line.qty_cases / line.scheme.min_qty)
        free = sets * line.scheme.free_qty
        saving = (free * line.unit_price).quantize(TWO_PLACES, ROUND_HALF_UP)
        desc = f"{free} case(s) free (Buy {line.scheme.min_qty} Get {line.scheme.free_qty})"

    elif line.scheme.scheme_type == "DISCOUNT_ON_MIN_QTY":
        pct = line.scheme.discount_pct / Decimal("100")
        saving = (gross * pct).quantize(TWO_PLACES, ROUND_HALF_UP)
        desc = f"{line.scheme.discount_pct}% discount on {line.qty_cases} cases"

    net = gross - saving
    return SchemeResult(
        scheme_applied=True,
        scheme_type=line.scheme.scheme_type,
        gross_line_total=gross,
        scheme_saving=saving,
        net_line_total=net,
        scheme_description=desc,
    )
```

