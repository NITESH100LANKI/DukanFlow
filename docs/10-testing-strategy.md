# 10 — Testing Strategy

## 1. Philosophy

- Tests are written to verify **business behaviour**, not implementation details.
- Every business rule (scheme calculation, role restriction, AI draft rules) must have at least one test.
- Tests run automatically in CI before any merge.
- Aim for fast feedback: the full backend test suite should finish in under 2 minutes.

---

## 2. Testing Layers

```
┌──────────────────────────────────┐
│   E2E Tests (Playwright)         │  ← Critical user journeys only (not MVP scope)
├──────────────────────────────────┤
│   Integration Tests (Pytest)     │  ← API endpoint tests with test DB
├──────────────────────────────────┤
│   Unit Tests (Pytest + Vitest)   │  ← Pure logic: scheme engine, validators, AI parser
└──────────────────────────────────┘
```

---

## 3. Backend Testing (Pytest)

### 3.1 Setup

- **Test database:** SQLite in-memory for unit tests; PostgreSQL test database for integration tests.
- **Fixtures (`conftest.py`):**
  - `db_session` — transactional SQLAlchemy session that rolls back after each test.
  - `test_client` — FastAPI `TestClient` with overridden `get_db` dependency.
  - `retailer_token` — a pre-issued JWT for a seeded test retailer.
  - `desk_token` — a pre-issued JWT for a seeded test Order Desk user.
  - `sample_products` — a fixture that seeds the three sample SKUs.
  - `sample_schemes` — a fixture that seeds the two active schemes.

### 3.2 Unit Tests

#### Scheme Engine (`tests/unit/test_scheme_engine.py`)

| Test | Description |
|------|-------------|
| `test_no_scheme_applied` | No scheme returns gross = net, saving = 0, qty_free = 0 |
| `test_buy_n_get_m_below_min` | 9 cases with Buy 10 Get 1 — no scheme applied |
| `test_buy_n_get_m_exact_min` | Exactly 10 cases — 1 free, qty_fulfilment = 11, net = gross (no deduction) |
| `test_buy_n_get_m_multiple_sets` | 25 cases — 2 sets, 2 free, qty_fulfilment = 27 |
| `test_buy_n_get_m_net_equals_gross` | Verify net_line_total == gross_line_total for free-goods (retailer pays for paid cases only) |
| `test_buy_n_get_m_benefit_value` | Verify benefit_value = free_qty × unit_price_per_case |
| `test_discount_on_min_qty_below_min` | 4 cases with 5-case min — no discount |
| `test_discount_on_min_qty_exact_min` | 5 cases — 3% applied, net < gross |
| `test_discount_rounding` | Verify ROUND_HALF_UP with awkward decimals (9.225 → 9.23) |
| `test_scheme_expired` | Scheme `valid_to` in the past — not applied |
| `test_scheme_future` | Scheme `valid_from` in the future — not applied |
| `test_scheme_inactive` | `is_active = False` — not applied |
| `test_decimal_precision` | All results have exactly 2 decimal places |
| `test_price_derivation` | `unit_price_per_case = dealer_price_per_pack × case_qty` (assumption A-1) |

#### AI Response Parser (`tests/unit/test_ai_parser.py`)

| Test | Description |
|------|-------------|
| `test_valid_json_parsed` | Well-formed Gemini JSON → valid `GeminiResponse` |
| `test_invalid_json_raises` | Malformed JSON → raises `AIParseError` |
| `test_null_product_hint` | `product_hint = null` → line marked `unmatched` |
| `test_null_qty_value` | `qty_value = null` → line marked `unit_unclear` |
| `test_unknown_qty_unit` | `qty_unit = "unknown"` → line marked `unit_unclear` |
| `test_piece_qty_unit` | `qty_unit = "piece"` → line marked `unit_unclear` |

#### SKU Resolution (`tests/unit/test_sku_resolution.py`)

| Test | Description |
|------|-------------|
| `test_alias_takes_priority` | Retailer alias resolves before name search |
| `test_exact_sku_match` | SKU-BS-075 input → confirmed match |
| `test_exact_name_match` | Exact lowercase name → confirmed |
| `test_single_fuzzy_match` | One ilike result → confirmed |
| `test_multiple_fuzzy_matches` | 2 results → ambiguous with alternatives |
| `test_no_match` | No DB match → unmatched |
| `test_alias_updated_on_remap` | Re-confirming a different product updates the alias |

### 3.3 Integration Tests (API Layer)

#### Auth (`tests/integration/test_auth.py`)

| Test | Description |
|------|-------------|
| `test_retailer_otp_request_valid_mobile` | Returns 200 and message |
| `test_retailer_otp_request_invalid_mobile` | Returns 422 |
| `test_retailer_verify_otp_success` | Returns access token + sets cookie |
| `test_retailer_verify_otp_wrong_code` | Returns 401 |
| `test_retailer_verify_otp_expired` | Returns 401 (time-mocked) |
| `test_retailer_otp_lockout_after_5_failures` | 6th attempt → 423 |
| `test_desk_login_success` | Returns access token |
| `test_desk_login_wrong_password` | Returns 401 |
| `test_refresh_token_rotation` | Old JTI blocklisted, new token issued |
| `test_logout_blocklists_jti` | Subsequent refresh with old token → 401 |

#### Catalogue (`tests/integration/test_catalogue.py`)

| Test | Description |
|------|-------------|
| `test_list_products_authenticated` | Returns paginated product list |
| `test_list_products_unauthenticated` | Returns 401 |
| `test_search_by_name` | `?q=biscuit` returns only matching products |
| `test_filter_in_stock` | `?in_stock=true` excludes SKU-TE-250 (stock=0) |
| `test_product_detail_found` | Returns full product + scheme |
| `test_product_detail_not_found` | Returns 404 |

#### Cart (`tests/integration/test_cart.py`)

| Test | Description |
|------|-------------|
| `test_empty_cart_on_first_load` | GET cart returns empty lines |
| `test_add_product_to_cart` | POST line → product in cart |
| `test_add_out_of_stock_blocked` | Adding SKU-TE-250 → 422 |
| `test_add_exceeds_stock_blocked` | qty > stock_cases → 409 |
| `test_scheme_applied_in_cart` | 10 cases biscuit → scheme saving shown |
| `test_scheme_not_applied_below_min` | 9 cases → no scheme saving |
| `test_remove_line` | DELETE line → line gone from cart |
| `test_clear_cart` | DELETE /cart → empty cart |
| `test_desk_cannot_access_cart` | 403 for Order Desk |

#### Orders (`tests/integration/test_orders.py`)

| Test | Description |
|------|-------------|
| `test_place_order_from_cart` | POST /orders → 201, cart emptied |
| `test_place_order_empty_cart` | 422 |
| `test_place_order_stock_conflict` | Stock drops between cart add and place → 409 |
| `test_retailer_sees_own_orders_only` | Retailer B cannot see Retailer A's orders |
| `test_desk_sees_all_orders` | Order Desk sees both retailers' orders |
| `test_desk_approves_order` | Status → approved |
| `test_desk_rejects_order_requires_note` | Rejection without note → 422 |
| `test_desk_rejects_order_with_note` | Status → rejected, reason stored |
| `test_retailer_cancels_pending_order` | Status → cancelled |
| `test_retailer_cannot_cancel_approved_order` | 422 |
| `test_desk_edits_line_qty` | Recalculated totals returned |
| `test_desk_removes_line` | Line removed from order |
| `test_audit_log_populated` | Each transition written to audit log |

#### AI Capture (`tests/integration/test_ai_capture.py`)

| Test | Description |
|------|-------------|
| `test_ai_extract_valid_message` | Mock Gemini response → validated draft returned |
| `test_ai_extract_gemini_unavailable` | Gemini mock raises error → 503 |
| `test_ai_extract_out_of_stock_flagged` | Tea 250g → warning in draft |
| `test_ai_extract_saves_alias_on_confirm` | Confirm ambiguous → alias saved with `source = "retailer"` |
| `test_desk_product_correction_saves_alias` | Order Desk corrects product → alias saved with `source = "desk"` using `raw_fragment` |
| `test_ai_confidence_level_high_for_alias` | Alias match → `confidence_level = "high"` |
| `test_ai_confidence_level_medium_for_ilike` | Single ilike match → `confidence_level = "medium"` |
| `test_ai_confidence_level_low_requires_confirm` | Weak fuzzy match → `confidence_level = "low"`, presented as ambiguous |
| `test_ai_max_two_alternatives` | Ambiguous result returns at most 2 alternatives (not 3) |
| `test_ai_extract_empty_text` | 422 |

#### Export (`tests/integration/test_export.py`)

| Test | Description |
|------|-------------|
| `test_export_approved_order_csv` | Returns CSV with correct columns and values |
| `test_export_pending_order_blocked` | 422 for non-approved order |
| `test_retailer_cannot_export` | 403 |

---

## 4. Frontend Testing (Vitest)

### 4.1 Setup

- **Vitest** with `@testing-library/react` for component tests.
- `msw` (Mock Service Worker) for API mocking in tests.

### 4.2 Unit Tests

| File | Tests |
|------|-------|
| `formatCurrency.test.ts` | `₹8.10`, `₹0.00`, large numbers |
| `formatDate.test.ts` | ISO string → `06 Nov 2026` |
| `AuthContext.test.tsx` | Login sets token; logout clears token |

### 4.3 Component Tests

| Component | Tests |
|-----------|-------|
| `ProductCard` | Renders name, price, scheme badge; "Out of Stock" badge; Add to Cart disabled when OOS |
| `CartLine` | Shows qty, price, scheme saving; remove button works |
| `AiDraftLine` | Renders confirmed/ambiguous/unmatched/out-of-stock states correctly |
| `AlternativeSelector` | Clicking an option calls `onSelect`; correct product names shown |
| `UnitClarifier` | Renders unit options; selecting one calls callback |
| `OrderStatusChip` | Correct colour and label for each status |

---

## 5. Test Data Seed

A `tests/fixtures/seed_data.py` module provides:
- 2 test retailers (Retailer A, Retailer B)
- 1 test Order Desk user
- 3 products (the 3 sample SKUs from the brief)
- 2 schemes (Buy 10 Get 1 Free on biscuits; 3% on 5+ cases detergent)
- Retailer A has 1 existing order in `pending_review`

This seed is applied per-test via a Pytest fixture that wraps each test in a rolled-back transaction.

---

## 6. CI Pipeline (GitHub Actions — planned)

```yaml
jobs:
  backend-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: dukaanflow_test
          ...
    steps:
      - checkout
      - setup-python 3.11
      - pip install -r requirements-dev.txt
      - pytest tests/ --cov=app --cov-report=term-missing

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - checkout
      - setup-node 20
      - pnpm install
      - pnpm run test
```

---

## 7. Coverage Targets

| Layer | Target |
|-------|--------|
| Scheme engine | 100% line coverage |
| Auth service | ≥ 90% |
| Order service | ≥ 85% |
| AI service | ≥ 80% (Gemini calls mocked) |
| Routers (integration) | ≥ 80% |
| Frontend components | ≥ 70% |

Coverage is enforced in CI with `--cov-fail-under=80` for the backend.

