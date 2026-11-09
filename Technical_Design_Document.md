# DukaanFlow (दुकानफ्लो) — Technical Design Document (TDD)

**Project Name:** DukaanFlow — FMCG Distributor Retailer Ordering Platform  
**Target Market:** FMCG Distributor & 1,800+ Kirana Shops, Jabalpur, Madhya Pradesh  
**Author / Developer:** Nitesh Solanki  
**Official GitHub Repository:** [https://github.com/NITESH100LANKI/DukanFlow](https://github.com/NITESH100LANKI/DukanFlow)  
**Version:** 1.0.0 (Production-Ready Release)  
**Date:** November 2026  

---

## 1. Executive Summary & Problem Context

In Jabalpur, Madhya Pradesh, a high-volume FMCG distributor manages daily sales and physical delivery across 1,800+ independent kirana (grocery) retailers. Currently, order intake relies on unstructured WhatsApp text messages, physical sales rep visits, and phone calls. This results in:
1. **Severe Order Desk Bottlenecks:** Human operators spend hours deciphering phonetic brand names (*"parle g 10 peti"*, *"surf excel 5 peti"*, *"maggi 2 carton"*), manually cross-referencing distributor trade schemes, checking warehouse stock, and typing orders into accounting software.
2. **Pricing & Scheme Calculation Errors:** Trade schemes (such as *Buy 10 Get 1 Free* or *3% turnover cash discounts*) are frequently misapplied, causing margin erosion or merchant disputes.
3. **Data Loss & Financial Discrepancies:** Orders modified after placement lack immutable audit trails, preventing clear reconciliation between distributor dispatch logs and accounting records.

**DukaanFlow** resolves these pain points through an end-to-end cloud platform combining:
- **Multilingual AI Draft Order Extraction:** Powered by Google Gemini, extracting mixed Hindi, Hinglish, and English informal text with a 5-tier deterministic SKU matching engine and merchant alias learning.
- **Deterministic Scheme Engine:** High-precision decimal calculations supporting BOGOF (Buy N Get M) and percentage discounts with strict fulfilment inventory validation and separation of free goods benefit from monetary invoice deductions.
- **Atomic Order Lifecycle & Row Locking:** Pessimistic locking prevents double deductions under concurrent desk approvals.
- **Accounting & Generic CSV Export:** Compliant, sanitized accounting batch exports protected against spreadsheet formula injection.
- **Enterprise-Grade Security:** Fast2SMS OTP gateway with state machine tracking (`PENDING`, `SENT`, `FAILED`, `UNKNOWN`), dual-token JWT authentication (HttpOnly refresh cookies), and strict role-based access control (Retailer vs. Order Desk).

---

## 2. System Architecture

DukaanFlow uses a decoupled, high-performance architecture built for reliability and horizontal scalability:

```
                               ┌─────────────────────────────────────────┐
                               │            END USER CLIENTS             │
                               │   Retailers (Mobile) & Order Desk (Web) │
                               └────────────────────┬────────────────────┘
                                                    │
                                             HTTPS Requests
                                                    │
                                                    ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ FRONTEND TIER (Vercel Global Edge Network)                                             │
│                                                                                        │
│  - Single Page Application (SPA): React 18, TypeScript, Tailwind CSS, Lucide Icons      │
│  - Edge Rewrites: /api/v1/:path* proxied to backend, eliminating cross-domain cookies  │
│  - Mobile-First UI: Optimized for low-bandwidth mobile browsers in kirana environments │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
                                    Proxied HTTPS
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ BACKEND TIER (FastAPI on Render Web Service)                                           │
│                                                                                        │
│  - Framework: FastAPI (Python 3.12) + Uvicorn ASGI                                     │
│  - Database Engine: SQLAlchemy 2.0 ORM with connection pool budgeting (5 pool + 5 ovfl) │
│  - Migration Pipeline: Alembic (Deterministic revisions from 1fbf2d3 up to 6c3513e)    │
│  - Background Integrations: Google Gemini Interactions API & Fast2SMS Smart OTP Gateway│
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
                                 Pooled TCP Connections
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ DATA TIER (PostgreSQL 15 Managed Engine)                                               │
│                                                                                        │
│  - ACID Transactions, Pessimistic Row Locking (FOR UPDATE)                             │
│  - Immutable Audit Logs, Financial Snapshots, Learned Merchant Aliases                  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Core Database Models & Schema Design

All monetary amounts are strictly stored as `Numeric(10, 2)` (never IEEE floating point) and quantities as `Integer` (in canonical **Cases** / *peti*).

### 3.1 Authentication & User Management
- **`retailers`**: Unique `mobile` (10 digits), business name, owner name, Jabalpur locality address, verified flag, active status.
- **`order_desk_users`**: Email/username, bcrypt password hash, role (`order_desk_operator`, `admin`), active status.
- **`otp_records`**: Mobile, bcrypt OTP hash, 10-minute expiry timestamp, `delivery_status` (`PENDING`, `SENT`, `FAILED`, `UNKNOWN`), `provider_request_id`, `failure_reason`, attempt counter (5-strike lockout), verified/locked flags.
- **`refresh_token_blocklist`**: JTI token hashes, expiration tracking for immediate revocation upon logout or rotation.

### 3.2 Catalogue & Schemes
- **`products`**: Unique SKU (`PARLE-G-100G`, `SURF-EXCEL-1KG`, `TAJ-MAHAL-250G`), brand, category, case pack quantity (e.g. 24 units/case), price per case (`Numeric(10, 2)`), stock in cases (`Integer`), active flag.
- **`schemes`**: Active date range, product SKU target, scheme type (`buy_n_get_m`, `percentage_discount`), threshold quantity `n`, benefit quantity `m`, discount percentage, active flag.

### 3.3 Shopping Cart & Order Lifecycle
- **`carts` & `cart_lines`**: Persistent shopping carts per retailer with real-time recalculation of gross, discount, free goods, and net totals.
- **`orders`**: Incremental order number (`ORD-YYYYMMDD-XXXX`), retailer FK, status (`submitted`, `under_review`, `approved`, `rejected`), immutable financial snapshots (`gross_amount`, `scheme_discount_amount`, `free_goods_benefit_amount`, `net_amount`), desk review timestamps, cancellation reason.
- **`order_lines`**: Snapshot line items with paid cases, free cases, fulfilment cases, unit price, applied scheme details, line gross, line discount, line benefit, and line net.
- **`order_audit_logs`**: Append-only log recording every status change, quantity edit, and product substitution with operator ID, prior values, new values, and mandatory edit reason.

### 3.4 AI Order Drafts & Aliases
- **`retailer_aliases`**: `retailer_id`, `raw_text`, `canonical_sku`, confidence score, `source` (`retailer_resolved` or `desk_corrected`).
- **`ai_order_drafts` & `lines`**: Extracted text sessions, line status (`matched`, `ambiguous`, `unmatched`), candidate SKU alternatives, resolution flags.

### 3.5 Accounting Export Tracking
- **`export_batches`**: Unique batch ID, operator ID, export format (`generic_accounting_csv`), record count, total value, date range filter, timestamp.
- **`export_batch_lines`**: Audit join tracking which order lines were included in which export batch.

---

## 4. Key Engineering Implementations

### 4.1 Scheme Engine & Mathematical Precision
- **Free Goods Scheme (`buy_n_get_m`):**
  - $\text{Free Cases} = \lfloor \frac{\text{Ordered Cases}}{N} \rfloor \times M$
  - $\text{Fulfilment Cases} = \text{Ordered Cases} + \text{Free Cases}$
  - Benefit value is calculated as $\text{Free Cases} \times \text{Price per Case}$ for retailer visibility, but **never deducted from monetary gross**, preserving gross = net.
  - Warehouse stock validation requires $\text{Available Stock} \ge \text{Fulfilment Cases}$, completely preventing unfulfillable free goods commitments.
- **Percentage Discount (`percentage_discount`):**
  - Triggered when $\text{Ordered Cases} \ge N$.
  - Rounded deterministically using **`ROUND_HALF_UP`** to 2 decimal places.

### 4.2 Gemini AI Order Extraction Engine
- **Multilingual Support:** Extracts structured items from Hindi, Hinglish, and English text (e.g. *"bhaiya 10 peti parle g aur 5 box surf excel bhej do"*).
- **5-Tier Deterministic SKU Matching:**
  1. *Tier 1:* Retailer-specific learned alias lookup (`retailer_aliases`).
  2. *Tier 2:* Exact canonical SKU / exact product title match.
  3. *Tier 3:* High-confidence substring matching across brand, title, and keywords.
  4. *Tier 4:* Ambiguous match (surfacing $\le 2$ alternatives to the retailer for 1-tap disambiguation).
  5. *Tier 5:* Unmatched line with manual catalog search fallback.
- **Self-Learning Alias Pipeline:** When a retailer resolves an ambiguity or Order Desk corrects a product line, a persistent alias is recorded to guarantee instant Tier-1 matching for all future orders.

### 4.3 Order Review & Atomic Inventory Deductions
- Order approvals execute pessimistic row locks (`SELECT ... FOR UPDATE` on `products`).
- Validates total fulfilment cases against live inventory.
- Atomically decrements stock and transitions order status to `approved`.
- If any line has insufficient stock, the transaction rolls back cleanly with HTTP 409 and zero stock leakage.

### 4.4 Fast2SMS Smart OTP Gateway & State Machine
- Strict delivery state workflow: `PENDING` $\rightarrow$ `SENT`, `FAILED`, or `UNKNOWN`.
- Validates both HTTP 200 and JSON response payload `return: true` with non-empty `request_id`.
- Ambiguous network timeouts transition to `UNKNOWN` and **never retry automatically**, protecting against duplicate SMS blasts and conserving wallet credits.
- Verification strictly permits only records with `delivery_status == "SENT"`.

### 4.5 Generic Accounting CSV Export
- Generates accounting-compatible CSV exports for back-office integration.
- Sanitizes formula injection threats (`=`, `+`, `-`, `@`, `\t`, `\r`) by prefixing single quotation marks (`'`).
- Tracks export history in `export_batches` with immutability guarantees.

---

## 5. Test Verification & Code Quality Metrics

The codebase is fortified with comprehensive unit, integration, and security tests across both backend and frontend:

| Component | Framework | Test Count | Pass Rate | Execution Time |
|---|---|---|---|---|
| **Backend API & Engines** | Pytest + Asyncio | **136 tests** | **100% Passed** | 37.5s |
| **Frontend UI & State** | Vitest + React Testing Library | **50 tests** | **100% Passed** | 4.1s |
| **Frontend Production Build** | Vite + TypeScript compiler | **0 errors** | **Built Cleanly** | 2.1s (103.6 kB gzip) |

### Tested Edge Cases:
- Concurrent order approvals preventing double deductions.
- Prompt injection and malicious payload resistance in AI extraction.
- Formula injection evasion in CSV export.
- 5-attempt retailer lockout and 3-per-10-minute rate limiting.
- HttpOnly cookie token rotation and revocation.
- Tenant isolation across distinct kirana accounts.

---

## 6. Official Links & Repository Information

- **GitHub Repository:** [https://github.com/NITESH100LANKI/DukanFlow](https://github.com/NITESH100LANKI/DukanFlow)
- **Production Runbook:** Included in repository as `deployment.md`
- **Architecture Documentation:** Included in repository under `docs/` (13 detailed planning specifications)

---
*DukaanFlow Technical Design Document — Jabalpur FMCG Platform Project*
