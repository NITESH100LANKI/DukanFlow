# 01 — Functional Requirements

## 1. Authentication Module

### FR-AUTH-01 — Retailer Login
- Retailers log in using their registered mobile number.
- A 6-digit OTP is sent to the mobile number and must be verified within 10 minutes.
- For the demo phase, a fixed OTP (e.g., `123456`) is acceptable; this assumption is flagged in `02-assumptions-and-open-questions.md`.
- On success, the backend issues a signed JWT access token (15-minute expiry) and a refresh token (7-day expiry).
- Failed OTP attempts are tracked on the active OTP record. After 5 consecutive failed attempts on an OTP, that OTP record is locked (`locked = True`). The retailer must request a new OTP. Rate limiting (max 3 requests/10 min) protects against abuse.

### FR-AUTH-02 — Order Desk Login
- Order Desk staff log in with an email address and password.
- Passwords are stored as bcrypt hashes (minimum cost factor 12).
- Same JWT and refresh token structure as retailers.

### FR-AUTH-03 — Token Refresh
- A dedicated `/auth/refresh` endpoint accepts the refresh token and returns a new access token without requiring re-authentication.

### FR-AUTH-04 — Logout
- The client discards both tokens.
- The refresh token is added to a server-side blocklist (stored in the database) until it expires naturally.

---

## 2. Product Catalogue Module

### FR-CAT-01 — Product Listing
- Retailers can browse all active products assigned to the distributor.
- Each product card shows: name, pack size, case quantity, dealer price per pack, derived dealer price per case (`dealer_price_per_pack × case_qty`), available stock (in cases), tax treatment ("Tax: Unspecified"), and any active scheme.
- Out-of-stock products are displayed with a clear "Out of Stock" badge; they cannot be added to cart.

### FR-CAT-02 — Retailer-Specific Pricing
- Dealer prices shown to a retailer are based on `dealer_price_per_pack` with case price derived from `case_qty`.
  - **[ASSUMED]** The supplied demo prices are per retail pack (not per case). This remains an unconfirmed assumption.
- Price computation is done exclusively by the backend; the frontend only renders values returned by the API.
- Tax treatment: GST rates and inclusion status are unspecified. No GST is calculated or invented; tax status is clearly displayed as "Unspecified".

### FR-CAT-03 — Stock Display
- Stock is shown in cases. If stock < 10 cases, display "Low Stock (N left)" to prompt urgency.
- Stock quantities are read-only for retailers.

### FR-CAT-04 — Scheme Display
- Active schemes are shown inline on each product card.
- Scheme types supported (MVP): Buy-N-Get-M-Free, Percentage-Discount-on-Minimum-Quantity.
- Schemes can have validity dates; expired schemes are not displayed.

### FR-CAT-05 — Search and Filter
- Retailers can search products by name or partial name (minimum 2 characters).
- Filter by: in-stock only, category (if categories are available).

---

## 3. Shopping Cart Module

### FR-CART-01 — Add to Cart
- Retailer can add a product to their cart in whole-case units only.
  - **Assumption:** Piece-level ordering is out of scope for MVP. Flagged in `02-assumptions-and-open-questions.md`.
- Minimum quantity is 1 case. Maximum quantity per line item is capped at available stock.
- Adding an out-of-stock item is blocked with a clear error message.

### FR-CART-02 — Cart Persistence
- Cart state is persisted in the backend (database), not solely in browser local storage, so it survives page refresh and device switches.

### FR-CART-03 — Line Item Totals
- For each cart line, the backend returns: unit price (per case), quantity, gross line total, scheme benefit (if any), and net line total.
- Backend recalculates totals on every add/update/remove; the frontend never performs price arithmetic.

### FR-CART-04 — Cart Summary
- Cart summary shows: subtotal (gross), total scheme savings, net payable total, and item count.
- Cart summary is recomputed by the backend on every mutation.

### FR-CART-05 — Remove / Update Quantity
- Retailer can change quantity or remove a line item.
- Scheme recalculation is triggered automatically.

### FR-CART-06 — Stock Validation at Checkout
- At order placement, the backend re-validates that all items are still in stock at the requested quantity. If stock has changed, the retailer is shown a clear error listing affected items.

---

## 4. Order Placement Module

### FR-ORD-01 — Place Order
- Retailer submits the cart as an order.
- Order status after placement: `pending_review`.
- Retailer receives on-screen confirmation with an order ID and expected processing time (shown as a fixed message; actual SLA is TBD — flagged as an assumption).

### FR-ORD-02 — Order Record
- Each order stores: retailer, timestamp, order lines (SKU, qty, unit price, scheme applied, line total), gross total, net total, status, and optional remarks from the retailer.

### FR-ORD-03 — Retailer Order History
- Retailers can view their own past orders with status and totals.
- Order detail shows individual line items.
- Retailers cannot see other retailers' orders.

### FR-ORD-04 — Order Cancellation by Retailer
- A retailer may cancel an order only while it is in `pending_review` status.
- Once an Order Desk user changes the status, cancellation is locked.

---

## 5. AI-Powered Order Capture Module

### FR-AI-01 — Message Input
- The AI Order Capture screen accepts a free-text input (Hindi, English, or mixed Hinglish).
- Input can be typed or pasted; voice input is out of scope for MVP.

### FR-AI-02 — AI Draft Generation
- The backend sends the raw message, the product catalogue, and retailer alias data to the Gemini API.
- The Gemini API returns a structured JSON draft (see `07-ai-order-extraction.md` for schema).
- The backend validates this JSON with Pydantic before returning it to the frontend.
- The AI **never** places an order directly; it only produces a draft.

### FR-AI-03 — Confidence and Ambiguity Handling
- Each extracted line item carries a `match_status` field: `confirmed`, `ambiguous`, or `unmatched`.
- Each line also carries a qualitative `confidence_level`: `"high"`, `"medium"`, or `"low"`. No numeric percentages are fabricated.
- `confirmed` with `"high"`: Alias match or exact SKU/name match. Auto-accepted.
- `confirmed` with `"medium"`: Single unambiguous substring match. Auto-accepted.
- `confirmed` with `"low"`: Weak fuzzy match. Must require explicit confirmation before sending to cart.
- `ambiguous`: The AI identified multiple possible products — at most **2 alternatives** are shown to the retailer for selection.
- `unmatched`: No recognisable product was found — the retailer must manually search and add from catalogue.
- AI prompt context includes active catalogue, retailer-specific aliases, and the retailer's recent purchase history (last 90 days SKUs).

### FR-AI-04 — Quantity Ambiguity
- If the extracted message contains a quantity that could be interpreted as either cases or pieces (e.g., "2 biscuit"), the system must flag it and ask the retailer to confirm the unit before proceeding.
- The draft line is marked `unit_unclear` and blocked from proceeding until resolved.

### FR-AI-05 — Draft to Cart
- The retailer reviews and edits the AI draft.
- Once all lines are `confirmed` and no `unit_unclear` flags remain, the retailer can send the draft to their cart in one action.
- Out-of-stock items extracted by AI are flagged and cannot be sent to cart.
- Free-goods schemes (e.g., Buy 10 Get 1 Free) calculate 10 paid cases + 1 physical free case (`qty_fulfilment = 11`), without deducting the free goods' value from payable amount.

### FR-AI-06 — Retailer Alias Storage & Corrections
- When the retailer confirms an ambiguous or unmatched product, the mapping (raw term → SKU) is saved as a retailer-specific alias with `source = "retailer"`.
- When Order Desk corrects a product match on a submitted order, the retailer's original `raw_fragment` is saved against the corrected SKU as a retailer alias with `source = "desk"`.
- Future AI calls for the same retailer prioritise alias matches before generic product search.

---

## 6. Order Desk Module

### FR-DESK-01 — Order Queue
- Order Desk sees all orders in `pending_review` status across all retailers.
- Orders are listed in chronological order, oldest first.

### FR-DESK-02 — Order Review
- Order Desk can open an order and view all line items, prices, scheme benefits, and retailer remarks.
- Order Desk can edit quantities within available stock limits.
- Order Desk can remove line items.
- Order Desk can add new line items from the product catalogue.
- Order Desk can correct a product match on an order line (`POST /orders/{id}/lines/{lid}/correct-product`), which updates the order and automatically saves the retailer alias.

### FR-DESK-03 — Order Approval & Atomic Stock Deduction
- Order Desk can mark an order as `approved`.
- On approval, the backend performs **atomic inventory revalidation**: verifies stock for all items at `qty_fulfilment` (accounting for free cases) within the approval transaction and deducts stock.
- If any item has insufficient stock at approval time, approval is rejected with an error.

### FR-DESK-04 — Order Rejection
- Order Desk can reject an order with a mandatory rejection reason.
- Rejected orders appear in the retailer's history with the reason displayed.

### FR-DESK-05 — Tally CSV Export
- Order Desk can export any single approved order or a batch of approved orders as a configurable CSV file compatible with Tally import workflows.
- Contains separate columns for paid quantity, free quantity, fulfilment quantity, gross amount, scheme benefit value, discount amount, and net payable.
- Tax columns are left blank because GST treatment is unconfirmed.
- Format is generic and configurable; exact client Tally Prime column format remains an open question.

### FR-DESK-06 — Order Search and Filter
- Order Desk can search orders by: retailer name or mobile, order ID, date range, status.

---

## 7. Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-01 | API response time < 500 ms for catalogue and cart endpoints under normal load. |
| NFR-02 | AI order extraction response time < 10 s (Gemini API latency included). |
| NFR-03 | All API responses use JSON; errors follow a consistent error envelope (`{ "detail": ..., "code": ... }`). |
| NFR-04 | Frontend renders correctly on Chrome (latest) and Safari (latest) on mobile. |
| NFR-05 | Retailer-facing UI supports both Hindi and English. Language toggle available in header. |
| NFR-06 | Interactive touch targets on retailer UI must be at least 48 × 48 px. |
| NFR-07 | Low-network resilience: page payloads under 200 KB initial JS gzip, pagination max 20 items, resilient against 3G/poor 4G. |
| NFR-08 | All sensitive data in transit is encrypted via HTTPS (TLS 1.2 minimum). |
| NFR-09 | JWT secrets must not be hard-coded; they must be loaded from environment variables. |
| NFR-10 | No production credentials or secrets in the repository. |
| NFR-11 | Backend must log every order-state transition with actor, timestamp, and before/after status. |

