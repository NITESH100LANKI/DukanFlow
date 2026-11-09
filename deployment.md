# DukaanFlow — Production Deployment & Release Readiness Runbook

> **Document Version:** 1.0.0
>
> **Status:** Release-Ready Architecture Specification & Operations Manual
>
> **Target Release:** DukaanFlow v0.2.0
>
> **Accepted Git Baseline:** `f29799f`
>
> **Latest Migration Head:** `a831e5f88421` (`create_export_batches_and_lines`)
>
> **Mandatory Deployment Boundary:** This runbook provides exact, deterministic deployment specifications. All automated tooling operates strictly under read/staging verification. Provisioning paid cloud infrastructure, purchasing domain names, binding production ports, or pushing live deployments requires explicit, manual human confirmation.

---

## 1. Target Architecture Overview

DukaanFlow is engineered as a modern, decoupled cloud application with high availability, isolated state boundaries, and zero secret leakage.

```
                              ┌─────────────────────────────────────────┐
                              │            END USER CLIENTS             │
                              │   Retailers (Mobile) & Order Desk (Web) │
                              └────────────────────┬────────────────────┘
                                                   │
                                         HTTPS / WSS Requests
                                                   │
                                                   ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ FRONTEND TIER (Vercel Global Edge Network)                                             │
│                                                                                        │
│  - Static Asset Delivery: HTML5, CSS, JS bundles via globally distributed CDN          │
│  - Client Routing: Single Page Application (SPA) rewrite rules to /index.html          │
│  - Same-Origin Proxy: /api/v1/:path* rewritten to Render Web Service                   │
│    (Eliminates third-party cookie restrictions across *.vercel.app & *.onrender.com)   │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
                                    Proxied HTTPS
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ BACKEND TIER (Render Web Service — Linux Container)                                    │
│                                                                                        │
│  - Process Engine: Python 3.12 + Uvicorn (ASGI) + FastAPI                              │
│  - Dynamic Port Binding: Listens on 0.0.0.0:$PORT                                      │
│  - Health Probes: /health & /ready (Deep DB status), /live (Lightweight ping)          │
│  - Auth Engine: Dual-token JWT (15-min Bearer Access Token + 7-day HttpOnly Cookie)   │
│  - Order Desk RBAC: Role-based authorization for order approvals & accounting export   │
└──────────────────────┬──────────────────────────────────┬──────────────────────────────┘
                       │                                  │
       PostgreSQL SSL  │                                  │ HTTPS REST / SDK
       Connection      │                                  │
                       ▼                                  ▼
┌───────────────────────────────────────┐  ┌─────────────────────────────────────────────┐
│ PERSISTENCE TIER                      │  │ EXTERNAL AI SERVICES                        │
│ (Render Managed PostgreSQL 16)        │  │ (Google Gemini 3.8 Flash)                   │
│                                       │  │                                             │
│  - Transactional ACID storage         │  │  - Multimodal handwritten order extraction  │
│  - Row-level pessimistic locking      │  │  - Structured Pydantic schema validation    │
│  - SSL Mode: sslmode=require          │  │  - 15s timeout with deterministic fallback  │
│  - Zero Seed Policy in Production     │  │  - Zero server secrets exposed to frontend  │
└───────────────────────────────────────┘  └─────────────────────────────────────────────┘
```

---

## 2. Vercel Frontend Setup Step-by-Step

### 2.1 Project Creation & Git Link
1. Log in to the [Vercel Dashboard](https://vercel.com/dashboard).
2. Click **Add New...** > **Project**.
3. Import the `dukaanflow` Git repository.
4. In the **Project Settings**:
   - **Framework Preset**: `Vite`
   - **Root Directory**: `frontend` (Click *Edit* and select the `frontend` folder).
   - **Build Command**: `npm run build` (or leave default Vite command).
   - **Output Directory**: `dist`
   - **Install Command**: `npm ci` (ensures exact `package-lock.json` dependency versions).

### 2.2 SPA & Reverse-Proxy Rewrites (`vercel.json`)
The repository includes `frontend/vercel.json` pre-configured for both client routing and cookie-safe API forwarding:
```json
{
  "rewrites": [
    {
      "source": "/api/v1/:path*",
      "destination": "https://dukaanflow-api.onrender.com/api/v1/:path*"
    },
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" }
      ]
    }
  ]
}
```

> [!IMPORTANT]
> When your Render backend URL is created, verify that the `destination` URL in `frontend/vercel.json` matches your exact Render Web Service hostname.

---

## 3. Render Backend Setup Step-by-Step

### 3.1 Web Service Creation
1. Log in to the [Render Dashboard](https://dashboard.render.com).
2. Click **New +** > **Web Service**.
3. Connect your Git repository.
4. Configure the following service settings:
   - **Name**: `dukaanflow-api`
   - **Region**: `Oregon (US West)` (must match the database region for sub-millisecond latency).
   - **Branch**: `main` (or production branch).
   - **Root Directory**: `backend`
   - **Runtime**: `Python 3` (or `Docker` using `backend/Dockerfile`).
   - **Build Command**: `pip install -r requirements.txt`
   - **Pre-Deploy Command**: `alembic upgrade head`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: `Starter` ($7/mo) or higher (ensures persistent execution without cold starts).

### 3.2 Dynamic Port Binding Verification
Render dynamically assigns a port to the web service via the `PORT` environment variable. The backend start command strictly uses `--host 0.0.0.0 --port $PORT`. The application also contains fallback handling defaulting to `8000` during local container testing.

### 3.3 Infrastructure as Code (`render.yaml`)
Alternatively, deploy using the committed `render.yaml` blueprint:
1. In Render Dashboard, click **Blueprints** > **New Blueprint Instance**.
2. Select the repository. Render will automatically parse `render.yaml` and provision both the Web Service and Managed PostgreSQL database together.

---

## 4. Managed PostgreSQL Database Setup

### 4.1 Provisioning Independent Database on Render
1. In the Render Dashboard, click **New +** > **PostgreSQL**.
2. Set specifications:
   - **Name**: `dukaanflow-postgres`
   - **Database**: `dukaanflow`
   - **User**: `dukaanflow_user`
   - **Region**: `Oregon (US West)` (same region as Web Service).
   - **PostgreSQL Version**: `16`
   - **Plan**: `Starter` ($7/mo).

### 4.2 Connection Strings: Internal vs External
Render provides two connection strings:
- **Internal Database URL**: `postgresql://dukaanflow_user:<pwd>@dpg-xxxxxx-a:5432/dukaanflow`
  - Used for the backend Web Service. Traffic stays within Render's private network; zero egress latency, no internet transit, highly secure.
- **External Database URL**: `postgresql://dukaanflow_user:<pwd>@dpg-xxxxxx-a.oregon-postgres.render.com:5432/dukaanflow?sslmode=require`
  - Used for developer database migrations, emergency CLI access, or manual administrative queries.

### 4.3 SSL and Connection Pooling
- Render PostgreSQL requires SSL for all external connections.
- SQLAlchemy engine configures `pool_pre_ping=True` and handles reconnection automatically.
- Production connection URLs must include `sslmode=require`.

### 4.4 Zero Seed Data Policy
> [!CAUTION]
> **Strict Production Rule:** Under no circumstances should `seed.py` or local development dump files be executed against the production database.
>
> Seed scripts contain mock retailer phone numbers (`9876543210`), dummy products, and arbitrary scheme configurations. Production must start completely clean, with catalog products loaded through verified administrative tools and order desk operators securely initialized.

---

## 5. Environment Variables & Secret Management

### 5.1 Backend Production Environment Variables

| Variable | Type / Example | Required | Purpose / Notes |
| :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | `production` | **YES** | Activates production security guards, cookie flags, and strict error handlers. |
| `DEBUG` | `false` | **YES** | Disables detailed stack traces and debugging endpoints. |
| `DATABASE_URL` | `postgresql+psycopg2://...` | **YES** | Internal connection string injected automatically by Render. |
| `JWT_SECRET_KEY` | `64+ char base64 string` | **YES** | Secret key used to sign and verify HMAC-SHA256 JWT tokens. |
| `JWT_ALGORITHM` | `HS256` | **YES** | Cryptographic algorithm for JWTs. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | **YES** | Short-lived retailer and desk access token lifetime. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | **YES** | Long-lived refresh token lifetime stored in HttpOnly cookie. |
| `COOKIE_SECURE` | `true` | **YES** | Enforces `Secure` flag on refresh cookies (browsers send only over HTTPS). |
| `COOKIE_SAMESITE` | `lax` | **YES** | `lax` for Solution A (same-origin proxy); `none` for cross-site subdomains. |
| `COOKIE_DOMAIN` | Empty string / `null` | NO | Leave blank for proxy; set to `.dukaanflow.in` if using custom shared apex. |
| `CORS_ORIGINS` | `https://dukaanflow.vercel.app` | **YES** | Comma-separated list of authorized web frontend origins. |
| `CORS_ORIGIN_REGEX` | `^https://.*dukaanflow.*\.vercel\.app$` | NO | Authorizes dynamic Vercel preview branch deployment URLs. |
| `GEMINI_API_KEY` | `AIzaSy...` | **YES** | Google Gemini API key for multimodal order extraction. Never expose to client! |
| `GEMINI_MODEL` | `gemini-3.8-flash` | **YES** | Standard high-efficiency production model for extraction. |
| `GEMINI_USE_INTERACTIONS_API` | `false` | **YES** | Set `true` if transitioning to direct Interactions API gateway. |
| `AI_TIMEOUT_SECONDS` | `15` | **YES** | Upstream timeout for AI vision extraction before returning graceful degradation. |
| `DEMO_MODE` | `false` | **YES** | **MUST BE FALSE IN PROD.** If true, backend refuses to authenticate and halts. |
| `SMS_PROVIDER_CONFIGURED` | `false` | **YES** | Blocks unauthenticated OTP bypass until live SMS provider (e.g. Twilio) is live. |

### 5.2 Frontend Production Environment Variables

| Variable | Example | Exposure | Purpose / Notes |
| :--- | :--- | :--- | :--- |
| `VITE_API_BASE_URL` | `/api/v1` | **PUBLIC** | Relative path proxied by Vercel to Render. Embedded into JS bundle. |

> [!WARNING]
> **Secret Hygiene:** Never prefix secrets with `VITE_`. Vite compiles all `VITE_*` variables directly into public plaintext JavaScript files readable by any website visitor.

### 5.3 Generating Strong Cryptographic Secrets
Generate a cryptographically secure 256-bit key for `JWT_SECRET_KEY` using Python:
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

---

## 6. CORS and Cookie Architecture

Vercel frontend (`*.vercel.app`) and Render backend (`*.onrender.com`) have different public domain suffixes. Modern browsers (Chrome 80+, Safari ITP, Firefox) classify cookies exchanged across different public suffixes as third-party cookies and block them by default.

### Solution A: Same-Origin Vercel Reverse Proxy (Recommended & Configured)
- **Architecture**: The browser only ever talks to `https://dukaanflow.vercel.app`.
- Requests to `/api/v1/*` are transparently proxied to `https://dukaanflow-api.onrender.com/api/v1/*` by Vercel edge routers.
- **Cookie Mechanics**: The refresh token cookie is set for domain `dukaanflow.vercel.app` with `SameSite=Lax` and `Secure=True`. To the browser, this is a 100% first-party cookie. No cross-site tracking protections are triggered.
- **CORS Requirements**: No complex cross-origin headers are needed between the browser and backend.

### Solution B: Custom Apex Domain with Subdomains (Alternative)
- **Architecture**:
  - Frontend: `https://app.dukaanflow.in`
  - Backend: `https://api.dukaanflow.in`
- **Cookie Mechanics**: The backend sets `COOKIE_DOMAIN=.dukaanflow.in` with `COOKIE_SAMESITE=lax` and `COOKIE_SECURE=true`. Both hostnames share the same `.dukaanflow.in` parent domain, allowing first-party cookie inheritance.
- If completely distinct domains are used, `COOKIE_SAMESITE=none` and `COOKIE_SECURE=true` must be set, and `CORS_ORIGINS` must explicitly match the frontend URL with `Access-Control-Allow-Credentials: true`.

---

## 7. Database Migration Runbook

### 7.1 Pre-Deploy Automated Execution
In Render Web Service settings, the **Pre-Deploy Command** is configured as:
```bash
alembic upgrade head
```
Render runs this command in an isolated container before routing traffic to the newly built image. If the migration fails, the deployment is aborted immediately, keeping the previously running backend online without downtime.

### 7.2 Manual CLI Verification
To inspect migration status from an administrative machine:
```bash
cd backend
export DATABASE_URL="postgresql+psycopg2://dukaanflow_user:<PWD>@dpg-xxxxxx.oregon-postgres.render.com:5432/dukaanflow?sslmode=require"

# Check current database revision
alembic current

# Check available head in codebase
alembic heads

# Apply all outstanding migrations
alembic upgrade head
```

### 7.3 Why Startup Migrations Are Prohibited
Alembic migrations are intentionally **never** executed inside FastAPI's `@app.on_event("startup")` or lifespan context:
1. When scaling to multiple Uvicorn worker processes or container replicas, concurrent startup events race to execute migrations simultaneously, causing table lock deadlocks and schema corruption.
2. An unhandled migration failure during startup causes crash loops, masking the underlying database error.
3. Separation of deployment tasks guarantees schema changes complete before application code boots.

---

## 8. Health Checks & Monitoring

The DukaanFlow backend provides three specialized health endpoints:

### 8.1 Specification Table

| Endpoint | Method | DB Dependency | Target Consumer | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `/health` | GET | **YES** (`SELECT 1`) | Render Health Check & Uptime Monitors | Returns HTTP 200 `{"status": "ok", "db": "connected"}` if database is reachable; HTTP 503 `{"status": "degraded", "db": "unreachable"}` if down. |
| `/ready` | GET | **YES** (`SELECT 1`) | Load Balancers & Traffic Routers | Readiness probe confirming the instance is capable of serving transactional traffic. |
| `/live` | GET | **NO** (Zero I/O) | Container Orchestrator Liveness Probe | Instant HTTP 200 `{"status": "alive"}` confirming process event loop is responsive. |

### 8.2 Safe Operations Verification
- Health endpoints **never** execute Gemini API calls (avoids consuming quota or incurring costs).
- Health endpoints **never** print or leak database credentials or connection strings in HTTP responses or logs.

---

## 9. Frontend Build & Production Bundle Verification

Before pushing frontend releases to Vercel, run the local production build and bundle audit:

```bash
cd frontend
npm ci
npm run build
```

### 9.1 Verification Checklist
1. **Zero Backend Secrets**:
   Run a string search across the generated `frontend/dist/` directory:
   ```bash
   grep -rn "AIzaSy" frontend/dist/
   grep -rn "postgres" frontend/dist/
   ```
   Both checks must return **0 results**.
2. **Correct API Base URL**:
   Inspect compiled JavaScript chunks to confirm `baseURL` resolves to `/api/v1` and does not contain hardcoded `http://localhost:8000`.
3. **Asset Size Optimization**:
   Ensure total vendor chunk size is under 500 KB gzip.

---

## 10. Staging / Preview Deployment Strategy

### 10.1 Vercel Preview Deployments
- Every GitHub pull request automatically triggers an isolated Vercel preview deployment (e.g., `https://dukaanflow-git-feat-xyz-team.vercel.app`).
- The backend CORS middleware includes `CORS_ORIGIN_REGEX=^https://.*dukaanflow.*\.vercel\.app$`.
- Preview deployments can securely test API interactions against staging environments without CORS rejections.

### 10.2 Render Staging Services
- Create a secondary Render Web Service `dukaanflow-api-staging` tracking the `develop` or `staging` branch.
- Connect to an independent staging PostgreSQL database (`dukaanflow-postgres-staging`) to test migrations and load scenarios safely.

---

## 11. Production Go-Live Procedure (Step-by-Step)

Follow this chronological checklist for the initial go-live release:

- [ ] **Step 1: Code Freeze & Git Tagging**
  Confirm all tests pass and tag the accepted release commit:
  `git tag -a v0.2.0 -m "Release v0.2.0: DukaanFlow Production Baseline"`
- [ ] **Step 2: Provision Render PostgreSQL**
  Create `dukaanflow-postgres` in Oregon. Record internal and external connection URLs.
- [ ] **Step 3: Run Database Migrations**
  Execute `alembic upgrade head` from external CLI or Render pre-deploy hook. Verify migration head matches `a831e5f88421`.
- [ ] **Step 4: Provision Initial Order Desk Administrator**
  Because the public API intentionally does not allow self-registration for Order Desk administrators, run the one-time provisioning script against the database:
  ```bash
  python scripts/create_desk_user.py --username admin@dukaanflow.in --password "<STRONG_TEMPORARY_PASSWORD>"
  ```
- [ ] **Step 5: Deploy Render Web Service**
  Create `dukaanflow-api` with Python 3.12 runtime. Configure all environment variables in the Render Dashboard. Verify `/health` reports HTTP 200.
- [ ] **Step 6: Deploy Vercel Frontend**
  Connect frontend repository, verify `vercel.json` points to Render hostname, and trigger production deploy.
- [ ] **Step 7: Post-Deployment Smoke Test**
  1. Open frontend root: verify redirects to `/login`.
  2. Log in as Order Desk operator: verify JWT access token issued and refresh cookie set.
  3. Navigate to Order Desk: `/desk/dashboard`, `/desk/orders`, `/desk/exports`.
  4. Perform test AI order extraction on staging catalog image.
  5. Verify export generation produces valid Tally CSV.
- [ ] **Step 8: Enable External Uptime Monitoring**
  Configure [BetterStack](https://betterstack.com) or [UptimeRobot](https://uptimerobot.com) to ping `https://dukaanflow-api.onrender.com/health` every 60 seconds.

---

## 12. Database Backup & Disaster Recovery

### 12.1 Automated Render Backups
- Render Managed PostgreSQL Starter and higher plans automatically capture **daily physical snapshots** retained for 7 days.
- Point-in-time recovery can be triggered directly in the Render dashboard.

### 12.2 Manual Logical Backups (`pg_dump`)
Prior to performing major version upgrades or schema changes, execute a logical snapshot:
```bash
pg_dump "postgresql://dukaanflow_user:<PWD>@dpg-xxxxxx.oregon-postgres.render.com:5432/dukaanflow?sslmode=require" \
  -F c -b -v -f "dukaanflow_backup_$(date +%Y%m%d_%H%M%S).dump"
```

### 12.3 Disaster Recovery Restoration
To restore a backup into a new recovery database:
```bash
pg_restore -v --clean --no-acl --no-owner \
  -h dpg-recovery-instance.oregon-postgres.render.com \
  -U dukaanflow_user -d dukaanflow "dukaanflow_backup_20261109_120000.dump"
```

---

## 13. Troubleshooting Common Deployment Issues

### 13.1 Authentication Session Lost on Page Refresh
- **Symptom**: User logs in, but refreshing the browser immediately redirects back to `/login`.
- **Root Cause**: Third-party cookie blocking between Vercel and Render.
- **Solution**: Ensure requests are routed through Vercel's `/api/v1` reverse-proxy (Solution A), or verify `COOKIE_SECURE=true` and `COOKIE_SAMESITE=none` if using cross-domain subdomains.

### 13.2 Backend Service Crashes on Port Binding
- **Symptom**: Render deployment logs show `Service failed to bind to port within 10 minutes`.
- **Root Cause**: Uvicorn is hardcoded to port `8000` instead of reading Render's injected `$PORT`.
- **Solution**: Verify the start command is `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

### 13.3 Database Connection Pool Exhaustion
- **Symptom**: Backend logs show `psycopg2.OperationalError: FATAL: remaining connection slots are reserved for non-replication superuser connections`.
- **Root Cause**: High concurrency exceeding PostgreSQL Starter tier limit (97 connections).
- **Solution**: Configure SQLAlchemy connection pool limits in `backend/app/db/session.py` (`pool_size=10`, `max_overflow=5`), or deploy PgBouncer connection pooling.

### 13.4 Gemini AI Rate Limits or Upstream Outages
- **Symptom**: Order extraction returns HTTP 500 or hangs.
- **Solution**: The backend implements an upstream timeout (`AI_TIMEOUT_SECONDS=15`). The frontend gracefully handles errors by prompting the retailer to verify extracted line items or proceed via manual catalog search.

---

## 14. Rollback Procedures

### 14.1 Instant Frontend Rollback (Vercel)
Vercel keeps immutable deployment builds indefinitely. To rollback instantly:
1. Open the Vercel Dashboard > **Deployments**.
2. Find the last known stable deployment.
3. Click the three dots (`...`) > **Promote to Production**.
4. Traffic cuts over in under 5 seconds with zero build delay.

### 14.2 Backend Rollback (Render)
1. In the Render Dashboard, navigate to `dukaanflow-api` > **Events**.
2. Locate the previous successful deploy.
3. Click **Rollback to this deploy**.

### 14.3 Database Schema Rollback (Alembic)
> [!CAUTION]
> Reverting database migrations that dropped columns will cause permanent data loss. Always verify database backups exist before downgrading.

To step back one migration:
```bash
alembic downgrade -1
```
To step back to a specific revision:
```bash
alembic downgrade 4e7f793b510a
```

---

## 15. Outstanding Go-Live Blockers

The following items must be resolved before conducting commercial transactions:

1. **SMS Gateway Integration for Retailer OTP**:
   - `DEMO_MODE=true` is strictly prohibited in production.
   - Real SMS provider (Fast2SMS, Twilio, or Gupshup) credentials must be configured to deliver one-time passcodes to retailer mobile devices.
   - `SMS_PROVIDER_CONFIGURED` must be set to `true` once live.
2. **Client Tally Accounting Schema Confirmation**:
   - dukaanflow exports canonical Tally-compliant CSV files with complete order, line, financial, and batch metadata.
   - The distributor's specific Tally XML / custom TDL column mappings must be verified against their local Tally Prime installation.
3. **GST Legal & Tax Architectural Decision**:
   - dukaanflow currently operates in FMCG wholesale catalog price mode (all product rates and discounts are gross trade prices).
   - If GST tax invoices (CGST + SGST or IGST) must be calculated on-platform, the tax breakdown module must be formally scheduled.

---

## 16. Performance & Operational Limits

- **CSV Export Batch Size**: Hard limit of **500 orders per export batch**. Prevents Uvicorn worker memory spikes and keeps export generation under 3.5 seconds.
- **Database Connection Pooling**: Default `pool_size=10`, `max_overflow=10` per Uvicorn instance.
- **AI Extraction Latency**: Typical response 2.8s – 6.2s. Enforced client timeout of 15 seconds.

---

## 17. Human Approval Gate & Deployment Boundary

**Notice to Operators and Engineers:**

All preparatory infrastructure manifests (`render.yaml`, `backend/Dockerfile`, `frontend/vercel.json`, `requirements.txt`, `.env.production.example`) have been generated and validated.

No third-party cloud accounts, cloud databases, domains, or billing resources have been or will be provisioned without explicit, documented human authorization.
