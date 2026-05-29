# 🚑 MediRoute — Smart Emergency Dispatch & Routing System

MediRoute is a smart, real-time emergency medical dispatch and routing system. It minimizes the time it takes for emergency patients to receive appropriate care by intelligently routing ambulances based on patient stability, traffic/congestion-aware ETAs, hospital specialties, and available bed capacities.

> **Live Demo:** [https://technomax-1.onrender.com](https://technomax-1.onrender.com)

---

## 🚀 1. Tech Stack Overview

### 💻 Frontend
- **Framework:** React 19 (Vite, JS)
- **Styling:** TailwindCSS 3, Lucide React (Icons)
- **Maps:** Leaflet & React Leaflet (Interactive maps & routing geometry)
- **State & Notifications:** Firebase Web Push Notification SDK (FCM)
- **HTTP Client:** Axios with JWT request interceptors

### ⚙️ Backend
- **Framework:** FastAPI (Python 3.12+)
- **Database ORM:** SQLAlchemy 2.0 (PostgreSQL 15)
- **Cache & Pub/Sub:** Redis 7 (WebSocket state cache, real-time channels)
- **Background Tasks:** RQ (Redis Queue) for audit logging & webhooks; `async_queue/` for Redis-backed async task dispatch
- **Security:** JWT (JSON Web Tokens) with bcrypt password hashing, SlowAPI (Rate limiting), security response headers
- **Core Engine:** Scikit-Learn based pre-trained ML models (`hospital_model.pkl`) with a robust rule-based weighted fallback, Haversine distance math, and stability triage logic

### 🌐 External Services
- **OpenRouteService (ORS) API:** Live routing geometries & base distance-matrix computations (Haversine fallback when ORS is unavailable)
- **Google Gemini API:** AI-driven medical description & paramedic voice transcript parsing
- **Firebase Cloud Messaging (FCM):** Live push alerts for critical hospital/ambulance updates

---

## 🗂️ 2. Project Folder Structure

```
📂 mediroute-root
├── 📂 backend/                    # FastAPI Backend Codebase
│   ├── 📂 alembic/                # Database migration history
│   ├── 📂 app/                    # Application core modules
│   │   ├── 📂 api/
│   │   │   └── 📂 endpoints/      # Route files: ai, auth, cases, dispatch,
│   │   │                          #   hospitals, tracking, voice, users
│   │   ├── 📂 core/               # Security, auth helpers, config settings
│   │   ├── 📂 db/                 # PostgreSQL DB models & connection setups
│   │   ├── 📂 engine/             # Core dispatch pipeline:
│   │   │                          #   dispatch_engine.py, ml_scorer.py,
│   │   │                          #   stability_engine.py, haversine.py
│   │   ├── 📂 middleware/         # Rate limiting & security headers
│   │   ├── 📂 schemas/            # Pydantic input/output schemas
│   │   └── 📂 services/           # Integrations: dispatch_service, eta_service,
│   │                              #   routing_service, notification_service,
│   │                              #   webhook_service, case_realtime, case_status_service
│   ├── 📂 async_queue/            # Redis-backed async task queue (tasks, redis_client)
│   ├── 📂 audit/                  # Audit log writers
│   ├── 📂 config/                 # Additional runtime configuration
│   ├── 📂 diagnostics/            # Component dominance & score diagnostics
│   ├── 📂 learning/               # Trust layer analytics & scenario adjustments
│   ├── 📂 ml_training/            # ML model training scripts & hospital_model.pkl
│   ├── 📂 queue/                  # RQ worker definitions (tasks, redis_client)
│   ├── 📂 scripts/                # Utility scripts (drift check, dominance diagnostics)
│   ├── 📂 simulation/             # Synthetic scenario engine:
│   │                              #   dispatch_sim, scenario_generator,
│   │                              #   scenario_evaluator, scenario_library, run.py
│   ├── 📂 tests/                  # 33-file pytest suite & validation harness
│   ├── Makefile                   # Task runner (validate, test, check, drift, diagnose)
│   ├── seed_db.py                 # Seeds hospital configurations
│   ├── seed_users.py              # Seeds default users
│   ├── seed_specialists.py        # Seeds specialist hospital data
│   ├── seed_prod.py               # Production-grade seed script
│   ├── profile_dispatch.py        # Dispatch engine profiler
│   ├── .env                       # Backend local environment configs
│   ├── Dockerfile                 # Backend Docker build instructions
│   └── requirements.txt           # Python dependencies
│
├── 📂 frontend/                   # React Frontend Codebase
│   ├── 📂 public/                 # Firebase service worker & static assets
│   ├── 📂 src/
│   │   ├── 📂 api/                # Client Axios instances & interceptors
│   │   ├── 📂 components/         # Reusable components:
│   │   │                          #   MapWidget, VoiceInput, CaseChat, CallPanel,
│   │   │                          #   CaseTimeline, Toast, BackendWakeUp,
│   │   │                          #   ProtectedRoute, ErrorBoundary, StatusBadge,
│   │   │                          #   TerminalBox, TerminalLayout, RouteFallback
│   │   ├── 📂 hooks/              # Custom React hooks
│   │   ├── 📂 pages/              # Application pages:
│   │   │                          #   Login, Dispatch, HospitalDashboard,
│   │   │                          #   HospitalTrack, Result, AdminDashboard,
│   │   │                          #   Map, NotFound
│   │   ├── 📂 styles/             # Global and component-level stylesheets
│   │   ├── firebase.js            # Firebase SDK initialisation
│   │   ├── App.jsx                # Main React Router setup
│   │   └── main.jsx               # React DOM mount point
│   ├── nginx.conf                 # Nginx config for production Docker image
│   ├── .env                       # Frontend local environment configs
│   ├── package.json               # NPM dependencies & build scripts
│   └── vite.config.js             # Vite build config & proxy setups
│
├── 📂 loadtest/                   # k6 load-test scripts & results
├── AGENTS.md                      # AI Test Contract (mandatory test rules)
├── API_REFERENCE.md               # Full REST & WebSocket API reference
├── FEATURE_TRACKER.md             # Feature implementation status
├── REPORT.md                      # System design & architecture report
├── .env                           # Root environment config for Docker Compose
└── docker-compose.yml             # Multi-container orchestration (App, PG, Redis)
```

---

## ⚙️ 3. How to Run the Project Locally

### 🐳 Option A: Running with Docker Compose (Recommended)
This sets up PostgreSQL 15, Redis 7, the backend (10 uvicorn workers), and the frontend (nginx) automatically.

1. Ensure Docker and Docker Compose are running.
2. Copy `.env.example` to `.env` in the root and fill in required secrets (see Section 4).
3. In the root workspace directory, run:
   ```bash
   docker-compose up --build
   ```
4. The frontend will be available at `http://localhost:3000`.
5. The backend API will be available at `http://localhost:8000`.
6. API docs (development only) at `http://localhost:8000/docs`.

> **Note:** In Docker, `ENVIRONMENT=production` hides `/docs` and `/redoc`. Remove or change this env var to expose them locally.

---

### 🛠️ Option B: Running Services Individually (Development Mode)

#### 1️⃣ Backend Setup
1. Open a terminal in the `backend/` directory.
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up the local environment variables in `backend/.env` (see Section 4).
5. Run database migrations:
   ```bash
   alembic upgrade head
   ```
6. Seed the database:
   ```bash
   python seed_db.py          # Hospital configurations
   python seed_users.py       # Default users (admin, paramedic, hospital roles)
   python seed_specialists.py # Specialist hospital data (optional)
   ```
7. Start the FastAPI development server:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   # or via Makefile:
   make dev
   ```

#### 2️⃣ Frontend Setup
1. Open a terminal in the `frontend/` directory.
2. Install npm packages:
   ```bash
   npm install
   ```
3. Set up the local environment variables in `frontend/.env` (see Section 4).
4. Run the frontend development server:
   ```bash
   npm run dev
   ```
5. Open your browser to `http://localhost:5173`.

---

## 🔑 4. Required Environment Variables

### Root `.env` (for Docker Compose)

| Variable | Description | Example |
|---|---|---|
| `DB_PASSWORD` | PostgreSQL password | `strongpassword` |
| `SECRET_KEY` | JWT signing key | `your-super-secret-random-key` |
| `CLAUDE_API_KEY` | Anthropic/Gemini API key | `sk-ant-...` |
| `ORS_API_KEY` | OpenRouteService API key | `eyJvcmc...` |
| `MODEL_SHA256` | SHA-256 hash of `hospital_model.pkl` | `a46ae388...` |
| `VITE_API_URL` | Public URL of the backend (used at frontend build time) | `http://localhost:8000` |

### Backend `.env` (`backend/.env`)

| Variable | Description | Example / Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:port/db` |
| `SECRET_KEY` | Key used to sign JWT tokens | `your-super-secret-random-key` |
| `ALGORITHM` | Encryption algorithm for auth | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT token validity window | `60` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `GEMINI_API_KEY` | Google Gemini API key (voice & text NLP) | `AIzaSy...` |
| `ORS_API_KEY` | OpenRouteService API key (traffic-aware routing) | `eyJvcmc...` |
| `MODEL_SHA256` | SHA-256 hash of `backend/ml_training/hospital_model.pkl` | `a46ae388b1fdc321edd355a3ae431d0eb5cd85f109227563d39c6edd8ee776b7` |
| `FIREBASE_SERVICE_ACCOUNT_PATH` | Path to Firebase credentials JSON | `firebase-service-account.json` |
| `ENVIRONMENT` | Runtime environment (`development` / `production`) | `development` |
| `ENABLE_RATE_LIMIT` | Toggle SlowAPI rate limiting | `true` |

### Frontend `.env` (`frontend/.env`)

| Variable | Description | Example / Default |
|---|---|---|
| `VITE_API_URL` | URL of the running FastAPI server | `http://localhost:8000` |
| `VITE_ORS_API_KEY` | OpenRouteService client API key | `eyJvcmc...` |
| `VITE_FIREBASE_API_KEY` | Firebase client web key | `AIzaSy...` |
| `VITE_FIREBASE_AUTH_DOMAIN` | Firebase project domain | `mediroute.firebaseapp.com` |
| `VITE_FIREBASE_PROJECT_ID` | Firebase project ID | `mediroute` |
| `VITE_FIREBASE_STORAGE_BUCKET` | Firebase storage endpoint | `mediroute.appspot.com` |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | Firebase messaging ID | `1234567890` |
| `VITE_FIREBASE_APP_ID` | Firebase web app identifier | `1:123:web:abc` |
| `VITE_FIREBASE_VAPID_KEY` | FCM web push key (VAPID) | `BI5xNX...` |

---

## 🧪 5. Testing & Verification

MediRoute has a strict **AI Test Contract** (see [`AGENTS.md`](AGENTS.md)) requiring 100% deterministic test execution.

### Backend Tests (pytest — 33 test files)

```bash
cd backend
# Activate venv first, then:

# Run the full pytest suite:
pytest tests/ -v --tb=short

# Or via Makefile:
make test
```

### Dispatch Regression Gate (40-case validation — required before any merge)

```bash
cd backend
make validate
# Equivalent to:
# MODEL_SHA256=<hash> DISABLE_DRIFT_CHECK=1 DISABLE_LEARNING_UPDATE=1 python tests/test_validation.py
```

### Full Pre-merge Gate (validation + pytest)

```bash
cd backend
make check
```

### Additional Makefile Targets

| Command | Description |
|---|---|
| `make dev` | Start the FastAPI dev server |
| `make lint` | Lint `app/` and `tests/` with `ruff` |
| `make diagnose` | Run component score dominance diagnostic against 40-case harness |
| `make drift` | Weekly scoring drift check against the production DB (requires `DATABASE_URL`) |

### Quick Smoke Test

```bash
cd backend
python tests/quick_validation_test.py
```

### Frontend Tests (Vitest)

```bash
cd frontend
npm run test
```

### Load Testing (k6)

```bash
cd loadtest
# See loadtest/README.md for full instructions
.\run-load.ps1
```

---

## 📋 6. Additional Documentation

| Document | Purpose |
|---|---|
| [`API_REFERENCE.md`](API_REFERENCE.md) | Full REST endpoint & WebSocket API reference |
| [`AGENTS.md`](AGENTS.md) | AI Test Contract — mandatory test tags, schemas, and patterns |
| [`FEATURE_TRACKER.md`](FEATURE_TRACKER.md) | Implementation status of all major features |
| [`REPORT.md`](REPORT.md) | System design, architecture decisions, and technical report |
| [`backend/app/engine/DESIGN.md`](backend/app/engine/DESIGN.md) | Dispatch engine & ML scorer design notes |
| [`backend/simulation/DESIGN.md`](backend/simulation/DESIGN.md) | Simulation engine design notes |
| [`loadtest/README.md`](loadtest/README.md) | Load testing setup and k6 scripts guide |

---

## 🏥 7. Key API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/login` | Obtain JWT access token |
| `POST` | `/dispatch/` | Trigger ambulance dispatch decision |
| `GET` | `/hospitals/` | List hospitals with bed availability |
| `GET` | `/cases/` | List active emergency cases |
| `WS` | `/tracking/ws/{case_id}` | Real-time GPS & ETA updates |
| `POST` | `/ai/parse-description` | Gemini-powered medical description parser |
| `POST` | `/voice/parse` | Paramedic voice transcript → structured vitals |
| `GET` | `/health` | Liveness probe (always fast, no DB) |
| `GET` | `/ready` | Readiness probe (confirms DB connectivity) |

> See [`API_REFERENCE.md`](API_REFERENCE.md) for full documentation including request/response schemas, auth headers, and WebSocket message formats.
