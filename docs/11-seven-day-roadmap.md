# 11 — Seven-Day Development Roadmap

> **Scope:** One developer, 6–8 productive hours per day.  
> Each day ends with a **working, testable vertical slice** — not just scaffolding.  
> Items marked 🔴 are **blockers** that require a client decision before full implementation.

---

## Day 1 — Project Foundation and Auth

**Goal:** A running FastAPI + PostgreSQL backend with working authentication for both user types, and a bare React app that can log in.

### Backend Tasks
- [ ] Initialise project structure (`pyproject.toml`, `requirements.txt`, folder layout)
- [ ] Configure `pydantic-settings` for environment variable loading (`core/config.py`)
- [ ] Set up SQLAlchemy with async-ready session factory (`core/database.py`)
- [ ] Write Alembic base migration + initial schema for `retailers`, `order_desk_users`, `otp_records`, `refresh_token_blocklist`
- [ ] Implement `AuthService`: OTP generation (demo mode: fixed `123456`), bcrypt OTP hashing, JWT issue/refresh/revoke
- [ ] Implement auth router (`/auth/retailer/request-otp`, `/auth/retailer/verify-otp`, `/auth/desk/login`, `/auth/refresh`, `/auth/logout`)
- [ ] Implement role-based dependency `get_current_user` and `require_role()`
- [ ] Write auth integration tests (all pass)
- [ ] Seed script: 2 test retailers, 1 Order Desk user

### Frontend Tasks
- [ ] Initialise Vite + React + TypeScript + Tailwind
- [ ] `AuthContext` with token storage strategy (memory + HttpOnly cookie)
- [ ] Axios client with automatic token refresh interceptor
- [ ] Login page (mobile OTP flow + email/password toggle)
- [ ] OTP verify page with countdown
- [ ] Protected route guards (`<RetailerRoute>`, `<DeskRoute>`)
- [ ] Retailer Home placeholder screen (shows logged-in name, logout button)
- [ ] Desk Dashboard placeholder screen

**Day 1 Done When:** A retailer can log in with OTP and see their home screen. An Order Desk user can log in with email/password.

---

## Day 2 — Product Catalogue

**Goal:** Retailers can browse, search, and filter the product catalogue with correct scheme display.

### Backend Tasks
- [ ] Alembic migration: `products` and `schemes` tables
- [ ] `CatalogueService`: product listing with pagination, search (ilike), in-stock filter, category filter
- [ ] `SchemeEngine`: implement `BUY_N_GET_M_FREE` and `DISCOUNT_ON_MIN_QTY` calculation
- [ ] Catalogue router: `GET /catalogue/products`, `GET /catalogue/products/:sku`
- [ ] Seed the 3 sample products + 2 sample schemes
- [ ] Write scheme engine unit tests (all pass)
- [ ] Write catalogue integration tests (all pass)

### Frontend Tasks
- [ ] `ProductCard` component (name, price, stock status, scheme badge)
- [ ] Catalogue page with grid layout, search input, in-stock toggle
- [ ] Product detail page
- [ ] `SchemeBadge` component
- [ ] Vitest tests for `ProductCard`

**Day 2 Done When:** Retailer can browse all 3 products, search for "biscuit", see the scheme badge on SKU-BS-075, and see SKU-TE-250 shown as "Out of Stock".

---

## Day 3 — Shopping Cart

**Goal:** Retailers can build a cart, see scheme-adjusted totals, and the backend calculates everything.

### Backend Tasks
- [ ] Alembic migration: `carts` and `cart_lines` tables
- [ ] `CartService`: add/update/remove lines, scheme recalculation on every mutation, stock validation
- [ ] Cart router: all 5 cart endpoints
- [ ] `GET /cart` returns full computed cart (not just raw DB rows)
- [ ] Write cart integration tests (all pass, including scheme edge cases)

### Frontend Tasks
- [ ] `useCart` hook wrapping all cart API calls
- [ ] Cart page with line items, qty controls, scheme savings, order summary
- [ ] `CartLine` component
- [ ] Add to Cart button on `ProductCard` and `ProductDetail` (with stock check feedback)
- [ ] Cart item count badge in nav
- [ ] Empty cart state
- [ ] Vitest tests for `CartLine`

**Day 3 Done When:** Retailer adds 10 cases of biscuit, sees "1 case free — ₹8.10 saving", adds 2 cases detergent (no scheme), sees correct net total.

---

## Day 4 — Order Placement and Retailer Order History

**Goal:** Retailer can place an order. Order Desk can see the queue and change status.

### Backend Tasks
- [ ] Alembic migration: `orders`, `order_lines`, `order_audit_log` tables
- [ ] `OrderService`: create order from cart (snapshot prices), status transitions with guard logic, audit logging
- [ ] Orders router: `POST /orders`, `GET /orders`, `GET /orders/:id`, `PATCH /orders/:id/status`, `POST /orders/:id/cancel`
- [ ] Stock validation at order placement
- [ ] Write order integration tests (all status transitions, retailer isolation, audit log)

### Frontend Tasks
- [ ] Place Order flow on Cart page (remarks input, confirm button, success screen)
- [ ] Retailer Order History page (paginated list, status chips)
- [ ] Retailer Order Detail page (line items, totals, audit trail, cancel button)
- [ ] `OrderStatusChip` component
- [ ] Desk Order Queue page (all orders, oldest first, filters)
- [ ] Desk Order Review page (order detail, approve/reject controls)

**Day 4 Done When:** Retailer places an order → it appears in Order Desk queue → desk approves it → retailer sees status change to "approved".

---

## Day 5 — AI Order Capture

**Goal:** Retailer pastes a WhatsApp message, sees an AI draft, resolves ambiguities, and sends confirmed items to cart.

### Backend Tasks
- [ ] Alembic migration: `retailer_aliases` table
- [ ] `AIOrderService`: build prompt, call Gemini API, parse response, resolve SKUs, check stock, return draft
- [ ] AI capture router: `POST /ai/extract`
- [ ] `POST /cart/from-ai-draft` endpoint
- [ ] Alias save logic (called when retailer confirms ambiguous/unmatched item)
- [ ] Write AI unit tests (parser, SKU resolver) with mocked Gemini
- [ ] Write AI integration tests with mocked Gemini API

### Frontend Tasks
- [ ] AI Capture input screen
- [ ] AI Draft Review screen
- [ ] `AiDraftLine` component (renders all 4 states: confirmed, ambiguous, unmatched, out-of-stock)
- [ ] `AlternativeSelector` component (shows up to 3 alternatives)
- [ ] `UnitClarifier` component (case vs. piece selector)
- [ ] Send to Cart CTA (blocked until all issues resolved)
- [ ] Vitest tests for `AiDraftLine`, `AlternativeSelector`, `UnitClarifier`

**Day 5 Done When:** The sample raw order produces the correct 3-line draft. Biscuit and detergent go to cart. Tea 250g is blocked with "Out of Stock" warning.

---

## Day 6 — Order Desk Edit Tools and Tally Export

**Goal:** Order Desk can edit order lines inline and export approved orders as Tally CSV.

### Backend Tasks
- [ ] `PATCH /orders/:id/lines/:lid` — edit line qty with recalculation
- [ ] `DELETE /orders/:id/lines/:lid` — remove a line
- [ ] `ExportService`: build Tally-compatible CSV from order data 🔴 (pending Tally column spec — build generic version first)
- [ ] Export router: `GET /export/orders/:id/tally-csv`, `GET /export/orders/tally-csv-batch`
- [ ] Write export integration tests

### Frontend Tasks
- [ ] Desk Order Review page: inline qty edit per line, remove line button
- [ ] Add line from catalogue (search modal)
- [ ] Export Preview page (CSV column preview table)
- [ ] Download CSV button
- [ ] Batch Export page (multi-select approved orders)

**Day 6 Done When:** Order Desk edits a line quantity, recalculated totals appear, approves the order, downloads a Tally CSV with all correct data columns.

---

## Day 7 — Hardening, Polish, and Deployment

**Goal:** The app is production-ready at the demo scale, deployed and working end-to-end.

### Backend Tasks
- [ ] Rate limiting middleware for AI and auth endpoints
- [ ] Blocklist cleanup job (delete expired refresh token blocklist rows)
- [ ] `GET /health` endpoint
- [ ] Error handler middleware (consistent error envelope for all 4xx/5xx)
- [ ] Structured logging (JSON format for production)
- [ ] Review all Pydantic schemas for missing constraints
- [ ] Run full test suite; fix any failing tests
- [ ] Write `Dockerfile` for backend (Render deployment)
- [ ] Write `docker-compose.yml` for local development only (db + api)
- [ ] Write `.env.example`

### Frontend Tasks
- [ ] Add loading skeletons to catalogue, cart, and order pages
- [ ] Error boundary component
- [ ] Empty state illustrations for empty cart, no orders, etc.
- [ ] Language toggle (Hindi / English) in retailer layout header
- [ ] Verify all touch targets ≥ 48 × 48 px on mobile screens
- [ ] Mobile responsiveness pass on all Retailer screens (test on 360px viewport)
- [ ] `pnpm run build` and check bundle size (target < 200 KB initial JS gzip)
- [ ] Configure `vercel.json` with `/api/*` rewrite to Render backend URL

### Documentation Tasks
- [ ] `README.md` with local setup and production deployment instructions
- [ ] `docs/` updated with any changes from implementation
- [ ] API tested end-to-end with Postman/Bruno collection

**Day 7 Done When:** Backend deploys to Render, frontend deploys to Vercel, the Vercel `/api/*` rewrite works, refresh cookie is set correctly, and the full retailer → AI capture → order placement → desk approval → CSV export journey works end-to-end in production.

---

## Priority Ordering Within Each Day

If time is tight, implement features in this order:

1. **Happy path first** — the core working flow matters more than edge cases.
2. **Backend first** — the UI can be a simple form; the business logic must be correct.
3. **Tests next** — write tests for the business logic immediately after (not at end of week).
4. **Polish last** — loading states, mobile responsiveness, and empty states come last.

---

## Deferred to Post-MVP

| Feature | Reason |
|---------|--------|
| Real SMS OTP gateway | Demo mode is sufficient for pilot |
| Self-service retailer onboarding | Currently done by Order Desk |
| Product / retailer CSV import | Manual DB seeding sufficient for pilot |
| Voice input on AI screen | Requires speech-to-text integration |
| Order-level (cross-line) schemes | No confirmed requirement |
| Credit limit hard blocking | Currently warn-only |
| Advanced admin panel | Direct DB access for pilot |
| E2E tests (Playwright) | High value, insufficient time in 7 days |
| Push notifications | No confirmed requirement |

