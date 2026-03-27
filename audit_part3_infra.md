# MediRoute — Technical Audit (Part 3: Infra & System Analysis)

---

## 33. [backend/Dockerfile](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/backend/Dockerfile)

- **Purpose:** Builds Python 3.11-slim backend image
- **Key Logic:** `COPY requirements.txt → pip install → COPY . . → uvicorn`
- **Known Issues:** No `--reload` for dev; no multi-stage build; no health check; ML model `.pkl` not included (mounted via volume)

---

## 34. [frontend/Dockerfile](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/Dockerfile)

- **Purpose:** Multi-stage build — Node 20 builder + Nginx production server
- **Key Logic:** `npm ci → npm run build → copy dist to nginx → copy nginx.conf`
- **Known Issues:** [.env](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/backend/.env) must be present at build time (Vite embeds env vars at build); no `.dockerignore` check

---

## 35. [frontend/nginx.conf](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/nginx.conf)

- **Purpose:** Nginx config for SPA routing, API proxy, and WebSocket proxy
- **Key Logic:**
  - `try_files $uri $uri/ /index.html` — React Router support
  - `/api/` → `proxy_pass http://backend:8000/api/`
  - `/ws/` → WebSocket upgrade proxy to backend
- **Known Issues:** No caching headers; no gzip compression; no rate limiting

---

## 36. [docker-compose.yml](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/docker-compose.yml)

- **Purpose:** Orchestrates 3 services: [db](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/backend/app/db/database.py#13-19) (Postgres 15), `backend` (FastAPI), `frontend` (Nginx)
- **Key Config:**
  - DB: `postgres:mediroute123@db:5432/mediroute` with health check
  - Backend: ports 8000, mounts `ml_training/` for model persistence
  - Frontend: port 3000→80
- **Known Issues:**
  > [!WARNING]
  > 1. **Password mismatch** — docker-compose uses `mediroute123`, [.env](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/backend/.env) uses `postgres`
  > 2. `SECRET_KEY: mediroute_hackathon_secret_2024` — hardcoded in compose file, committed to repo
  > 3. `version: "3.9"` — deprecated in modern Docker Compose

---

## 37. [backend/seed.py](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/backend/seed.py)

- **Purpose:** One-command seeder — runs synthetic data gen → dataset gen → model training
- **Key Logic:** Runs 3 scripts sequentially via `subprocess.run`, exits on failure
- **Usage:** `docker exec mediroute_backend python seed.py`
- **Known Issues:** Assumes CWD is `/app`; no seed for initial hospitals/users (must be pre-seeded)

---

## 38. [frontend/.env](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/.env)

- **Purpose:** Frontend environment variables for map APIs
- **Contents:** `VITE_GOOGLE_MAPS_KEY=your_google_key_here`, `VITE_ORS_API_KEY=eyJvcm...` (real key), no `VITE_MAPBOX_TOKEN`
- **Known Issues:** ORS key committed to repo; Mapbox token placeholder will break Map page

---

## 39. [backend/requirements.txt](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/backend/requirements.txt)

- **Purpose:** Python dependencies — 12 packages
- **Key Deps:** `fastapi>=0.100.0`, `sqlalchemy>=2.0.0`, `psycopg2-binary`, `passlib[bcrypt]`, `python-jose[cryptography]`, `anthropic`
- **Known Issues:** Missing `scikit-learn`, `xgboost`, `pandas`, `numpy` — needed for ML training/inference; `anthropic` pinned to old version

---

## 40. [frontend/package.json](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/package.json)

- **Purpose:** Frontend dependencies — React 19, Vite 8, routing, maps
- **Key Deps:** `axios`, `jwt-decode`, `leaflet`, `mapbox-gl`, `react-leaflet`, `react-router-dom`
- **DevDeps:** `tailwindcss` (present but may not be fully configured)
- **Known Issues:** No test framework (no jest/vitest); `lucide-react` in deps but unused in audited files

---

# SYSTEM-LEVEL SECTIONS

---

## A. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT (Browser)                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │  Login   │  │ Dispatch │  │  Result  │  │ Hospital Track   │   │
│  │  Page    │  │  Console │  │  Page    │  │ (Leaflet + WS)   │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘   │
│       │              │             │                  │             │
│       └──────────────┴─────────────┴──────────────────┘             │
│                          │ HTTP / WebSocket                         │
└──────────────────────────┼──────────────────────────────────────────┘
                           │
                    ┌──────┴──────┐
                    │   NGINX     │  :3000 → :80
                    │  (frontend) │
                    │  /api → :8000│
                    │  /ws  → :8000│
                    └──────┬──────┘
                           │
                    ┌──────┴──────┐
                    │   FastAPI   │  :8000
                    │  (backend)  │
                    │             │
                    │ ┌─────────┐ │     ┌──────────────┐
                    │ │ Auth    │─┼────►│  PostgreSQL   │
                    │ │ Router  │ │     │   :5432       │
                    │ ├─────────┤ │     │               │
                    │ │Dispatch │ │     │ users         │
                    │ │ Router  │ │     │ hospitals     │
                    │ ├─────────┤ │     │ availabilities│
                    │ │ ML      │ │     │ cases         │
                    │ │ Scorer  │ │     └───────────────┘
                    │ ├─────────┤ │
                    │ │WebSocket│ │     ┌──────────────┐
                    │ │Tracking │ │     │ ML Model     │
                    │ ├─────────┤ │     │ (.pkl file)  │
                    │ │ AI/     │─┼────►│ RandomForest │
                    │ │ Claude  │ │     │ 15 features  │
                    │ └─────────┘ │     └──────────────┘
                    └─────────────┘
                           │
                    ┌──────┴──────┐
                    │ Claude API  │ (Optional)
                    │ (Anthropic) │
                    └─────────────┘
```

---

## B. API Contract Table

| Method | Path | Auth | Role | Request Body | Response Body | Status Codes |
|--------|------|------|------|-------------|---------------|--------------|
| `GET` | `/` | No | — | — | `{status}` | 200 |
| `POST` | `/api/auth/register` | No | — | `{email, password, role, hospital_id?}` | `{message}` | 201, 400 |
| `POST` | `/api/auth/login` | No | — | `{email, password}` | `{access_token, token_type}` | 200, 401 |
| `GET` | `/api/hospitals/` | No | — | — | `[{id, name, address, lat, lng, availability}]` | 200 |
| `PUT` | `/api/hospitals/{id}/availability` | Yes | hospital | `{beds, icu, doctors, equipment[], accepting}` | `{message}` | 200, 403 |
| `POST` | `/api/dispatch/` | Yes | ambulance | `{condition, equipment_needed[], ambulance_lat, ambulance_lng}` | [DispatchResponse](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/backend/app/schemas/dispatch.py#11-27) (17 fields) | 200, 403, 404 |
| `GET` | `/api/cases/` | Yes | any | — | `[CaseOut]` | 200 |
| `GET` | `/api/cases/hospital` | Yes | hospital | — | `[Case]` (last 24h) | 200, 403 |
| `GET` | `/api/cases/admin/stats` | Yes | any* | — | `{total_hospitals, beds, icu, cases, districts[], recent_cases[]}` | 200, 403 |
| `POST` | `/api/ai/analyze` | No | — | `{input: string}` | `{result: {condition, severity, equipment[], reasoning}}` | 200, 500 |
| `WS` | `/ws/ambulance/{case_id}` | No | — | JSON `{lat, lng, eta_minutes}` | — (forwards to hospital) | — |
| `WS` | `/ws/hospital/{case_id}` | No | — | — (listen only) | JSON `{lat, lng, eta_minutes}` | — |

---

## C. Database Schema Audit

| Table | Column | Type | Constraints | Issues |
|-------|--------|------|-------------|--------|
| **users** | id | Integer | PK, indexed | ✓ |
| | email | String | unique, indexed | ✓ |
| | password_hash | String | — | ✓ |
| | role | String | — | ⚠ No enum constraint |
| | hospital_id | Integer | FK→hospitals, nullable | ✓ |
| | created_at | DateTime(tz) | server_default=now() | ✓ |
| **hospitals** | id | Integer | PK, indexed | ✓ |
| | name | String | indexed | ✓ |
| | address | String | — | ✓ |
| | lat/lng | Float | — | ⚠ No range validation |
| **availabilities** | id | Integer | PK, indexed | ✓ |
| | hospital_id | Integer | FK→hospitals | ⚠ No unique constraint (allows duplicates) |
| | beds/icu/doctors | Integer | default=0 | ⚠ No non-negative check |
| | equipment | ARRAY(String) | default=[] | ⚠ PostgreSQL-specific |
| | accepting | Boolean | default=True | ✓ |
| | updated_at | DateTime(tz) | server_default + onupdate | ✓ |
| **cases** | id | Integer | PK, indexed | ✓ |
| | user_id | Integer | FK→users | ✓ |
| | condition | String | — | ⚠ No enum |
| | equipment_needed | ARRAY(String) | default=[] | ⚠ PostgreSQL-specific |
| | ambulance_lat/lng | Float | — | ✓ |
| | assigned_hospital_id | Integer | FK→hospitals, nullable | ✓ |
| | final_score/distance_km | Float | — | ✓ |
| | eta_minutes | Integer | — | ✓ |
| | created_at | DateTime(tz) | server_default=now() | ✓ |

**Missing:** No `status` field on cases; no indexes on `cases.assigned_hospital_id` or `cases.created_at` (used in queries); no `availabilities` unique constraint on `hospital_id`.

---

## D. ML Pipeline Audit

```
generate_synthetic.py    →    generate_dataset.py    →    train_model.py    →    ml_scorer.py
(600 cases, 20 conds)    →    (positive+negative       →    (RandomForest,       →    (Inference with
 scored by formula)            feature vectors)              threshold tuning)          fallback)
```

| Risk | Detail | Severity |
|------|--------|----------|
| **Scoring weight mismatch** | Synthetic gen: 25/45/30, scorer.py: 40/35/25, ml_scorer fallback: 40/35/25 | HIGH |
| **Beds normalization mismatch** | Synthetic: `beds/100`, scorer: `beds/10`, dataset: `beds/30` | HIGH |
| **Condition list mismatch** | synthetic=20, dataset=21 (extra: `mild allergic reaction`), frontend=9 | MEDIUM |
| **Threshold overfitting** | Threshold tuned on test set, not validation set | MEDIUM |
| **No cross-validation** | Single 80/20 split | LOW |
| **Feature leakage risk** | Low — features are all legitimate hospital attributes | LOW |

---

## E. Security Audit

| Finding | Severity | Location |
|---------|----------|----------|
| **SECRET_KEY is placeholder** or hardcoded in docker-compose | CRITICAL | [.env](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/backend/.env), [docker-compose.yml](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/docker-compose.yml) |
| **Claude API key committed** to version control | CRITICAL | [.env](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/backend/.env) |
| **CORS allow_origins=["*"]** | HIGH | [main.py](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/backend/app/main.py) |
| **No WebSocket authentication** | HIGH | [tracking.py](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/backend/app/api/endpoints/tracking.py) |
| **No role validation** on registration | MEDIUM | [auth.py](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/backend/app/api/endpoints/auth.py) |
| **No auth on AI endpoint** | MEDIUM | [ai.py](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/backend/app/api/endpoints/ai.py) |
| **JWT role not validated** — ProtectedRoute only checks token existence | MEDIUM | [ProtectedRoute.jsx](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/src/components/ProtectedRoute.jsx) |
| **No rate limiting** on login | LOW | [auth.py](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/backend/app/api/endpoints/auth.py) |
| **No HTTPS enforced** in config | LOW | [nginx.conf](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/frontend/nginx.conf) |

---

## F. Performance Audit

| Issue | Location | Impact |
|-------|----------|--------|
| **N+1 Query: hospitals** | `hospitals.py:16-20`, `dispatch.py:26-30` | O(n) queries per request |
| **Full table scan** on every dispatch | `dispatch.py:23` — `db.query(Hospital).all()` | Loads 188 hospitals every dispatch |
| **No DB indexes** on `cases.assigned_hospital_id`, `cases.created_at` | [models.py](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/backend/app/db/models.py) | Slow filtered queries |
| **ML model loaded at import** | `ml_scorer.py:28` | Blocks startup; loaded once (✓ cached) |
| **WebSocket in-memory only** | [tracking.py](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/backend/app/api/endpoints/tracking.py) | Single-worker limitation |
| **No pagination** on case lists | [cases.py](file:///c:/Users/ARYAN/OneDrive/Desktop%281%29/team%20tech/backend/app/api/endpoints/cases.py) | Unbounded result sets |

---

## G. Full Test Plan (Summary)

| Category | Count | Key Tests |
|----------|-------|-----------|
| **Unit Tests** | 12 | Haversine, scorer, ml_scorer, schemas validation |
| **Integration Tests** | 9 | Auth flow, dispatch, hospital availability update |
| **API Tests** | 12 | All endpoints: auth, hospitals, dispatch, cases, admin stats |
| **E2E Tests** | 6 | Login→Dispatch→Result→Map flow, Hospital dashboard→Track |
| **Load Tests** | 3 | 100 concurrent dispatches, WebSocket 50 connections, Stats endpoint under load |

See Part 1 and Part 2 for all 42 individual test cases per file.

---

## H. Deployment Checklist

```bash
# 1. Clone and navigate
git clone <repo-url>
cd team-tech

# 2. Configure environment
#    - Edit backend/.env: set real SECRET_KEY, verify DATABASE_URL
#    - Edit frontend/.env: set VITE_MAPBOX_TOKEN, VITE_ORS_API_KEY

# 3. Start all services
docker compose up --build -d

# 4. Wait for DB healthcheck, then seed data
docker exec mediroute_backend python seed.py

# 5. Create demo users (run inside backend container)
docker exec -it mediroute_backend python -c "
from app.db.database import SessionLocal
from app.core.security import hash_password
from app.db.models import User
db = SessionLocal()
db.add(User(email='amb1@test.com', password_hash=hash_password('test123'), role='ambulance'))
db.add(User(email='bhagwati@test.com', password_hash=hash_password('test123'), role='hospital', hospital_id=1))
db.add(User(email='admin@test.com', password_hash=hash_password('test123'), role='admin'))
db.commit()
print('Users created')
"

# 6. Access
#    Frontend:  http://localhost:3000
#    Backend:   http://localhost:8000/docs (Swagger)
#    Demo creds: amb1@test.com / test123 (ambulance)
#               bhagwati@test.com / test123 (hospital)
#               admin@test.com / test123 (admin)
```

---

## I. Hackathon Judge Briefing

### What is MediRoute?
MediRoute is a **real-time ML-powered emergency dispatch system** that optimally assigns ambulances to hospitals across Uttarakhand's ~188 hospitals. It uses a trained RandomForest model with 15 clinical/geographic features to score every hospital in real-time, then routes the ambulance with live GPS tracking via WebSocket.

### Key Technical Differentiators
1. **ML-Powered Dispatch** — Not just nearest-hospital; considers beds, ICU, equipment match, specialty match, condition severity, and 10 more features
2. **Real-Time GPS Tracking** — WebSocket relay between ambulance and hospital with animated map (Mapbox + ORS routing)
3. **188 Real Hospitals** — Seeded from actual Uttarakhand hospital data across 6 districts
4. **Dual Map Libraries** — Mapbox GL JS for ambulance (3D, premium) + Leaflet for hospital (lightweight, open-source)
5. **Terminal UI Aesthetic** — Custom-built retro terminal interface with boot sequence, ASCII art, scanlines

### What to Look for During Demo
1. **Login** — Watch the boot sequence typewriter animation
2. **Dispatch** — Select condition + equipment → ML engine evaluates all 188 hospitals in real-time
3. **Result** — ML confidence score with ASCII bar, reasoning explanation, one-click map
4. **Map** — Animated ambulance route with live ETA countdown
5. **Hospital Dashboard** — Incoming case alerts with live tracking
6. **Admin** — System-wide stats with district capacity ASCII charts

### Architecture Strengths
- Clean separation: React SPA → Nginx → FastAPI → PostgreSQL
- Docker Compose for one-command deployment
- ML pipeline: synthetic data → feature engineering → model training → threshold tuning → inference with rule-based fallback
