# 05 — API Endpoint Design

## Conventions

- Base URL: `/api/v1`
- All request/response bodies: `application/json`
- Authentication: `Authorization: Bearer <access_token>` header on all protected routes
- Error envelope:
  ```json
  {
    "detail": "Human-readable message",
    "code": "MACHINE_READABLE_CODE"
  }
  ```
- Timestamps: ISO 8601 UTC strings (`2026-11-06T13:12:00Z`)
- UUIDs: lowercase hyphenated strings
- Monetary values: strings with 2 decimal places (e.g., `"8.10"`) to avoid floating-point issues in transit
  - **[ASSUMPTION]** This format may need adjustment based on client/Tally requirements.

---

## 1. Auth Endpoints

### `POST /api/v1/auth/retailer/request-otp`
Request an OTP for retailer login.

**Auth:** None  
**Body:**
```json
{ "mobile": "9876543210" }
```
**Response 200:**
```json
{ "message": "OTP sent", "expires_in_seconds": 600 }
```
**Errors:** `422` invalid mobile, `429` rate limit hit

---

### `POST /api/v1/auth/retailer/verify-otp`
Verify OTP and receive tokens.

**Auth:** None  
**Body:**
```json
{ "mobile": "9876543210", "otp": "123456" }
```
**Response 200:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900,
  "retailer": {
    "id": "uuid",
    "name": "Sharma General Store",
    "mobile": "9876543210"
  }
}
```
Refresh token set as `HttpOnly` cookie named `refresh_token`.  
**Errors:** `401` invalid/expired OTP, `423` account locked, `404` retailer not found

---

### `POST /api/v1/auth/desk/login`
Order Desk email + password login.

**Auth:** None  
**Body:**
```json
{ "email": "desk@dukaanflow.in", "password": "secret" }
```
**Response 200:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900,
  "user": {
    "id": "uuid",
    "full_name": "Ramesh Verma",
    "email": "desk@dukaanflow.in",
    "role": "order_desk"
  }
}
```
**Errors:** `401` invalid credentials, `403` account inactive

---

### `POST /api/v1/auth/refresh`
Get a new access token using the refresh token cookie.

**Auth:** HttpOnly cookie `refresh_token`  
**Body:** Empty  
**Response 200:** Same as login response (new access token)  
**Errors:** `401` invalid/expired/blocklisted refresh token

---

### `POST /api/v1/auth/logout`
Invalidate the refresh token.

**Auth:** Bearer token (any role)  
**Body:** Empty  
**Response 200:** `{ "message": "Logged out" }`  
Refresh token cookie cleared and JTI added to blocklist.

---

## 2. Catalogue Endpoints

### `GET /api/v1/catalogue/products`
List active products.

**Auth:** Retailer or Order Desk  
**Query params:**
- `q` (string, min 2 chars) — search by name
- `category` (string) — filter by category
- `in_stock` (bool, default false) — filter to in-stock only
- `page` (int, default 1), `page_size` (int, default 20, max 100)

**Response 200:**
```json
{
  "items": [
    {
      "id": "uuid",
      "sku": "SKU-BS-075",
      "name": "Glucose Biscuit 75g",
      "pack_size": "75g",
      "case_qty": 96,
      "dealer_price_per_case": "8.10",
      "stock_cases": 340,
      "stock_status": "in_stock",
      "category": "Biscuits",
      "active_scheme": {
        "type": "BUY_N_GET_M_FREE",
        "min_qty": 10,
        "free_qty": 1,
        "valid_to": "2026-12-31"
      }
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 20
}
```
`stock_status` values: `in_stock`, `low_stock` (< 10 cases), `out_of_stock`

---

### `GET /api/v1/catalogue/products/{sku}`
Single product detail.

**Auth:** Retailer or Order Desk  
**Response 200:** Single product object (same shape as list item)  
**Errors:** `404` product not found or inactive

---

## 3. Cart Endpoints

### `GET /api/v1/cart`
Get the current retailer's cart with computed totals.

**Auth:** Retailer only  
**Response 200:**
```json
{
  "id": "uuid",
  "lines": [
    {
      "id": "uuid",
      "product_id": "uuid",
      "sku": "SKU-BS-075",
      "name": "Glucose Biscuit 75g",
      "qty_cases": 10,
      "unit_price": "8.10",
      "gross_line_total": "81.00",
      "scheme_applied": {
        "type": "BUY_N_GET_M_FREE",
        "free_qty": 1,
        "saving": "8.10"
      },
      "net_line_total": "72.90"
    }
  ],
  "summary": {
    "gross_total": "81.00",
    "total_scheme_saving": "8.10",
    "net_total": "72.90",
    "item_count": 1
  },
  "updated_at": "2026-11-06T13:00:00Z"
}
```

---

### `POST /api/v1/cart/lines`
Add or update a product line in the cart. If the product already exists in the cart, its quantity is replaced (not added).

**Auth:** Retailer only  
**Body:**
```json
{ "product_id": "uuid", "qty_cases": 10 }
```
**Response 200:** Full cart object (same as GET)  
**Errors:**
- `404` product not found
- `422` invalid quantity (0 or negative)
- `409` requested qty exceeds available stock
- `422` product out of stock

---

### `DELETE /api/v1/cart/lines/{line_id}`
Remove a line from the cart.

**Auth:** Retailer only  
**Response 200:** Full cart object  
**Errors:** `404` line not found or not in this retailer's cart

---

### `DELETE /api/v1/cart`
Clear all lines from the cart.

**Auth:** Retailer only  
**Response 200:** Empty cart object

---

### `POST /api/v1/cart/from-ai-draft`
Populate cart from a confirmed AI draft (replaces existing cart).

**Auth:** Retailer only  
**Body:**
```json
{
  "lines": [
    { "product_id": "uuid", "qty_cases": 5 },
    { "product_id": "uuid", "qty_cases": 2 }
  ]
}
```
**Response 200:** Full cart object  
**Errors:** Same stock/product errors as adding individual lines; all lines are validated before any are written (atomic).

---

## 4. Order Endpoints

### `POST /api/v1/orders`
Place an order from the current cart.

**Auth:** Retailer only  
**Body:**
```json
{ "remarks": "Please deliver before 10am" }
```
**Response 201:**
```json
{
  "order_id": "uuid",
  "status": "pending_review",
  "net_total": "72.90",
  "created_at": "2026-11-06T13:05:00Z",
  "message": "Your order has been placed and is under review."
}
```
Cart is emptied after successful order placement.  
**Errors:** `422` empty cart, `409` stock conflict (item became out of stock between cart add and place)

---

### `GET /api/v1/orders`
Retailer: list their own orders. Order Desk: list all orders.

**Auth:** Retailer or Order Desk  
**Query params:**
- `status` — filter by status
- `retailer_id` — Order Desk only; filter by retailer
- `date_from`, `date_to` — ISO date strings
- `q` — Order Desk only; search by retailer name or mobile
- `page`, `page_size`

**Response 200:** Paginated list of order summaries.

---

### `GET /api/v1/orders/{order_id}`
Full order detail including all lines.

**Auth:**
- Retailer: can only fetch their own orders
- Order Desk: can fetch any order

**Response 200:**
```json
{
  "id": "uuid",
  "retailer": { "id": "uuid", "name": "Sharma Store", "mobile": "9876543210" },
  "status": "pending_review",
  "lines": [ { "...": "..." } ],
  "summary": { "gross_total": "...", "scheme_saving": "...", "net_total": "..." },
  "remarks": "...",
  "created_at": "...",
  "updated_at": "...",
  "audit_log": [
    { "actor_type": "retailer", "to_status": "pending_review", "created_at": "..." }
  ]
}
```

---

### `PATCH /api/v1/orders/{order_id}/status`
Change order status. Order Desk only.

**Auth:** Order Desk only  
**Body:**
```json
{
  "status": "approved",
  "note": "optional note"
}
```
Or for rejection:
```json
{
  "status": "rejected",
  "note": "Price dispute on biscuit line"
}
```
`note` is **required** when `status` is `rejected`.  
**Response 200:** Updated order object.  
**Errors:** `403` retailer attempts this endpoint, `422` invalid status transition

---

### `PATCH /api/v1/orders/{order_id}/lines/{line_id}`
Order Desk edits a specific line (quantity adjustment or price correction).

**Auth:** Order Desk only  
**Body:**
```json
{ "qty_cases": 8 }
```
**Response 200:** Updated order object with recalculated totals.  
**Errors:** `422` quantity exceeds stock, only allowed when order is in `pending_review`

---

### `DELETE /api/v1/orders/{order_id}/lines/{line_id}`
Order Desk removes a line. Only when order is `pending_review`.

**Auth:** Order Desk only  
**Response 200:** Updated order object.

---

### `POST /api/v1/orders/{order_id}/cancel`
Retailer cancels their own order.

**Auth:** Retailer only (must own the order)  
**Response 200:** Updated order (status: `cancelled`)  
**Errors:** `422` order is not in `pending_review`

---

## 5. AI Order Capture Endpoints

### `POST /api/v1/ai/extract`
Extract a structured order draft from raw text.

**Auth:** Retailer only  
**Body:**
```json
{
  "raw_text": "bhaiya 5 peti biscuit chhota, 2 peti washing powder 1 kilo, chai patti 250 wala 1 peti"
}
```
**Response 200:**
```json
{
  "raw_text": "...",
  "lines": [
    {
      "raw_fragment": "5 peti biscuit chhota",
      "match_status": "confirmed",
      "confidence_level": "medium",
      "product": {
        "id": "uuid",
        "sku": "SKU-BS-075",
        "name": "Glucose Biscuit 75g",
        "dealer_price_per_pack": "8.10",
        "dealer_price_per_case": "777.60",
        "stock_cases": 340,
        "stock_status": "in_stock"
      },
      "qty_cases": 5,
      "unit_unclear": false,
      "alternatives": []
    },
    {
      "raw_fragment": "2 peti washing powder 1 kilo",
      "match_status": "confirmed",
      "confidence_level": "medium",
      "product": { "sku": "SKU-DT-1KG" },
      "qty_cases": 2,
      "unit_unclear": false,
      "alternatives": []
    },
    {
      "raw_fragment": "chai patti 250 wala 1 peti",
      "match_status": "confirmed",
      "confidence_level": "high",
      "product": {
        "sku": "SKU-TE-250",
        "stock_cases": 0,
        "stock_status": "out_of_stock"
      },
      "qty_cases": 1,
      "unit_unclear": false,
      "alternatives": [],
      "warning": "OUT_OF_STOCK"
    }
  ],
  "unmatched_fragments": [],
  "processing_note": "Tea 250g is out of stock and cannot be added to cart."
}
```
`confidence_level` values: `"high"` (alias/exact), `"medium"` (single ilike), `"low"` (weak fuzzy — requires confirmation), `null` (ambiguous or unmatched).  
`alternatives` contains **at most 2** items.  
**Errors:** `503` Gemini API unavailable, `422` empty text, `429` rate limit

---

## 6. Export Endpoints

### `GET /api/v1/export/orders/{order_id}/tally-csv`
Download a generic configurable CSV for a single approved order.

**Auth:** Order Desk only  
**Response:** `text/csv` file download  
**Errors:** `404` order not found, `422` order not in `approved` status

**CSV columns (generic — exact Tally format unconfirmed, see assumption D-1):**

| Column | Example | Notes |
|--------|---------|-------|
| `OrderID` | `uuid` | |
| `OrderDate` | `06-11-2026` | |
| `PartyLedger` | `Sharma General Store` | From `tally_ledger_name` |
| `SKU` | `SKU-BS-075` | |
| `StockItem` | `Glucose Biscuit 75g` | |
| `QtyPaid` | `10` | Cases retailer pays for |
| `QtyFree` | `1` | Free cases (BUY_N_GET_M_FREE) |
| `QtyFulfilment` | `11` | Total cases to deliver |
| `RatePerCase` | `777.60` | unit_price_snapshot |
| `GrossAmount` | `7776.00` | |
| `SchemeType` | `BUY_N_GET_M_FREE` | |
| `BenefitValue` | `777.60` | Informational |
| `DiscountAmount` | `0.00` | Monetary deduction (0 for free-goods) |
| `NetAmount` | `7776.00` | Retailer's payable |
| `GSTRate` | `` | Blank until GST confirmed (assumption A-2) |
| `GSTAmount` | `` | Blank until GST confirmed |

> **Note:** Column names, ordering, and date format will be adjusted once the client's exact Tally Prime import specification is confirmed.

---

### `GET /api/v1/export/orders/tally-csv-batch`
Batch export multiple approved orders as a single CSV.

**Auth:** Order Desk only  
**Query params:** `order_ids` (comma-separated list of UUIDs)  
**Response:** `text/csv` file download

---

## 7. Order Desk — Product Correction

### `POST /api/v1/orders/{order_id}/lines/{line_id}/correct-product`
Correct the product assignment on an order line. Only available when order is `pending_review`.

**Auth:** Order Desk only  
**Body:**
```json
{ "product_id": "uuid-of-correct-product" }
```
**Response 200:** Updated order object with recalculated totals.  
**Side effect:** Saves a retailer alias: `raw_fragment → corrected product_id` with `source = "desk"`.  
**Errors:** `404` line not found, `422` order not in `pending_review`, `422` product not found/inactive

---

## 8. Health Check

### `GET /api/v1/health`
**Auth:** None  
**Response 200:**
```json
{ "status": "ok", "db": "connected", "version": "0.1.0" }
```

