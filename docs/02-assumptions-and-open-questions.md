# 02 — Assumptions and Open Business Questions

> Every item in this document must be **confirmed or rejected by the client** before the relevant feature is implemented.  
> Items marked **[ASSUMED]** mean a decision has been made unilaterally to unblock development; it can be overridden.  
> Items marked **[OPEN]** mean no decision has been made; the feature is blocked until answered.

---

## Section A — Pricing and Financial

### A-1 [ASSUMED] — Dealer Price Unit
**Decision:** The supplied prices (`₹8.10`, `₹101.50`, `₹118.00`) are treated as the price **per retail pack** for the demo phase only.  
**Derivation:** `dealer_price_per_case = dealer_price_per_pack × case_qty`  
Example: Glucose Biscuit 75g at ₹8.10/pack × 96 packs/case = ₹777.60/case.  
**Impact:** This assumption changes every price calculation and cart total. If the client confirms prices are already per-case, the derivation step must be removed.  
**Label:** `dealer_price_per_pack` stored in the database. `price_unit` field stores `"per_pack"` as the current assumption. This is an **unconfirmed assumption** and must be verified before go-live.  
**Blocker:** Critical. Must be confirmed before production launch.

### A-2 [OPEN] — GST Treatment
**Question:** Are dealer prices inclusive or exclusive of GST? What GST rate applies to each product category?  
**Decision:** GST rates and inclusion status are **not provided**. The system will **not calculate, display, or export any GST amounts** until the client confirms the tax treatment.  
**Implementation:** A `gst_rate_pct` field (nullable) will be stored on products. When null, the UI shows "Tax: Unspecified" and the Tally CSV export column `GSTAmount` is left blank.  
**Impact:** Tally CSV will be incomplete for GST columns until this is resolved. Do not invent or assume GST rates.  
**Blocker:** Critical for Tally export. All GST-related columns are blocked until confirmed.

### A-3 [OPEN] — Credit Limit Enforcement
**Question:** Does a retailer have a credit limit? If so, should the system block order placement when credit is exceeded, or only warn?  
**Impact:** Requires a credit_limit field on retailers and a check at checkout.  
**Blocker:** Medium. Can be implemented as a warn-only flag without blocking logic initially.

### A-4 [OPEN] — Multiple Price Tiers
**Question:** Do different retailers get different dealer prices (tiered pricing), or is there a single dealer price for all?  
**Assumed:** Single dealer price for all retailers in this deployment.  
**Impact:** If tiers exist, the product pricing model changes significantly.

### A-5 [OPEN] — Currency and Locale
**Question:** All amounts are in Indian Rupees (INR)? No multi-currency requirement?  
**Assumed:** INR only.

---

## Section B — Ordering and Inventory

### B-1 [OPEN] — Piece-Level vs. Case-Level Ordering
**Question:** Can retailers order individual pieces, or only full cases?  
**Assumed:** Case-level only for MVP. Piece-level adds significant complexity (partial-case stock tracking, different pricing).  
**Impact:** If pieces are needed, the quantity model, scheme engine, and AI extraction all need rework.

### B-2 [ASSUMED] — Stock Reservation Timing
**Decision:** Stock is deducted from `stock_cases` **only after Order Desk approval**, not on order placement.  
**Implementation:** At the moment of approval, the backend performs an **atomic inventory revalidation**: it checks that `stock_cases >= ordered_qty` for every line in the same database transaction that decrements stock. If any line fails the check, the approval is rejected with a conflict error listing the affected products.  
**Rationale:** Prevents phantom reservations from unapproved orders. Avoids the scenario where Order Desk rejects an order but the stock was already decremented.  
**Risk acknowledged:** Two simultaneous approvals for the same low-stock item could race. The atomic check inside a serializable transaction prevents double-deduction.

### B-3 [OPEN] — Order Minimum Value or Quantity
**Question:** Is there a minimum order value or minimum number of cases per order?  
**Assumed:** No minimum enforced at MVP.

### B-4 [OPEN] — Back-Order / Waitlist
**Question:** If a product is out of stock, can retailers place a back-order to be fulfilled later?  
**Assumed:** No back-orders at MVP. Out-of-stock items are blocked.

### B-5 [OPEN] — Return / Replacement Orders
**Question:** Is there a return merchandise (RMA) workflow needed?  
**Assumed:** Out of scope for MVP.

### B-6 [OPEN] — Delivery Date
**Question:** Does an order carry a requested delivery date? Is there a delivery slot system?  
**Assumed:** No delivery scheduling at MVP; order placement date is the only date recorded.

---

## Section C — AI and Message Parsing

### C-1 [OPEN] — Supported Languages
**Question:** Is Hindi-in-Devanagari script also expected, or only Romanised Hindi (Hinglish)?  
**Assumed:** Both Devanagari and Roman Hindi, plus English. Gemini 1.5 Pro handles both.

### C-2 [OPEN] — Voice Input
**Question:** Should the AI capture screen support voice input (speech-to-text)?  
**Assumed:** Out of scope for MVP. Text input only.

### C-3 [ASSUMED] — AI Confidence Representation (No Numeric Score)
**Decision:** No numeric confidence percentage is computed or displayed. This avoids fabricating a metric without validated calibration.  
**Implementation:** Each extracted line carries a qualitative `confidence_level` field with three values:  
- `"high"` — Alias match or exact SKU/name match.  
- `"medium"` — Single unambiguous fuzzy/ilike match.  
- `"low"` — Weak fuzzy match requiring explicit retailer confirmation before cart addition.  
Lines with `confidence_level = "low"` are treated as requiring confirmation even if `match_status = "confirmed"` by fuzzy logic; they are presented to the retailer like `ambiguous` lines.

### C-6 [ASSUMED] — Maximum Alternatives Shown
**Decision:** At most **2 alternative SKUs** are shown for ambiguous matches (down from 3 in previous planning). This keeps the mobile UI uncluttered.

### C-7 [ASSUMED] — Purchase History in AI Context
**Decision:** The retailer's last 90 days of approved order lines are included as a context hint in the Gemini prompt. This improves match quality for repeat products without sending full order data.  
**Format:** `"Retailer recently ordered: Glucose Biscuit 75g (SKU-BS-075), Detergent Powder 1kg (SKU-DT-1KG)"`  
**Privacy:** Only SKUs and product names are sent; no quantities, prices, or order IDs.

### C-8 [ASSUMED] — Order Desk Alias Corrections
**Decision:** When Order Desk corrects a product match on a submitted order, the system saves the **retailer's original `raw_fragment`** from the AI draft against the corrected SKU as a retailer alias. This requires the `raw_fragment` to be persisted on the `order_lines` table so it is available to the Order Desk at review time.  
**API:** A new `POST /api/v1/orders/{order_id}/lines/{line_id}/correct-product` endpoint allows Order Desk to remap a line to a different SKU and optionally trigger alias saving.

### C-4 [OPEN] — Alias Scope
**Question:** Should retailer aliases be shared across all retailers (global) or private per retailer?  
**Assumed:** Aliases are private per retailer. A retailer's shorthand (e.g., "chhota biscuit" → SKU-BS-075) is their own and not shared.

### C-5 [OPEN] — Multi-Message / Conversation Threading
**Question:** A single delivery might be built from multiple WhatsApp messages sent in sequence. Should the system support merging multiple messages into one draft?  
**Assumed:** Single-message input only at MVP. Each AI capture call is stateless.

---

## Section D — Tally Integration

### D-1 [OPEN] — Tally CSV Column Specification
**Question:** What exact columns, header names, date format, and encoding does the client's Tally Prime version expect for voucher import?  
**Blocker:** Cannot finalise the CSV export feature without this.  
**Mitigation:** A **generic configurable CSV export** will be built with clearly named columns (see doc 12). Column mappings can be reconfigured per-deployment once the Tally spec is known. The export format remains unconfirmed and is explicitly labelled as such in the UI and in export file headers.

### D-2 [OPEN] — Tally Party Name Mapping
**Question:** How is a retailer mapped to a Party Ledger in Tally? By mobile number? By a Tally-assigned Ledger Name stored in DukaanFlow?  
**Assumed:** A `tally_ledger_name` field will be stored on each retailer record; initially populated manually.

### D-3 [OPEN] — Tally Auto-Push vs. Manual Export
**Question:** Is manual CSV export (download and import) acceptable, or is a live API push to Tally required?  
**Assumed:** Manual CSV export only for MVP.

---

## Section E — Users and Access

### E-1 [ASSUMED] — OTP Security and Lockout Rule
**Decision (reconciled):** The following single consistent rule applies:  
- An OTP is valid for **10 minutes**.  
- After **5 consecutive incorrect OTP attempts** on the same OTP record, that OTP record is marked `locked = True`.  
- A locked OTP cannot be verified even with the correct code; the retailer must request a new OTP.  
- There is **no separate 30-minute account lockout** at this stage. The lockout is per-OTP, not per-account. Requesting a new OTP resets the attempt counter.  
- Rate limiting on OTP requests (max 3/mobile/10 min) prevents OTP farming.  
- For the demo phase, OTP is a fixed code (`123456`) or printed in the server console. **This must be replaced with a real SMS gateway before production.**

### E-2 [OPEN] — Number of Order Desk Users
**Question:** How many Order Desk staff will use the system? Do they need individual accounts with different permissions, or is a single shared login acceptable?  
**Assumed:** Multiple individual accounts, all with the same `order_desk` role.

### E-3 [OPEN] — Retailer Onboarding
**Question:** Who creates retailer accounts — an admin user, a salesman, or self-registration?  
**Assumed:** Retailer accounts are created by Order Desk / Admin in an internal panel. Self-registration is out of scope.

### E-4 [OPEN] — Admin Role
**Question:** Is a third role (Admin/Super Admin) needed for user management and system configuration?  
**Assumed:** Admin functions (creating retailers, managing catalogue) are handled through direct database management or a minimal admin panel built in Day 6–7. Full admin UI is deferred.

### E-5 [OPEN] — Session Concurrency
**Question:** Should a retailer be able to be logged in on multiple devices simultaneously?  
**Assumed:** Allowed. No single-session enforcement at MVP.

---

## Section F — Technical

### F-1 [ASSUMED] — Deployment Architecture
**Local Development:** Docker Compose (PostgreSQL + FastAPI + Vite dev server). This is the working local setup.  
**Proposed Production Stack:**
- **Frontend:** Vercel (static SPA deployment)
- **Backend:** Render (FastAPI web service, Python 3.11)
- **Database:** Render Managed PostgreSQL or Supabase

**Refresh Cookie Cross-Origin Issue:**  
`HttpOnly` cookies set by the backend are blocked by browsers when the frontend origin (`vercel.app`) differs from the API origin (`render.com`). This must be resolved by one of:  
1. **Same-origin API proxy (recommended):** Configure a Vercel Rewrite rule so `/api/*` proxies to the Render backend. The browser sees one origin; cookies work normally.  
2. **Custom domain:** Point a single domain (e.g., `api.dukaanflow.in`) to Render and serve the frontend from `www.dukaanflow.in` with `SameSite=None; Secure` cookies and appropriate CORS headers.  

Option 1 is preferred for MVP simplicity. Option 2 requires domain ownership and is recommended before go-live.  

**The previous "single Linux VM + Nginx" deployment design is superseded** by this Vercel + Render stack. Docker Compose remains for local development only.

### F-2 [OPEN] — Existing Data Migration
**Question:** Is there existing product, retailer, or order data in Tally or spreadsheets that must be migrated?  
**Assumed:** Manual data entry for the pilot. A CSV import tool for products and retailers will be built in a later phase.

### F-3 [ASSUMED] — Gemini Model Version
**Decision:** Gemini 1.5 Flash is used for order extraction (cost/speed balance). Can be switched to Gemini 1.5 Pro if extraction quality is insufficient.

### F-4 [OPEN] — Rate Limiting on AI Endpoint
**Question:** Is there a Gemini API quota concern? How many AI extraction calls per day are expected?  
**Assumed:** At 1,800 retailers making at most 1 order per day, the peak is ~1,800 API calls/day. This is well within Gemini free-tier limits.

