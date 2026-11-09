# 12 — Acceptance Criteria for Every Core Feature

> Format: **GIVEN** (precondition) / **WHEN** (action) / **THEN** (expected outcome)  
> These are the conditions that must pass before a feature is considered complete.

---

## AC-AUTH — Authentication

### AC-AUTH-01 — Retailer OTP Request
**GIVEN** a valid Indian mobile number registered in the system  
**WHEN** `POST /auth/retailer/request-otp` is called  
**THEN** the response is `200 OK` with `{ "message": "OTP sent", "expires_in_seconds": 600 }`  
AND an OTP record is created in the database  
AND the OTP is hashed before storage (raw OTP is not stored)

### AC-AUTH-02 — Retailer OTP Request — Unknown Mobile
**GIVEN** a mobile number not registered in the system  
**WHEN** `POST /auth/retailer/request-otp` is called  
**THEN** the response is `404 Not Found` (do not create an OTP for a non-existent retailer)

### AC-AUTH-03 — Retailer OTP Verification — Success
**GIVEN** a valid, unexpired OTP for a registered retailer  
**WHEN** `POST /auth/retailer/verify-otp` is called with the correct OTP  
**THEN** the response is `200 OK` with an `access_token`  
AND an `HttpOnly` cookie named `refresh_token` is set  
AND the OTP record is marked `used = True`

### AC-AUTH-04 — Retailer OTP Verification — Wrong Code
**GIVEN** a valid, unexpired OTP  
**WHEN** the wrong OTP code is submitted  
**THEN** the response is `401 Unauthorized`  
AND the `attempts` counter on the OTP record increments by 1

### AC-AUTH-05 — OTP Lockout
**GIVEN** an OTP record with `attempts = 4`  
**WHEN** a 5th incorrect OTP is submitted  
**THEN** the response is `423 Locked`  
AND any subsequent attempt (even with the correct OTP) also returns `423`

### AC-AUTH-06 — Expired OTP
**GIVEN** an OTP record where `expires_at` is in the past  
**WHEN** the correct OTP code is submitted  
**THEN** the response is `401 Unauthorized` (expired, not locked)

### AC-AUTH-07 — Order Desk Login — Success
**GIVEN** valid email + password for an active Order Desk user  
**WHEN** `POST /auth/desk/login` is called  
**THEN** the response is `200 OK` with an `access_token` whose JWT `role` claim is `order_desk`

### AC-AUTH-08 — Token Refresh
**GIVEN** a valid, non-blocklisted refresh token cookie  
**WHEN** `POST /auth/refresh` is called  
**THEN** a new `access_token` is returned  
AND the old refresh token's JTI is added to the blocklist  
AND a new refresh token cookie is set

### AC-AUTH-09 — Logout Invalidation
**GIVEN** an active refresh token  
**WHEN** `POST /auth/logout` is called  
AND then `POST /auth/refresh` is called with the same old token  
**THEN** the second call returns `401 Unauthorized`

---

## AC-CAT — Product Catalogue

### AC-CAT-01 — Product Listing Requires Auth
**GIVEN** no Authorization header  
**WHEN** `GET /catalogue/products` is called  
**THEN** the response is `401 Unauthorized`

### AC-CAT-02 — Product Listing Returns All Active Products
**GIVEN** 3 active products are seeded  
**WHEN** `GET /catalogue/products` is called by an authenticated retailer  
**THEN** all 3 products are returned  
AND each product includes: `sku`, `name`, `dealer_price_per_case`, `stock_cases`, `stock_status`, and `active_scheme` (if applicable)

### AC-CAT-03 — Stock Status Labels
**GIVEN** SKU-TE-250 has `stock_cases = 0`  
AND SKU-BS-075 has `stock_cases = 340`  
AND a product X has `stock_cases = 7`  
**WHEN** the catalogue is fetched  
**THEN** SKU-TE-250 has `stock_status = "out_of_stock"`  
AND SKU-BS-075 has `stock_status = "in_stock"`  
AND product X has `stock_status = "low_stock"`

### AC-CAT-04 — Search Filters by Name
**GIVEN** 3 products seeded  
**WHEN** `GET /catalogue/products?q=biscuit` is called  
**THEN** only SKU-BS-075 is returned

### AC-CAT-05 — In-Stock Filter
**GIVEN** SKU-TE-250 has `stock_cases = 0`  
**WHEN** `GET /catalogue/products?in_stock=true` is called  
**THEN** SKU-TE-250 is not in the response  
AND the other 2 products are present

### AC-CAT-06 — Scheme Shown on Product
**GIVEN** SKU-BS-075 has an active Buy 10 Get 1 Free scheme  
**WHEN** the product detail is fetched  
**THEN** `active_scheme.type = "BUY_N_GET_M_FREE"`, `active_scheme.min_qty = 10`, `active_scheme.free_qty = 1`

---

## AC-CART — Shopping Cart

### AC-CART-01 — Retailer Can Add In-Stock Product
**GIVEN** an authenticated retailer and an in-stock product  
**WHEN** `POST /cart/lines` with `{ product_id, qty_cases: 5 }`  
**THEN** the response is `200 OK` with the updated cart  
AND the line appears with correct `gross_line_total = unit_price × 5`

### AC-CART-02 — Out-of-Stock Blocked
**GIVEN** SKU-TE-250 has `stock_cases = 0`  
**WHEN** `POST /cart/lines` with SKU-TE-250  
**THEN** the response is `422 Unprocessable Entity`  
AND the cart is unchanged

### AC-CART-03 — Quantity Exceeds Stock Blocked
**GIVEN** a product with `stock_cases = 85`  
**WHEN** `POST /cart/lines` with `qty_cases: 100`  
**THEN** the response is `409 Conflict`

### AC-CART-04 — Free-Goods Scheme Applied at Threshold
**GIVEN** SKU-BS-075 (Buy 10 Get 1 Free, `dealer_price_per_pack = ₹8.10`, `case_qty = 96`)  
**AND** `unit_price_per_case = 8.10 × 96 = ₹777.60` (assumption A-1)  
**WHEN** 10 cases are added to cart  
**THEN** `qty_free = 1`, `qty_fulfilment = 11`  
AND `gross_line_total = "7776.00"` (10 paid cases × ₹777.60)  
AND `net_line_total = "7776.00"` (retailer pays for 10 cases — no monetary deduction)  
AND `benefit_value = "777.60"` (informational: value of 1 free case)

### AC-CART-04b — Free-Goods Scheme NOT Applied Below Threshold
**GIVEN** SKU-BS-075 (Buy 10 Get 1 Free)  
**WHEN** 9 cases are added to cart  
**THEN** `qty_free = 0`, `qty_fulfilment = 9`  
AND `net_line_total = gross_line_total`  
AND `benefit_value = "0.00"`

### AC-CART-06 — Order Desk Cannot Access Cart
**GIVEN** an authenticated Order Desk user  
**WHEN** `GET /cart` is called  
**THEN** the response is `403 Forbidden`

### AC-CART-05 — Discount Scheme Applied
**GIVEN** SKU-DT-1KG (3% off ≥ 5 cases, `dealer_price_per_pack = ₹101.50`, `case_qty = 20`)  
**AND** `unit_price_per_case = 101.50 × 20 = ₹2,030.00` (assumption A-1)  
**WHEN** 5 cases are added to cart  
**THEN** `gross_line_total = "10150.00"`  
AND `discount_amount = "304.50"` (3% of 10,150, rounded half up)  
AND `net_line_total = "9845.50"`

### AC-CART-08 — Backend Recalculates on Every Mutation
**GIVEN** a cart with 10 cases of biscuit (free-goods scheme: `qty_free = 1`, `qty_fulfilment = 11`)  
**WHEN** quantity is updated to 9 cases  
**THEN** `qty_free = 0`, `qty_fulfilment = 9`, `benefit_value = "0.00"`, and `net_line_total = gross_line_total`

### AC-CART-09 — Stock Deducted by Fulfilment Quantity on Approval
**GIVEN** an approved order with 10 paid cases of biscuit + 1 free case (qty_fulfilment = 11)  
**WHEN** Order Desk approves the order (status → `approved`)  
**THEN** `products.stock_cases` is decremented by `11` (not 10)  
AND if stock was 10 or fewer, the approval is blocked with a conflict error

---

## AC-ORD — Order Placement and Management

### AC-ORD-01 — Place Order from Cart
**GIVEN** a retailer with 2 items in cart  
**WHEN** `POST /orders` with optional remarks  
**THEN** response is `201 Created` with `order_id` and `status = "pending_review"`  
AND the cart is emptied  
AND prices are snapshotted in `order_lines`

### AC-ORD-02 — Empty Cart Cannot be Placed
**GIVEN** a retailer with an empty cart  
**WHEN** `POST /orders`  
**THEN** response is `422 Unprocessable Entity`

### AC-ORD-03 — Retailer Cannot See Other Retailer's Order
**GIVEN** an order placed by Retailer A  
**WHEN** Retailer B calls `GET /orders/{order_id}` with that order ID  
**THEN** response is `403 Forbidden`

### AC-ORD-04 — Order Desk Sees All Orders
**GIVEN** orders from Retailer A and Retailer B  
**WHEN** Order Desk calls `GET /orders`  
**THEN** both orders appear in the response

### AC-ORD-05 — Desk Approval
**GIVEN** an order in `pending_review`  
**WHEN** Order Desk calls `PATCH /orders/:id/status` with `{ "status": "approved" }`  
**THEN** order status is `approved`  
AND the audit log has a new entry with `actor_type = "order_desk"` and `to_status = "approved"`

### AC-ORD-06 — Rejection Requires Note
**GIVEN** an order in `pending_review`  
**WHEN** Order Desk calls `PATCH /orders/:id/status` with `{ "status": "rejected" }` and no `note`  
**THEN** response is `422 Unprocessable Entity`

### AC-ORD-07 — Retailer Cancels Pending Order
**GIVEN** an order in `pending_review` owned by the authenticated retailer  
**WHEN** `POST /orders/:id/cancel`  
**THEN** status is `cancelled`

### AC-ORD-08 — Retailer Cannot Cancel Approved Order
**GIVEN** an order in `approved` status  
**WHEN** `POST /orders/:id/cancel`  
**THEN** response is `422 Unprocessable Entity`

### AC-ORD-09 — Desk Edits Line Quantity — Totals Recalculated
**GIVEN** an approved-pending order with 10 cases biscuit (scheme saving ₹8.10)  
**WHEN** Order Desk updates the line to `qty_cases = 20`  
**THEN** the response shows updated `scheme_saving` (₹16.20 for 2 sets) and correct `net_total`

---

## AC-AI — AI Order Capture

### AC-AI-01 — Confirmed Match Returned
**GIVEN** the sample raw text with "biscuit chhota" and a seeded catalogue  
**WHEN** `POST /ai/extract` is called  
**THEN** the biscuit line has `match_status = "confirmed"` and `product.sku = "SKU-BS-075"`

### AC-AI-02 — Out-of-Stock Product Flagged
**GIVEN** SKU-TE-250 has `stock_cases = 0`  
**WHEN** the raw text includes "chai patti 250 wala 1 peti"  
**THEN** the tea line has `warning = "OUT_OF_STOCK"` in the draft  
AND the line is included in the draft (not silently dropped) so the retailer sees the warning

### AC-AI-03 — Ambiguous Match Returns Alternatives
**GIVEN** multiple products matching a vague term  
**WHEN** AI extraction returns `match_status = "ambiguous"`  
**THEN** up to 3 alternative products are listed for the retailer to choose from

### AC-AI-04 — Unit Unclear Must Be Resolved
**GIVEN** a quantity with `qty_unit = "piece"` or `qty_unit = "unknown"`  
**WHEN** the draft is rendered  
**THEN** that line is marked `unit_unclear = true`  
AND the retailer cannot send the draft to cart until they resolve it

### AC-AI-05 — AI Never Places Order
**GIVEN** any raw text input  
**WHEN** `POST /ai/extract` is called  
**THEN** the response always returns a draft object  
AND no order is created in the database  
AND no cart is modified

### AC-AI-06 — Alias Saved on Confirmation
**GIVEN** an ambiguous draft line  
**WHEN** the retailer selects a specific product from the alternatives  
AND sends the draft to cart  
**THEN** a `retailer_alias` record is created mapping the retailer's raw term to the selected SKU  
AND future AI extraction calls for the same retailer resolve this term as `confirmed`

### AC-AI-07 — Gemini Unavailable Returns 503
**GIVEN** the Gemini API is unreachable (mocked in tests)  
**WHEN** `POST /ai/extract` is called  
**THEN** the response is `503 Service Unavailable` with `code = "AI_UNAVAILABLE"`

---

## AC-EXPORT — Tally CSV Export

### AC-EXPORT-01 — Approved Order Exports CSV
**GIVEN** an order in `approved` status  
**WHEN** Order Desk calls `GET /export/orders/:id/tally-csv`  
**THEN** the response is a `text/csv` file  
AND the CSV contains one row per order line  
AND each row contains: retailer name, SKU, product name, qty in cases, unit price, gross amount, scheme saving, net amount, order date

### AC-EXPORT-02 — Non-Approved Order Cannot Be Exported
**GIVEN** an order in `pending_review` status  
**WHEN** `GET /export/orders/:id/tally-csv` is called  
**THEN** the response is `422 Unprocessable Entity`

### AC-EXPORT-03 — Retailer Cannot Export
**GIVEN** an authenticated retailer  
**WHEN** any export endpoint is called  
**THEN** the response is `403 Forbidden`

### AC-EXPORT-04 — Batch Export Contains All Requested Orders
**GIVEN** 3 approved orders with IDs [A, B, C]  
**WHEN** `GET /export/orders/tally-csv-batch?order_ids=A,B,C` is called  
**THEN** the CSV contains all order lines from all 3 orders  
AND each row is identifiable by its `order_id` or `party_ledger`

---

## AC-SEC — Security

### AC-SEC-01 — Unauthenticated Requests Rejected
**GIVEN** no Authorization header  
**WHEN** any protected endpoint is called  
**THEN** the response is `401 Unauthorized`

### AC-SEC-02 — Cross-Role Access Blocked
**GIVEN** a valid retailer JWT  
**WHEN** any Order Desk-only endpoint is called  
**THEN** the response is `403 Forbidden`

### AC-SEC-03 — Expired Access Token Rejected
**GIVEN** an access token that has passed its `exp` claim  
**WHEN** any protected endpoint is called with that token  
**THEN** the response is `401 Unauthorized`

### AC-SEC-04 — Blocklisted Refresh Token Rejected
**GIVEN** a refresh token whose JTI is in the blocklist  
**WHEN** `POST /auth/refresh` is called  
**THEN** the response is `401 Unauthorized`

### AC-SEC-05 — Raw OTP Not Stored
**GIVEN** an OTP request is made  
**WHEN** the `otp_records` table is inspected  
**THEN** only the bcrypt hash of the OTP is present, never the raw 6-digit value

