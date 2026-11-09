# 03 — System Architecture

## 1. Architecture Overview

DukaanFlow uses a **layered monolith** architecture — a single backend application organised into well-separated modules. This approach is chosen deliberately:

- It is manageable by a single developer.
- It avoids the operational complexity of microservices (service discovery, inter-service auth, distributed tracing).
- Internal modules can be extracted into separate services later if the load warrants it.

```
┌──────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                          │
│   React + TypeScript + Vite + Tailwind CSS (SPA)             │
│   Served as static files from Nginx                          │
└───────────────────────────┬──────────────────────────────────┘
                            │  HTTPS  (REST JSON)
┌───────────────────────────▼──────────────────────────────────┐
│                       API GATEWAY LAYER                      │
│   Nginx (reverse proxy, SSL termination, static file serve)  │
└───────────────────────────┬──────────────────────────────────┘
                            │  HTTP (internal)
┌───────────────────────────▼──────────────────────────────────┐
│                     APPLICATION LAYER                        │
│   FastAPI (Python 3.11+)                                     │
│   ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐    │
│   │  Auth       │  │  Catalogue   │  │  Cart / Orders  │    │
│   │  Router     │  │  Router      │  │  Router         │    │
│   └──────┬──────┘  └──────┬───────┘  └────────┬────────┘    │
│          │                │                   │             │
│   ┌──────▼──────────────────────────────────▼─────────┐    │
│   │               Service / Business Logic Layer       │    │
│   │   AuthService │ CatalogueService │ CartService     │    │
│   │   OrderService │ SchemeEngine    │ AIOrderService  │    │
│   └──────────────────────────────┬────────────────────┘    │
│                                  │                          │
│   ┌──────────────────────────────▼────────────────────┐    │
│   │               Data Access Layer                   │    │
│   │   SQLAlchemy ORM  +  Repository pattern           │    │
│   └──────────────────────────────┬────────────────────┘    │
└──────────────────────────────────┼──────────────────────────┘
                                   │
            ┌──────────────────────┼─────────────────┐
            │                      │                 │
┌───────────▼────────┐  ┌──────────▼──────┐  ┌──────▼──────────┐
│   PostgreSQL 15    │  │  Gemini API      │  │  File Storage   │
│   (primary DB)     │  │  (AI provider)   │  │  (CSV exports)  │
└────────────────────┘  └─────────────────┘  └─────────────────┘
```

---

## 2. Component Responsibilities

### 2.1 Frontend (React SPA)
- Renders UI for Retailer and Order Desk roles.
- All routing is client-side (`react-router-dom`).
- Makes authenticated REST calls to the FastAPI backend.
- Stores JWT access token in memory (not localStorage) to reduce XSS risk.
- Stores refresh token in an `HttpOnly` cookie.
- Never performs price or scheme calculations; all business logic lives in the backend.

### 2.2 Nginx
- Serves the compiled React SPA (`dist/`).
- Reverse-proxies `/api/*` requests to the FastAPI process.
- Handles SSL termination (Let's Encrypt / self-signed for local).
- Applies basic rate limiting on `/api/auth/*` endpoints.

### 2.3 FastAPI Application

| Module | Responsibility |
|--------|---------------|
| `routers/auth.py` | OTP generation, OTP verification, JWT issue/refresh, logout |
| `routers/catalogue.py` | Product listing, search, single product detail |
| `routers/cart.py` | Cart CRUD, line totals, scheme application |
| `routers/orders.py` | Order placement, retailer history, Order Desk queue, status transitions |
| `routers/ai_capture.py` | Accept raw text, call AIOrderService, return draft |
| `routers/export.py` | Tally CSV generation and download |
| `services/auth_service.py` | OTP lifecycle, bcrypt, JWT operations |
| `services/catalogue_service.py` | Product queries, stock checks |
| `services/cart_service.py` | Cart mutations, calls SchemeEngine |
| `services/order_service.py` | Order creation, status transitions, audit log |
| `services/scheme_engine.py` | Scheme evaluation and benefit calculation |
| `services/ai_order_service.py` | Prompt building, Gemini API call, response parsing, alias resolution |
| `services/export_service.py` | CSV generation from order data |
| `models/` | SQLAlchemy ORM models |
| `schemas/` | Pydantic request/response schemas |
| `repositories/` | Database query functions (isolate raw ORM from services) |
| `core/config.py` | Settings from environment variables (pydantic-settings) |
| `core/security.py` | JWT helpers, password hashing |
| `core/dependencies.py` | FastAPI dependency injection (get_db, get_current_user, role guards) |

### 2.4 AI Provider / Service Layer
- `AIOrderService` is the **only** place that calls the Gemini API.
- It accepts raw text + product context and returns a typed Python object (validated by Pydantic).
- The Gemini model, prompt template, and retry logic are configurable without changing business logic.
- If the Gemini API is unavailable, the service raises a `503` and the frontend displays a "AI unavailable, place order manually" message.

### 2.5 PostgreSQL
- Single database with separate schemas if needed; for MVP a single schema is sufficient.
- Alembic handles all schema migrations.
- Connection pooling via SQLAlchemy's built-in pool (size=5, overflow=10 for a t3.small).

---

## 3. Data Flow: Retailer Places AI-Assisted Order

```
Retailer types message
        │
        ▼
Frontend POSTs /api/ai/extract  (raw_text)
        │
        ▼
AIOrderService.extract(raw_text, retailer_id)
  ├── Load retailer aliases from DB
  ├── Load active product catalogue from DB
  ├── Build structured Gemini prompt
  ├── Call Gemini API
  ├── Parse + Pydantic-validate JSON response
  ├── Resolve each extracted item:
  │     confirmed → lookup SKU, check stock
  │     ambiguous → fetch up to 3 alternatives
  │     unmatched → flag for manual selection
  │     unit_unclear → flag for retailer confirmation
  └── Return AIDraft response
        │
        ▼
Frontend renders AI Draft for review
        │
  Retailer edits / confirms all lines
        │
        ▼
Frontend POSTs /api/cart/from-ai-draft
        │
        ▼
CartService creates / replaces cart
SchemeEngine evaluates schemes
        │
        ▼
Frontend shows cart with totals
        │
  Retailer confirms → POST /api/orders
        │
        ▼
OrderService creates order (status: pending_review)
        │
        ▼
Order Desk reviews → PATCH /api/orders/{id}/status
```

---

## 4. Deployment Topology

### 4.1 Local Development (Docker Compose)

```
Developer machine
    │
    ├── Vite dev server (port 5173)   ← React SPA, hot reload
    │       │  proxy /api/* →
    ├── FastAPI / uvicorn (port 8000) ← Backend
    │
    └── PostgreSQL (port 5432)        ← Managed by Docker Compose
```

`docker-compose.yml` manages PostgreSQL and optionally the FastAPI container.  
The Vite dev server proxies `/api/*` to `localhost:8000` (configured in `vite.config.ts`).  
No Nginx in local development.

### 4.2 Proposed Production Stack

```
User Browser
    │
    ▼
Vercel (Frontend)              ← React SPA (static)
    │  /api/* rewrite →
    ▼
Render (Backend)               ← FastAPI + uvicorn
    │
    ▼
Render Managed PostgreSQL      ← or Supabase Postgres
```

**Cookie strategy in production:**  
Vercel Rewrites forward `/api/*` requests to the Render backend URL. From the browser's perspective, all requests go to the same Vercel origin. This allows `SameSite=Strict; HttpOnly; Secure` cookies to function correctly without CORS issues.

**Deployment containers:**

| Service | Platform | Config |
|---------|----------|--------|
| Frontend | Vercel | Auto-deploy from `main` branch |
| Backend | Render Web Service | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Database | Render Managed PostgreSQL | Connection via `DATABASE_URL` env var |

> **[IMPORTANT]** The previous "single Linux VM + Nginx" topology described in Phase 1 is **superseded** by this stack. Nginx is not part of the production or development architecture. Docker Compose is for local development only.

---

## 5. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Monolith vs. microservices | Layered monolith | Single developer, manageable complexity |
| ORM | SQLAlchemy | Type-safe, Alembic migrations, standard in Python ecosystem |
| Async vs. sync FastAPI | Sync endpoints with async Gemini calls | Simpler for a first build; can migrate to full async later |
| JWT storage | Access: in-memory JS variable; Refresh: HttpOnly cookie | Balances security (XSS resistance) with UX |
| Scheme engine | In-process Python | No external dependency; testable in isolation |
| AI abstraction | Service layer with interface | Allows swapping Gemini for another LLM without touching routers |

