# DukaanFlow (दुकानफ्लो)

**FMCG Distributor Retailer Ordering Platform**  
Designed for 1,800+ kirana shops in Jabalpur, digitizing WhatsApp-based ordering with AI draft extraction, dealer pricing, scheme engines, and Tally-compatible order desk workflows.

---

## Architecture & Technology Stack

- **Backend:** FastAPI (Python 3.11+), SQLAlchemy 2.0, Alembic, Pydantic v2
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, React Router v6
- **Database:** PostgreSQL 15+ (Local via Docker Compose; Render Managed PostgreSQL in production)
- **Deployment Strategy:** Local Docker Compose / Production: Vercel (Frontend) + Render (Backend) with same-origin `/api` rewrites for HttpOnly cookie compatibility
- **Testing:** Pytest (Backend) + Vitest / React Testing Library (Frontend)

---

## Directory Structure

```
dukaanflow/
├── backend/
│   ├── app/
│   │   ├── api/          # Route handlers (/api/v1/health, etc.)
│   │   ├── core/         # Config, Database engine, Security
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # Business logic & Scheme engine
│   │   └── main.py       # FastAPI application entrypoint
│   ├── tests/            # Pytest test suite
│   ├── alembic/          # Database migrations
│   └── pyproject.toml    # Backend dependencies & metadata
├── frontend/
│   ├── src/
│   │   ├── api/          # Axios client & typed API calls
│   │   ├── components/   # UI components (LanguageToggle, etc.)
│   │   ├── layouts/      # RootLayout with bilingual header & mobile-first shell
│   │   ├── pages/        # Route pages (HomePage, NotFoundPage)
│   │   ├── hooks/        # Custom React hooks
│   │   ├── test/         # Vitest setup
│   │   ├── App.tsx       # Main router setup
│   │   └── main.tsx      # React root
│   └── package.json      # Frontend dependencies & scripts
├── docs/                 # 13 System Architecture & Planning Documents
├── .env.example          # Environment variable template (NEVER commit secrets!)
├── .gitignore            # Git exclusions
├── docker-compose.yml    # Local PostgreSQL service
└── README.md             # This file
```

---

## Quickstart Guide

### 1. Database Setup (Local Docker)

Start PostgreSQL using Docker Compose:

```bash
docker compose up db -d
```

Check database status:
```bash
docker compose ps
```

The database container exposes port `5432` with user `dukaanflow`, password `dukaanflow`, and database `dukaanflow`.

### 2. Backend Setup

From the `backend/` directory:

```bash
cd backend
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -e ".[dev]"
```

Start the development server:
```bash
uvicorn app.main:app --reload --port 8000
```

Verify backend health:
```bash
curl http://localhost:8000/api/v1/health
```

Run backend tests:
```bash
pytest
```

### 3. Frontend Setup

From the `frontend/` directory:

```bash
cd frontend
npm install
```

Start Vite dev server:
```bash
npm run dev
```

The application will be running at `http://localhost:5173`.

Run frontend tests:
```bash
npm run test
```

Build for production:
```bash
npm run build
```

---

## Planning Documents

All 13 detailed architecture, requirement, and workflow documents are located in `docs/`:

1. `00-index.md` — Master index
2. `01-functional-requirements.md` — Functional specifications
3. `02-assumptions-and-open-questions.md` — Explicit assumptions and unresolved client questions
4. `03-system-architecture.md` — Layered monolith & deployment design
5. `04-database-schema.md` — ER diagram & table schemas
6. `05-api-design.md` — REST API endpoint definitions
7. `06-frontend-routes-and-screens.md` — Route map & screen wireframes
8. `07-ai-order-extraction.md` — AI prompt, confidence rules & alias workflow
9. `08-scheme-engine.md` — Free-goods and discount calculation rules
10. `09-security-and-access-control.md` — JWT, RBAC & OTP policy
11. `10-testing-strategy.md` — Testing matrix & coverage targets
12. `11-seven-day-roadmap.md` — Step-by-step development roadmap
13. `12-acceptance-criteria.md` — Given/When/Then acceptance criteria

---

## Current Status

**Phase 2 Initialized:**
- Project folder structure scaffolded.
- Backend FastAPI app with Pydantic settings, SQLAlchemy configuration, Alembic initialization, and `/api/v1/health` endpoint.
- Frontend React + TypeScript + Vite app with Tailwind CSS, React Router, bilingual layout, and Vitest suite.
- Docker Compose PostgreSQL service configured.
- Security boundaries (.env.example, .gitignore) enforced.
- Phase 2 tests (Backend health + Frontend rendering + Build) passing.

