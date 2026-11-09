# 09 — Security and Access Control Plan

## 1. Authentication Architecture

### 1.1 JWT Token Design

| Property | Access Token | Refresh Token |
|----------|-------------|---------------|
| Expiry | 15 minutes | 7 days |
| Storage (client) | JavaScript memory variable | `HttpOnly; Secure; SameSite=Strict` cookie |
| Signing algorithm | HS256 | HS256 |
| Secret source | `JWT_SECRET_KEY` environment variable | Same secret |
| Claims | `sub` (user ID), `role`, `jti`, `exp`, `iat` | `sub`, `jti`, `exp`, `iat` |

**Why memory for access token?**  
`localStorage` is readable by any JavaScript on the page (XSS risk). An in-memory variable disappears on tab close, forcing re-use of the refresh token. The refresh token in an `HttpOnly` cookie is inaccessible to JavaScript, protecting against XSS token theft.

### 1.2 Refresh Token Rotation

- On every `/auth/refresh` call, the old refresh token's `jti` is added to the blocklist.
- A new refresh token with a new `jti` is issued.
- If a blocklisted `jti` is presented (replay attack), the token is rejected with `401`.

### 1.3 OTP Security

**Reconciled lockout rule (single consistent policy):**

- OTPs are **hashed** with bcrypt before storage. The raw OTP is never persisted.
- Each OTP record tracks `attempts` (failed verifications) and `locked` (boolean).
- After **5 consecutive incorrect OTP submissions**, the OTP record is set `locked = True`.
- A locked OTP **cannot be verified** even if the correct code is submitted.
- There is **no separate account-level 30-minute lockout**. Lockout is per-OTP-record only.
- The retailer may request a new OTP immediately after lockout; fresh OTP = fresh attempt counter.
- Rate limiting on `/auth/retailer/request-otp` (max 3/mobile/10 min) prevents OTP farming at the generation level.
- OTP records expire after **10 minutes** regardless of attempt status.
- For the demo phase, OTPs are generated as `123456` (or printed to console). **This must be replaced before production.**

### 1.4 Refresh Token Cookie — Cross-Origin Consideration

**Local development:**  
The Vite dev server proxies `/api/*` to `localhost:8000`. Both origins are `localhost`. `SameSite=Lax; HttpOnly; Secure=false` (HTTP is acceptable locally).

**Production (Vercel + Render):**  
The Vercel frontend rewrite forwards `/api/*` to Render. The browser sees the Vercel domain for all requests. The backend should set cookies with `SameSite=Strict; HttpOnly; Secure` targeting the Vercel origin, not `Render.com`.  

**Configuration:** The `COOKIE_DOMAIN` and `COOKIE_SAMESITE` values must be environment-variable-driven. No hardcoding.

---

## 2. Authorisation — Role-Based Access Control (RBAC)

### 2.1 Roles

| Role | Identifier in JWT | Description |
|------|------------------|-------------|
| Retailer | `retailer` | A kirana shop owner |
| Order Desk | `order_desk` | Distributor staff |

No super-admin role for MVP. Admin operations are done directly in the database or via a seeded account.

### 2.2 Endpoint Permission Matrix

| Endpoint | Retailer | Order Desk |
|----------|----------|------------|
| `POST /auth/retailer/request-otp` | ✅ Public | ✅ Public |
| `POST /auth/retailer/verify-otp` | ✅ Public | ✅ Public |
| `POST /auth/desk/login` | ✅ Public | ✅ Public |
| `POST /auth/refresh` | ✅ | ✅ |
| `POST /auth/logout` | ✅ | ✅ |
| `GET /catalogue/products` | ✅ | ✅ |
| `GET /catalogue/products/:sku` | ✅ | ✅ |
| `GET/POST/DELETE /cart/*` | ✅ Own cart only | ❌ |
| `POST /orders` | ✅ | ❌ |
| `GET /orders` | ✅ Own orders only | ✅ All orders |
| `GET /orders/:id` | ✅ Own orders only | ✅ Any order |
| `PATCH /orders/:id/status` | ❌ | ✅ |
| `PATCH /orders/:id/lines/:lid` | ❌ | ✅ |
| `DELETE /orders/:id/lines/:lid` | ❌ | ✅ |
| `POST /orders/:id/cancel` | ✅ Own + pending only | ❌ |
| `POST /ai/extract` | ✅ | ❌ |
| `GET /export/orders/*` | ❌ | ✅ |
| `GET /health` | ✅ Public | ✅ Public |

### 2.3 Resource-Level Checks (Beyond Role)

- **Retailers can only access their own orders and cart.** The backend compares `retailer_id` in the resource against `sub` in the JWT on every retrieval.
- Order Desk actions on orders are not restricted by retailer; they can access all orders.
- If a retailer attempts to access another retailer's order, the response is `403 Forbidden` (not `404` — to avoid leaking order existence).

**Counterpoint considered:** Returning `404` (not `403`) to avoid confirming that an order exists is a valid alternative security posture. This can be revisited. For MVP, `403` with a generic message is used.

---

## 3. Input Validation

### 3.1 Backend (Pydantic)

- Every API endpoint uses a Pydantic schema for request bodies.
- String fields have `max_length` constraints to prevent oversized payloads.
- Numeric fields have `ge=0` or `gt=0` constraints.
- Mobile numbers are validated with a regex: `^[6-9]\d{9}$` (Indian mobile numbers).
- Email fields use Pydantic's `EmailStr`.

### 3.2 SQL Injection Prevention

- All database access goes through SQLAlchemy ORM query methods.
- Raw SQL strings with user-supplied values are never used.
- The `like` / `ilike` search filters use SQLAlchemy's parameterised expressions, not string concatenation.

### 3.3 AI Input Sanitisation

- The raw text from the retailer is passed to the Gemini API inside a **quoted string** in the prompt, never as executable instructions.
- The raw text is length-limited to **1,000 characters** at the API layer (Pydantic constraint). Content exceeding this is rejected with `422`.

---

## 4. Transport Security

- **HTTPS required** in production. HTTP requests redirect to HTTPS.
- TLS 1.2 minimum. TLS 1.3 preferred.
- Security headers on all responses (set by backend middleware, not Nginx):
  - `Content-Security-Policy: default-src 'self'`
  - `X-Frame-Options: DENY`
  - `X-Content-Type-Options: nosniff`
  - `Referrer-Policy: no-referrer`
- **No Nginx in production.** The Vercel + Render architecture handles SSL termination at the platform level. These headers are set by the FastAPI middleware (`starlette.middleware.trustedhost`, `slowapi`, or a custom middleware).

---

## 5. Secrets Management

| Secret | Storage |
|--------|---------|
| `JWT_SECRET_KEY` | Environment variable (`.env` file, never in Git) |
| `DATABASE_URL` | Environment variable |
| `GEMINI_API_KEY` | Environment variable |
| bcrypt passwords | Hashed in DB; raw value never logged or stored |
| OTP values | Hashed in DB; raw value logged to console in demo mode only |

**`.env` files must be listed in `.gitignore`.** A `.env.example` with placeholder values is committed instead.

---

## 6. Audit Logging

- Every order status transition is recorded in `order_audit_log` with: `actor_type`, `actor_id`, `from_status`, `to_status`, `created_at`, and optional `note`.
- Failed login attempts (OTP or password) are logged at the application level (Python `logging`) with IP address and timestamp — **without** the submitted credential.
- Server logs are written to stdout (for Docker log capture), not to files inside the container.

---

## 7. Rate Limiting

| Endpoint | Limit | Enforcement |
|----------|-------|-------------|
| `/auth/retailer/request-otp` | 3 requests / mobile / 10 min | Nginx + DB counter |
| `/auth/retailer/verify-otp` | 5 attempts / OTP | DB counter on `otp_records` |
| `/auth/desk/login` | 10 requests / IP / minute | Nginx |
| `/ai/extract` | 10 requests / retailer / minute | FastAPI middleware |

---

## 8. Data Privacy Notes

- Retailer mobile numbers are PII. They must not appear in application logs.
- Order data is retailer-specific. No retailer can enumerate or access another retailer's data.
- Tally CSV exports contain retailer names and order totals. Access is restricted to Order Desk only.
- **[OPEN QUESTION]** Does the client have any DPDP Act (India) compliance obligations that require a formal data processing notice, data retention limits, or a data deletion workflow? This is not in scope for MVP but should be confirmed before production launch.

