# 04 — Database Schema (ER Diagram and Table Descriptions)

## 1. Entity-Relationship Diagram

```
┌─────────────────┐          ┌──────────────────────┐
│    retailers    │          │    order_desk_users  │
├─────────────────┤          ├──────────────────────┤
│ PK id (uuid)    │          │ PK id (uuid)         │
│    mobile       │          │    email             │
│    name         │          │    password_hash     │
│    address      │          │    full_name         │
│    tally_ledger │          │    is_active         │
│    credit_limit │          │    created_at        │
│    is_active    │          └──────────────────────┘
│    created_at   │
└────────┬────────┘
         │ 1
         │
         │ N
┌────────▼────────┐          ┌──────────────────────────┐
│     orders      │          │        products           │
├─────────────────┤          ├──────────────────────────┤
│ PK id (uuid)    │          │ PK id (uuid)              │
│ FK retailer_id  │          │    sku                    │
│ FK reviewed_by  │          │    name                   │
│    order_source │  ◄── NEW │    description            │
│    status       │          │    pack_size              │
│    gross_total  │          │    case_qty               │
│    scheme_total │          │    dealer_price_per_pack  │  ◄── RENAMED
│    net_total    │          │    gst_rate_pct (NULL)    │  ◄── NEW
│    remarks      │          │    price_unit             │  ◄── NEW
│    created_at   │          │    stock_cases            │
│    updated_at   │          │    category               │
└────────┬────────┘          │    is_active              │
         │ 1                 │    created_at             │
         │                   │    updated_at             │
         │ N                 └──────────┬────────────────┘
┌────────▼────────┐                    │ 1
│   order_lines   │                    │
├─────────────────┤                    │ N
│ PK id (uuid)    │          ┌─────────▼──────────────┐
│ FK order_id     │          │        schemes          │
│ FK product_id   │          ├────────────────────────┤
│    sku_snapshot │          │ PK id (uuid)           │
│    name_snapshot│          │ FK product_id          │
│    raw_fragment │  ◄── NEW │    scheme_type         │
│    qty_paid     │  ◄── NEW │    min_qty             │
│    qty_free     │  ◄── NEW │    free_qty            │
│    qty_fulfilmnt│  ◄── NEW │    discount_pct        │
│    unit_price   │          │    valid_from          │
│    gross_line   │          │    valid_to            │
│    scheme_snap  │  ◄── NEW │    is_active           │
│    benefit_value│  ◄── NEW └────────────────────────┘
│    net_line     │
└─────────────────┘

┌──────────────────────────────┐
│      retailer_aliases        │
├──────────────────────────────┤
│ PK id (uuid)                 │
│ FK retailer_id               │
│ FK product_id                │
│    raw_term (text)           │
│    source  (retailer/desk)   │  ◄── NEW
│    created_at                │
└──────────────────────────────┘

┌──────────────────────────────┐
│       otp_records            │
├──────────────────────────────┤
│ PK id (uuid)                 │
│    mobile                    │
│    otp_hash                  │
│    attempts                  │
│    locked                    │  ◄── RENAMED (was `used`)
│    expires_at                │
│    created_at                │
└──────────────────────────────┘

┌──────────────────────────────┐
│      refresh_token_blocklist │
├──────────────────────────────┤
│ PK id (uuid)                 │
│    jti (text, indexed)       │
│    expires_at                │
│    created_at                │
└──────────────────────────────┘

┌──────────────────────────────┐
│      order_audit_log         │
├──────────────────────────────┤
│ PK id (uuid)                 │
│ FK order_id                  │
│    actor_type (retailer/desk)│
│    actor_id  (uuid)          │
│    from_status               │
│    to_status                 │
│    note                      │
│    created_at                │
└──────────────────────────────┘

┌──────────────────────────────┐
│          carts               │
├──────────────────────────────┤
│ PK id (uuid)                 │
│ FK retailer_id (unique)      │
│    created_at                │
│    updated_at                │
└──────────────────────────────┘

┌──────────────────────────────┐
│        cart_lines            │
├──────────────────────────────┤
│ PK id (uuid)                 │
│ FK cart_id                   │
│ FK product_id                │
│    qty_cases                 │
│    added_at                  │
└──────────────────────────────┘
```

---

## 2. Table Descriptions

### `retailers`
Represents a kirana shop / retailer account.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | Generated server-side |
| `mobile` | VARCHAR(15) UNIQUE NOT NULL | Used as login identifier |
| `name` | VARCHAR(200) NOT NULL | Shop or owner name |
| `address` | TEXT | Delivery address |
| `tally_ledger_name` | VARCHAR(200) | Maps to Tally Party Ledger; manually set initially |
| `credit_limit` | NUMERIC(12,2) DEFAULT 0 | 0 = no limit enforced (assumption B-6) |
| `is_active` | BOOLEAN DEFAULT TRUE | Soft-disable instead of delete |
| `created_at` | TIMESTAMPTZ NOT NULL | Server UTC timestamp |

**Indices:** `mobile` (unique), `is_active`.

---

### `order_desk_users`
Represents an Order Desk staff member.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `email` | VARCHAR(255) UNIQUE NOT NULL | Login identifier |
| `password_hash` | TEXT NOT NULL | bcrypt hash |
| `full_name` | VARCHAR(200) NOT NULL | |
| `is_active` | BOOLEAN DEFAULT TRUE | |
| `created_at` | TIMESTAMPTZ NOT NULL | |

---

### `products`
The distributor's product catalogue.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `sku` | VARCHAR(50) UNIQUE NOT NULL | e.g., `SKU-BS-075` |
| `name` | VARCHAR(300) NOT NULL | Full product name |
| `description` | TEXT | Optional |
| `pack_size` | VARCHAR(100) | e.g., `75g`, `1kg` — descriptive only |
| `case_qty` | INTEGER NOT NULL | Number of retail packs per case |
| `dealer_price_per_pack` | NUMERIC(10,2) NOT NULL | **[ASSUMED]** Price per retail pack. See assumption A-1. |
| `price_unit` | VARCHAR(20) NOT NULL DEFAULT `'per_pack'` | Tracks the assumption: `'per_pack'` currently. Update to `'per_case'` if client confirms. |
| `gst_rate_pct` | NUMERIC(5,2) NULLABLE | GST rate percentage. NULL = unspecified. See assumption A-2. |
| `stock_cases` | INTEGER NOT NULL DEFAULT 0 | Available stock in full cases |
| `category` | VARCHAR(100) | Optional grouping (Biscuits, Detergent, etc.) |
| `is_active` | BOOLEAN DEFAULT TRUE | |
| `created_at` | TIMESTAMPTZ NOT NULL | |
| `updated_at` | TIMESTAMPTZ NOT NULL | Updated by trigger or service |

**Computed at runtime (not stored):** `dealer_price_per_case = dealer_price_per_pack × case_qty`

**Indices:** `sku` (unique), `is_active`, `category`, full-text index on `name` for search.

---

### `schemes`
Promotional schemes attached to products.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `product_id` | UUID FK → products | |
| `scheme_type` | VARCHAR(50) NOT NULL | Enum: `BUY_N_GET_M_FREE`, `DISCOUNT_ON_MIN_QTY` |
| `min_qty` | INTEGER NOT NULL | Minimum cases to qualify |
| `free_qty` | INTEGER | Only for `BUY_N_GET_M_FREE`; NULL otherwise |
| `discount_pct` | NUMERIC(5,2) | Only for `DISCOUNT_ON_MIN_QTY`; NULL otherwise |
| `valid_from` | DATE NOT NULL | Inclusive |
| `valid_to` | DATE NOT NULL | Inclusive |
| `is_active` | BOOLEAN DEFAULT TRUE | Manual override |

**Constraint:** CHECK that exactly one of `free_qty` or `discount_pct` is non-NULL based on `scheme_type`.  
**Index:** `product_id`, `is_active`, `valid_from`, `valid_to`.

> **Note:** Only one scheme per product is assumed active at a time for MVP. Multiple overlapping schemes are out of scope.

---

### `carts`
One active cart per retailer (1-to-1 with retailer).

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `retailer_id` | UUID FK UNIQUE → retailers | One cart per retailer |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

---

### `cart_lines`
Individual product lines in a cart.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `cart_id` | UUID FK → carts | |
| `product_id` | UUID FK → products | |
| `qty_cases` | INTEGER NOT NULL CHECK (qty_cases > 0) | |
| `added_at` | TIMESTAMPTZ | |

**Unique constraint:** `(cart_id, product_id)` — only one line per product per cart.

---

### `orders`
An order placed by a retailer.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `retailer_id` | UUID FK → retailers | |
| `reviewed_by` | UUID FK → order_desk_users NULLABLE | Set on first Order Desk action |
| `order_source` | VARCHAR(20) NOT NULL DEFAULT `'manual'` | `'manual'` = added from catalogue; `'ai_capture'` = originated from AI extraction |
| `status` | VARCHAR(30) NOT NULL | Enum: `pending_review`, `approved`, `rejected`, `cancelled` |
| `gross_total` | NUMERIC(12,2) NOT NULL | Sum of gross line totals |
| `scheme_total` | NUMERIC(12,2) NOT NULL DEFAULT 0 | Total scheme benefit value |
| `net_total` | NUMERIC(12,2) NOT NULL | Amount payable (gross_total − scheme_total for discount; gross for free-goods) |
| `remarks` | TEXT | Retailer remarks at placement |
| `rejection_reason` | TEXT | Required when status = rejected |
| `created_at` | TIMESTAMPTZ NOT NULL | |
| `updated_at` | TIMESTAMPTZ NOT NULL | |

**Indices:** `retailer_id`, `status`, `created_at`.

---

### `order_lines`
Snapshot of each product ordered (prices snapshotted at order creation time).

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `order_id` | UUID FK → orders | |
| `product_id` | UUID FK → products | |
| `sku_snapshot` | VARCHAR(50) NOT NULL | SKU at time of order |
| `name_snapshot` | VARCHAR(300) NOT NULL | Product name at time of order |
| `raw_fragment` | TEXT NULLABLE | Original text from AI extraction (e.g., `"5 peti biscuit chhota"`); NULL for manually-added lines |
| `qty_paid` | INTEGER NOT NULL | Cases the retailer pays for |
| `qty_free` | INTEGER NOT NULL DEFAULT 0 | Additional free cases earned under scheme (physical fulfilment) |
| `qty_fulfilment` | INTEGER GENERATED AS `(qty_paid + qty_free)` STORED | Total cases to be delivered |
| `unit_price_snapshot` | NUMERIC(10,2) NOT NULL | `dealer_price_per_pack × case_qty` at time of order — per case |
| `gross_line_total` | NUMERIC(12,2) NOT NULL | `unit_price_snapshot × qty_paid` (free cases not charged) |
| `scheme_snapshot` | TEXT NULLABLE | JSON snapshot of the scheme applied, e.g., `{"type":"BUY_N_GET_M_FREE","min_qty":10,"free_qty":1}` |
| `benefit_value` | NUMERIC(12,2) NOT NULL DEFAULT 0 | Monetary value of free goods (`free_cases × unit_price`); informational only |
| `net_line_total` | NUMERIC(12,2) NOT NULL | For `BUY_N_GET_M_FREE`: equals `gross_line_total` (retailer pays for paid cases only). For `DISCOUNT_ON_MIN_QTY`: `gross_line_total − discount_amount`. |

> **Why snapshots?** Product prices may change after order placement. The order must reflect prices at the time of ordering, not current prices.

> **Why separate `qty_paid` / `qty_free` / `qty_fulfilment`?** The free-goods scheme model requires knowing how many cases were charged vs. delivered. This separates the financial record (`qty_paid`, `gross_line_total`) from the inventory/fulfilment record (`qty_fulfilment`). Stock is decremented by `qty_fulfilment` on approval.

---

### `retailer_aliases`
Maps a retailer's informal product name/term to a canonical SKU. Created by retailer confirmations and by Order Desk product corrections.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `retailer_id` | UUID FK → retailers | |
| `product_id` | UUID FK → products | |
| `raw_term` | TEXT NOT NULL | The informal term (lowercase, stripped) |
| `source` | VARCHAR(20) NOT NULL DEFAULT `'retailer'` | `'retailer'` = saved when retailer confirms an ambiguous match; `'desk'` = saved when Order Desk corrects a product on a submitted order |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

**Unique constraint:** `(retailer_id, raw_term)`.

---

### `otp_records`
Tracks OTP lifecycle for retailer mobile login.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `mobile` | VARCHAR(15) NOT NULL | |
| `otp_hash` | TEXT NOT NULL | bcrypt hash of the OTP |
| `attempts` | INTEGER DEFAULT 0 | Failed attempts counter |
| `locked` | BOOLEAN DEFAULT FALSE | Set to `True` after 5 failed attempts. Replaces `used`. A locked OTP cannot be verified even with the correct code; a new OTP must be requested. |
| `verified` | BOOLEAN DEFAULT FALSE | Set to `True` after a successful verification |
| `expires_at` | TIMESTAMPTZ NOT NULL | 10 minutes from creation |
| `created_at` | TIMESTAMPTZ | |

**Index:** `mobile`, `expires_at`.

> **Reconciled rule:** An OTP locks after 5 failed attempts (`locked = True`). There is no separate account-level 30-minute lockout. The retailer may request a new OTP immediately; rate limiting (max 3/mobile/10 min) prevents OTP farming. See assumption E-1.

---

### `refresh_token_blocklist`
Invalidated refresh tokens (logout/rotation).

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `jti` | TEXT NOT NULL UNIQUE | JWT ID claim from the refresh token |
| `expires_at` | TIMESTAMPTZ NOT NULL | Tokens past this date can be pruned |
| `created_at` | TIMESTAMPTZ | |

**Index:** `jti` (unique lookup), `expires_at` (for cleanup job).

---

### `order_audit_log`
Immutable log of every status change on an order.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `order_id` | UUID FK → orders | |
| `actor_type` | VARCHAR(20) NOT NULL | `retailer` or `order_desk` |
| `actor_id` | UUID NOT NULL | ID from respective user table |
| `from_status` | VARCHAR(30) | NULL for first entry |
| `to_status` | VARCHAR(30) NOT NULL | |
| `note` | TEXT | Optional context (rejection reason, etc.) |
| `created_at` | TIMESTAMPTZ NOT NULL | |

**Index:** `order_id`, `created_at`.

---

## 3. Enumerated Values

### Order Status FSM

```
                  ┌──────────────────┐
                  │  pending_review  │◄── created here
                  └────────┬─────────┘
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
        approved       rejected       cancelled
        (by desk)      (by desk)    (by retailer,
                                   only from pending)
```

### Scheme Types
- `BUY_N_GET_M_FREE` — Buy N cases, get M cases free.
- `DISCOUNT_ON_MIN_QTY` — Percentage discount applied when minimum quantity met.

