# 📊 Project Audit Report — MediRoute

**Generated:** 2026-03-31  
**Auditor:** Automated Security & Architecture Audit  
**Project:** MediRoute — Emergency Ambulance Dispatch System  
**Stack:** FastAPI (Python) · React 19 + Vite · PostgreSQL · RandomForest ML · Claude AI · Leaflet Maps  
**Scope:** Full backend, frontend, ML pipeline, infrastructure, and security analysis

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [What Has Been Done Well](#-what-has-been-done-well)
3. [What Needs Improvement](#️-what-needs-improvement)
4. [Security Vulnerabilities Found](#-security-vulnerabilities-found)
5. [Code Quality Issues](#-code-quality-issues)
6. [Performance Issues](#-performance-issues)
7. [Architecture Issues](#-architecture-issues)
8. [Test Coverage Gaps](#-test-coverage-gaps)
9. [Suggested Improvements & New Features](#-suggested-improvements--new-features)
10. [Priority Roadmap](#-priority-roadmap)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MEDIROUTE SYSTEM                            │
├────────────────────┬──────────────────────┬─────────────────────────┤
│   FRONTEND (Vite)  │   BACKEND (FastAPI)  │   ML PIPELINE           │
│                    │                      │                         │
│  Login.jsx ────────┤► /api/auth/login     │  generate_dataset.py    │
│  Dispatch.jsx ─────┤► /api/ai/equip-rec   │  train_model.py         │
│                    │► /api/dispatch/      │  hospital_model.pkl     │
│  Result.jsx ───────┤  (ml_scorer.py)      │                         │
│  Map.jsx ──────────┤► ws/ambulance/{id}   │                         │
│  HospitalDash  ────┤► /api/cases/hospital │                         │
│  HospitalTrack ────┤► ws/hospital/{id}    │                         │
│  AdminDash ────────┤► /api/cases/admin    │                         │
├────────────────────┴──────────────────────┴─────────────────────────┤
│  INFRA: PostgreSQL 15 · Docker Compose · Nginx (prod)              │
│  EXTERNAL: Anthropic Claude API · OpenRouteService · CARTO Tiles   │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow (End-to-End Dispatch)

1. **Paramedic** opens `Dispatch.jsx` → voice input or manual condition selection
2. **Voice transcript** sent to `/api/ai/equipment-recommend` → Claude AI (or rule-based fallback) returns condition, severity, equipment
3. **Condition + equipment + GPS** sent to `/api/dispatch/` → `ml_scorer.py` scores 188 hospitals via RandomForest
4. **Best hospital** returned → `Result.jsx` shows ML reasoning, score, ETA
5. **Map.jsx** opens → Leaflet map with ORS routing, WebSocket ambulance tracking
6. **Hospital** sees case on `HospitalDashboard.jsx` → tracks ambulance via `HospitalTrack.jsx` WebSocket

### Authentication Flow

- JWT (HS256) tokens via `python-jose`, bcrypt password hashing via `passlib`
- Token stored in `localStorage`, attached via Axios interceptor
- Backend `get_current_user` dependency validates token per-request
- Roles: `ambulance`, `hospital`, `admin`

---

## ✅ What Has Been Done Well

| Feature / Pattern | Why It's Good |
|---|---|
| **ML-powered hospital selection** | RandomForest with 15 features, threshold tuning, and rule-based fallback — robust for a hackathon |
| **Feature normalization consistency** | `generate_dataset.py` and `ml_scorer.py` use identical normalization functions — prevents train/serve skew |
| **AI graceful degradation** | Claude API unavailable → rule-based fallback → frontend still works. Zero user-facing errors |
| **N+1 query fix** | `dispatch.py:29-43` uses single JOIN query instead of 189 individual lookups — 20-50× faster |
| **Specialist pre-filter** | `ml_scorer.py:183-194` filters hospitals by condition-specialist mapping before scoring |
| **Log-normalized bed scoring** | `ml_scorer.py:30-37` prevents large hospitals (AIIMS, 500 beds) from dominating over closer small hospitals |
| **Voice input with SpeechRecognition API** | Real browser voice input with i18n (en-IN), graceful mic-permission handling |
| **WebSocket tracking** | Real-time ambulance GPS forwarding from ambulance → hospital via `ConnectionManager` |
| **Distance-dominant ML weights** | Distance gets 0.45 weight, preventing distant mega-hospitals from auto-winning |
| **Docker Compose production setup** | 3-service compose with healthchecks, volume persistence, and nginx reverse proxy |
| **Pydantic settings management** | `pydantic-settings` for typed config with `.env` file support |
| **Frontend error boundaries** | Every API call has try/catch with user-facing error messages, not raw stack traces |
| ***.gitignore covers .env files*** | `.env` files are correctly excluded from git tracking |

---

## ⚠️ What Needs Improvement

### 🔴 Critical (Fix Immediately)

#### 1. HARDCODED ANTHROPIC API KEY IN `.env` FILE — EXPOSED ON DISK
- **File:** `backend/.env:6`
- **Issue:** The **full Anthropic API key** `sk-ant-api03-XXXX...XXXX` is stored in plaintext. While `.env` is in `.gitignore`, if this repo was **ever** pushed with the file accidentally committed (or the file is leaked), the key is fully compromised.
- **Fix:** 
  1. **Rotate the key immediately** in the Anthropic dashboard.
  2. Use environment variables exclusively in production (Docker env, cloud secrets manager).
  3. Add a `.env.example` file with placeholder values.
  4. Run `git log --all -p -- "*.env"` to verify the key was never committed.

#### 2. ROOT `.env` HAS TRUNCATED BUT REAL SECRETS
- **File:** `.env:3-4`
- **Issue:** `SECRET_KEY=mediroute_hackathon_secret_2024` and `CLAUDE_API_KEY=sk-ant-api03-...` are present. The root `.env` appears to be a convenience copy.
- **Fix:** Remove root `.env` or ensure it only contains non-sensitive defaults.

#### 3. CORS WILDCARD — ALLOWS ANY ORIGIN
- **File:** `backend/app/main.py:17`
- **Code:**
  ```python
  allow_origins=["*"],
  allow_credentials=True,
  ```
- **Issue:** `allow_origins=["*"]` combined with `allow_credentials=True` is a severe misconfiguration. Per the CORS spec, browsers should reject this combination, but some implementations may not. Any malicious site can make authenticated requests.
- **Fix:**
  ```python
  allow_origins=[
      "http://localhost:5173",  # Vite dev
      "http://localhost:3000",  # Docker prod
      "https://yourdomain.com",
  ],
  ```

#### 4. PICKLE DESERIALIZATION — ARBITRARY CODE EXECUTION
- **File:** `backend/app/engine/ml_scorer.py:14-15`
- **Code:**
  ```python
  with open(_MODEL_PATH, "rb") as f:
      data = pickle.load(f)
  ```
- **Issue:** `pickle.load()` can execute arbitrary Python code during deserialization. If the `.pkl` file is replaced by an attacker (e.g., via path traversal, supply chain, or compromised training pipeline), it leads to **Remote Code Execution (RCE)**.
- **Fix:** 
  - Validate the model file checksum before loading.
  - Consider using `skops.io` or `joblib` with safe serialization.
  - At minimum, verify the file path is constant and not user-influenced.

#### 5. RAW SQL QUERY — SQL INJECTION RISK
- **File:** `backend/app/api/endpoints/dispatch.py:29-43`
- **Code:**
  ```python
  rows = db.execute(text("""
      SELECT h.id, h.name, ...
      FROM hospitals h
      JOIN availabilities a ON a.hospital_id = h.id
      WHERE a.updated_at = (
          SELECT MAX(a2.updated_at)
          FROM availabilities a2
          WHERE a2.hospital_id = h.id
      )
  """)).fetchall()
  ```
- **Issue:** While this specific query has **no user input** injected into it (it's a static string), using `text()` with raw SQL bypasses SQLAlchemy's parameterization. Any future modification that adds user input to this query would be immediately vulnerable. This is a latent injection risk.
- **Fix:** Rewrite using SQLAlchemy ORM subqueries:
  ```python
  from sqlalchemy import func
  subq = db.query(
      Availability.hospital_id,
      func.max(Availability.updated_at).label("max_ut")
  ).group_by(Availability.hospital_id).subquery()
  
  rows = db.query(Hospital, Availability).join(
      Availability, Availability.hospital_id == Hospital.id
  ).join(subq, ...).all()
  ```

#### 6. NO RATE LIMITING ON ANY ENDPOINT
- **File:** All endpoints in `backend/app/api/endpoints/`
- **Issue:** Zero rate limiting on authentication (`/api/auth/login`), AI analysis (`/api/ai/analyze`), and dispatch (`/api/dispatch/`). An attacker can:
  - **Brute-force passwords** on `/api/auth/login`
  - **Exhaust Claude API credits** by spamming `/api/ai/equipment-recommend`
  - **Create unlimited dispatch cases** flooding the database
- **Fix:** Add `slowapi` or custom rate limiting:
  ```python
  from slowapi import Limiter
  limiter = Limiter(key_func=get_remote_address)
  
  @router.post("/login")
  @limiter.limit("5/minute")
  def login(...):
  ```

---

### 🟡 Moderate (Fix Soon)

#### 7. NO ROLE-BASED AUTHORIZATION ON ADMIN STATS
- **File:** `backend/app/api/endpoints/cases.py:48`
- **Code:**
  ```python
  if current_user.role not in ("admin", "ambulance", "hospital"):
      raise HTTPException(status_code=403, detail="Forbidden")
  ```
- **Issue:** This check allows **all authenticated users** to access admin stats. The check `not in ("admin", "ambulance", "hospital")` will never trigger because those are the only valid roles. Any logged-in user sees full system statistics.
- **Fix:**
  ```python
  if current_user.role != "admin":
      raise HTTPException(status_code=403, detail="Admin access required")
  ```

#### 8. HOSPITAL AVAILABILITY UPDATE — NO HOSPITAL OWNERSHIP CHECK (IDOR)
- **File:** `backend/app/api/endpoints/hospitals.py:34-46`
- **Issue:** A hospital user can update **any** hospital's availability by passing any `hospital_id` in the URL. The code checks `current_user.role != "hospital"` but never verifies `hospital_id == current_user.hospital_id`.
- **Fix:**
  ```python
  if current_user.role != "hospital":
      raise HTTPException(status_code=403, ...)
  if hospital_id != current_user.hospital_id:
      raise HTTPException(status_code=403, detail="Can only update your own hospital")
  ```

#### 9. AVAILABILITY UPDATE — SCHEMA MISMATCH IN `handleMarkReady`
- **File:** `frontend/src/pages/HospitalTrack.jsx:100-112`
- **Code:**
  ```javascript
  await api.put(`/api/hospitals/${caseData.assigned_hospital_id}/availability`, {
      accepting: true,
      status_message: `Ready for case #${case_id}`,
  });
  ```
- **Issue:** The `AvailabilityUpdate` Pydantic schema requires `beds`, `icu`, `doctors`, `equipment`, and `accepting`. This request only sends `accepting` and `status_message` (which isn't in the schema). This will fail with a 422 Validation Error.
- **Fix:** Either make schema fields optional or send the full payload:
  ```python
  class AvailabilityUpdate(BaseModel):
      beds: Optional[int] = None
      icu: Optional[int] = None
      doctors: Optional[int] = None
      equipment: Optional[list[str]] = None
      accepting: bool
  ```

#### 10. PROTECTED ROUTE — NO TOKEN VALIDATION
- **File:** `frontend/src/components/ProtectedRoute.jsx:4`
- **Code:**
  ```javascript
  const token = localStorage.getItem('token')
  if (!token) return <Navigate to="/login" replace />
  ```
- **Issue:** The check only verifies a token **exists**, not that it's valid or unexpired. Any random string in localStorage passes this guard. Routes are also not role-restricted (ambulance can access hospital pages).
- **Fix:**
  ```javascript
  import { jwtDecode } from 'jwt-decode';
  
  export default function ProtectedRoute({ allowedRoles }) {
      const token = localStorage.getItem('token');
      if (!token) return <Navigate to="/login" replace />;
      try {
          const decoded = jwtDecode(token);
          if (decoded.exp * 1000 < Date.now()) {
              localStorage.clear();
              return <Navigate to="/login" replace />;
          }
          if (allowedRoles && !allowedRoles.includes(decoded.role)) {
              return <Navigate to="/login" replace />;
          }
      } catch {
          localStorage.clear();
          return <Navigate to="/login" replace />;
      }
      return <Outlet />;
  }
  ```

#### 11. WEBSOCKET — NO AUTHENTICATION
- **File:** `backend/app/api/endpoints/tracking.py:33-51`
- **Issue:** WebSocket endpoints have **zero authentication**. Anyone can connect to `ws://host/ws/ambulance/{case_id}` or `ws://host/ws/hospital/{case_id}` and:
  - **Spoof ambulance locations** (send fake GPS data)
  - **Eavesdrop on patient case data** (listen to hospital channel)
- **Fix:** Accept token as query parameter and validate:
  ```python
  @router.websocket("/ws/ambulance/{case_id}")
  async def websocket_ambulance(websocket: WebSocket, case_id: int):
      token = websocket.query_params.get("token")
      if not validate_token(token):
          await websocket.close(code=1008)
          return
      await manager.connect_ambulance(case_id, websocket)
  ```

#### 12. BARE `except:` CLAUSES — SWALLOWED EXCEPTIONS
- **Files:**
  - `backend/app/api/endpoints/tracking.py:22` — `except:` silently deletes hospital connection
  - `backend/app/engine/ml_scorer.py:178` — `except:` silently ignores JSON parse errors
  - `backend/ml_training/generate_dataset.py:116` — `except:` silently ignores specialist parse errors
- **Issue:** Bare `except:` catches *everything* including `SystemExit`, `KeyboardInterrupt`, and `MemoryError`. Critical errors are silently swallowed.
- **Fix:** Use specific exception types:
  ```python
  except (ConnectionError, WebSocketDisconnect):
      del self.hospital_connections[case_id]
  ```

#### 13. DEMO CREDENTIALS DISPLAYED ON LOGIN PAGE
- **File:** `frontend/src/pages/Login.jsx:128`
- **Code:**
  ```jsx
  Demo: amb1@test.com · bhagwati@test.com · admin@test.com / test123
  ```
- **Issue:** Production-visible demo credentials. If deployed publicly, anyone can log in as admin.
- **Fix:** Gate behind environment variable:
  ```jsx
  {import.meta.env.DEV && (
      <p>Demo: amb1@test.com / test123</p>
  )}
  ```

#### 14. `scorer.py` — DEAD CODE
- **File:** `backend/app/engine/scorer.py` (entire file, 56 lines)
- **Issue:** This was the original rule-based scorer, fully replaced by `ml_scorer.py`. No imports reference it. It's dead code that adds confusion.
- **Fix:** Delete `scorer.py` or move to an `archive/` directory.

---

### 🟢 Minor (Polish)

#### 15. INCONSISTENT HTTP CLIENT IN FRONTEND
- **Files:** 
  - `frontend/src/pages/HospitalDashboard.jsx:3` — imports `axios` directly
  - `frontend/src/pages/AdminDashboard.jsx:4` — imports `axios` directly
  - `frontend/src/pages/Dispatch.jsx:4` — imports `api` from `../api/axios`
- **Issue:** Some pages use the configured `api` instance (with auth interceptor), others import raw `axios`. The pages using raw `axios` manually attach the token.
- **Fix:** Use `api` from `../api/axios` consistently everywhere.

#### 16. HARDCODED HOSPITAL INFO IN FRONTEND
- **File:** `frontend/src/pages/HospitalDashboard.jsx:62`
- **Code:**
  ```jsx
  <p className="text-[12px] text-[#737A8F]">Roorkee · ID #28</p>
  ```
- **Issue:** Hospital name and ID are hardcoded. Won't reflect the actual logged-in hospital.
- **Fix:** Decode from JWT token or fetch from backend.

#### 17. HARDCODED STATS IN FRONTEND
- **File:** `frontend/src/pages/HospitalDashboard.jsx:99`
- **Code:** `{ val: "28", label: "Beds Available", accent: "#FFB21A" }`
- **Issue:** "28 Beds Available" is hardcoded, not fetched from API.
- **Fix:** Fetch from hospital availability endpoint.

#### 18. `TerminalLayout.jsx` LOGOUT BUTTON IS NON-FUNCTIONAL
- **File:** `frontend/src/components/TerminalLayout.jsx:12-14`
- **Code:** `const handleLogout = () => { console.log('Logging out...'); };`
- **Issue:** Logout button only logs to console. Does not clear localStorage or redirect.
- **Fix:**
  ```javascript
  const handleLogout = () => {
      localStorage.clear();
      window.location.href = '/login';
  };
  ```

#### 19. `App.css` — VESTIGIAL VITE BOILERPLATE
- **File:** `frontend/src/App.css` (185 lines)
- **Issue:** Contains Vite template CSS (`.hero`, `.counter`, `#next-steps`) that is never used by MediRoute components.
- **Fix:** Remove the file or replace with actual project styles.

#### 20. STALE/ORPHANED FILES IN BACKEND ROOT
- **Files:** `backend/out.txt`, `backend/run_output.txt`, `backend/test_api_out.txt`, `backend/ai_test.json`, `backend/query.sql`, `backend/status.txt`, `git_status_output.txt`
- **Issue:** Debug output and temporary files left in the repo.
- **Fix:** Add to `.gitignore` and clean up.

#### 21. ORPHANED HOSPITAL PAGES IN `pages/hospital/` DIRECTORY
- **Files:** `frontend/src/pages/hospital/HospitalDashboard.jsx` (12KB), `frontend/src/pages/hospital/HospitalTrack.jsx` (22KB)
- **Issue:** These are older versions of the hospital pages. The active versions are directly in `pages/`. The orphaned files are larger (likely older terminal-style versions) and never imported.
- **Fix:** Delete `frontend/src/pages/hospital/` directory.

#### 22. MISSING `json` IMPORT IN `generate_dataset.py`
- **File:** `backend/ml_training/generate_dataset.py:115`
- **Code:** `specialists = json.loads(h['specialists'])`
- **Issue:** `json` is never imported at the top of the file. This will crash with a `NameError` if any specialist data is a string.
- **Fix:** Add `import json` at the top of the file.

---

## 🔐 Security Vulnerabilities Found

| Severity | Type | Location | Description | Fix |
|----------|------|----------|-------------|-----|
| **CRITICAL** | Secret Exposure | `backend/.env:6` | Full Anthropic API key (`sk-ant-api03-...`) stored in plaintext on disk | Rotate key immediately; use secrets manager |
| **CRITICAL** | CORS Misconfig | `backend/app/main.py:17` | `allow_origins=["*"]` with `allow_credentials=True` — allows any origin to make authenticated requests | Whitelist specific origins |
| **CRITICAL** | Insecure Deserialization | `backend/app/engine/ml_scorer.py:14` | `pickle.load()` on model file — RCE if file is tampered | Validate checksum; use safe serialization |
| **HIGH** | Missing Rate Limiting | All endpoints | No rate limits on login, AI, or dispatch endpoints | Add `slowapi` rate limiter |
| **HIGH** | Broken Auth (WebSocket) | `backend/app/api/endpoints/tracking.py:33-51` | WebSocket endpoints have zero authentication — anyone can spoof ambulance GPS | Add token validation on WS connect |
| **HIGH** | IDOR | `backend/app/api/endpoints/hospitals.py:47` | Hospital user can update any hospital's availability — no ownership check | Verify `hospital_id == current_user.hospital_id` |
| **HIGH** | Broken Access Control | `backend/app/api/endpoints/cases.py:48` | Admin stats accessible by all roles — check is effectively a no-op | Restrict to `role == "admin"` only |
| **MEDIUM** | SQL Injection (Latent) | `backend/app/api/endpoints/dispatch.py:29` | Raw `text()` SQL query — safe now but dangerous if modified | Refactor to ORM query |
| **MEDIUM** | Client-Side Auth Bypass | `frontend/src/components/ProtectedRoute.jsx:4` | Token existence checked but validity/expiry never verified | Decode and validate JWT client-side |
| **MEDIUM** | Demo Credentials | `frontend/src/pages/Login.jsx:128` | Login page displays demo credentials including admin account | Gate behind `import.meta.env.DEV` |
| **LOW** | Secret in Alternate `.env` | `.env:3` | Root `.env` has `SECRET_KEY` and partial `CLAUDE_API_KEY` | Remove or consolidate |
| **LOW** | Exposed ORS API Key | `frontend/.env:2` | OpenRouteService API key in frontend env (publicly accessible in built JS) | Not a high risk for ORS, but monitor usage |

---

## 🔧 Code Quality Issues

| Severity | Issue | Location | Description |
|----------|-------|----------|-------------|
| **HIGH** | Bare `except:` clauses | `tracking.py:22`, `ml_scorer.py:178`, `generate_dataset.py:116` | Swallows all exceptions including `SystemExit` |
| **HIGH** | Missing `json` import | `generate_dataset.py:115` | Will crash with `NameError` when specialist data is a string |
| **MEDIUM** | Dead code | `backend/app/engine/scorer.py` | 56-line file, never imported, fully replaced by `ml_scorer.py` |
| **MEDIUM** | Orphaned files | `frontend/src/pages/hospital/` | Old versions of hospital pages (34KB total), never imported |
| **MEDIUM** | Vestigial CSS | `frontend/src/App.css` | 185 lines of Vite boilerplate, none used by MediRoute |
| **MEDIUM** | Inconsistent API client | `HospitalDashboard.jsx`, `AdminDashboard.jsx` | Uses raw `axios` instead of configured `api` instance |
| **MEDIUM** | Hardcoded hospital info | `HospitalDashboard.jsx:62,99` | Hospital name "Roorkee · ID #28" and "28 Beds" hardcoded |
| **LOW** | Debug files in repo | `out.txt`, `run_output.txt`, etc. | 7+ temp/debug files in backend root |
| **LOW** | Non-functional logout | `TerminalLayout.jsx:12` | Logout button only logs to console |
| **LOW** | Unused dependency | `frontend/package.json:17` | `mapbox-gl` (3.20.0) installed but never imported — the project uses Leaflet |

---

## 🚀 Performance Issues

| Severity | Issue | Location | Description | Fix |
|----------|-------|----------|-------------|-----|
| **HIGH** | N+1 query in hospital listing | `backend/app/api/endpoints/hospitals.py:12-32` | `get_hospitals()` loops through all hospitals and does individual `db.query(Availability)` per hospital (1+188 queries) | Use a JOIN query like dispatch endpoint |
| **MEDIUM** | Model loaded on import | `backend/app/engine/ml_scorer.py:27` | 7.3MB pickle file loaded synchronously at module import time, blocking server startup | Use lazy loading or async init |
| **MEDIUM** | 10-second polling in HospitalDashboard | `frontend/src/pages/HospitalDashboard.jsx:24` | `setInterval(fetchCases, 10000)` — polls every 10s even if no new data. Uses HTTP instead of WebSocket | Use WebSocket or Server-Sent Events |
| **MEDIUM** | 15-second polling in AdminDashboard | `frontend/src/pages/AdminDashboard.jsx:29` | Same polling pattern for admin stats | Same fix — or use long-polling with ETag |
| **LOW** | No database connection pooling config | `backend/app/db/database.py:7` | `create_engine(DATABASE_URL)` uses defaults (pool_size=5) — may bottleneck under load | Configure `pool_size`, `max_overflow`, `pool_pre_ping` |
| **LOW** | Ambulance animation uses `setTimeout` chain | `frontend/src/pages/Map.jsx:56-68` | Recursive `setTimeout(move, 1000)` can drift and has no cancellation on unmount | Use `requestAnimationFrame` or `setInterval` with cleanup |

---

## 🏗 Architecture Issues

| Severity | Issue | Description | Fix |
|----------|-------|-------------|-----|
| **HIGH** | In-memory WebSocket manager | `tracking.py:5-29` — `ConnectionManager` uses a Python dict. In multi-worker/multi-process deployments, connections are lost | Use Redis pub/sub for cross-process WebSocket coordination |
| **HIGH** | No database migrations | Tables created via `models.Base.metadata.create_all()` at startup. No Alembic migration history despite `alembic` being in `requirements.txt` | Initialize Alembic and create migration scripts |
| **MEDIUM** | Tight coupling: dispatch → ml_scorer | `dispatch.py` directly imports and calls `predict_best_hospital`. No service layer or dependency injection | Add a service layer: `DispatchService` with injectable scorer |
| **MEDIUM** | District mapping hardcoded to hospital IDs | `cases.py:77-84` maps districts by hospital ID ranges (e.g., Dehradun = IDs 93-132). Adding/removing hospitals breaks district analytics | Add `district` column to Hospital model |
| **MEDIUM** | No health check endpoint | No `/health` or `/readiness` endpoint for container orchestration | Add `@app.get("/health")` returning DB connection status |
| **LOW** | Two design systems in frontend | `Login.jsx`, `Dispatch.jsx`, `Result.jsx` use modern light Tailwind design; `HospitalTrack.jsx` uses retro terminal-green-on-black design. Visual inconsistency | Unify design system |
| **LOW** | No OpenAPI auth documentation | FastAPI auto-docs at `/docs` don't show which endpoints need authentication | Add `dependencies=[Depends(get_current_user)]` to router or use security schemes |

---

## 🧪 Test Coverage Gaps

> **Current test coverage: 0%** — No automated tests exist anywhere in the project.

| Priority | Module/Function | What to Test |
|----------|----------------|--------------|
| **CRITICAL** | `backend/app/core/security.py` | Verify password hashing, JWT create/decode, expired token rejection, invalid token handling |
| **CRITICAL** | `backend/app/api/endpoints/auth.py` | Register with duplicate email, login with wrong password, role validation, SQL injection in email field |
| **CRITICAL** | `backend/app/engine/ml_scorer.py` | Score calculation with edge cases (0 beds, 999km distance, empty equipment), model loading failure, threshold behavior |
| **HIGH** | `backend/app/api/endpoints/dispatch.py` | Dispatch with no accepting hospitals, missing GPS coords, null equipment list, non-ambulance role |
| **HIGH** | `backend/app/api/endpoints/hospitals.py` | IDOR test (user A updating hospital B), missing availability record creation, concurrent updates |
| **HIGH** | `backend/app/api/endpoints/ai.py` | Non-medical input rejection, Claude API timeout handling, malformed AI response parsing |
| **MEDIUM** | `backend/app/engine/haversine.py` | Same-point distance (should be 0), antipodal points, negative coordinates |
| **MEDIUM** | `frontend/src/pages/Dispatch.jsx` | Equipment auto-selection on condition change, voice input error states, form validation |
| **MEDIUM** | `backend/app/api/endpoints/tracking.py` | WebSocket connection/disconnection, malformed JSON handling, concurrent connections for same case |
| **LOW** | `backend/ml_training/generate_dataset.py` | Feature normalization ranges, positive/negative ratio, specialist synthetic data generation |
| **LOW** | `Frontend ProtectedRoute` | Expired token redirect, missing token redirect, role-based route access |

---

## 🚀 Suggested Improvements & New Features

### Performance Upgrades

1. **Replace N+1 in `get_hospitals()`** — Convert to a JOIN query matching the optimization already done in `dispatch.py`. Expected: 188 queries → 1 query.
2. **Add Redis caching** — Cache hospital availability data with 30-second TTL. Dispatch reads from cache, availability updates invalidate cache.
3. **Lazy-load ML model** — Load the 7.3MB model on first request, not at import time. Add a warmup endpoint.
4. **Replace polling with SSE/WebSocket** — HospitalDashboard and AdminDashboard should use Server-Sent Events for real-time updates instead of 10/15-second HTTP polling.

### Architecture Improvements

1. **Add Alembic migrations** — Initialize Alembic, generate initial migration from current models, use for all future schema changes.
2. **Add a service layer** — Create `app/services/dispatch_service.py` to decouple API endpoints from business logic and ML scoring.
3. **Add redis-backed WebSocket** — Replace in-memory `ConnectionManager` with Redis pub/sub for multi-worker compatibility.
4. **Add structured logging** — Replace `print()` statements with Python `logging` module, with JSON formatter for production.
5. **Add OpenAPI security schemes** — Document authentication requirements in auto-generated API docs.

### New Features to Consider

| Feature | Why It Would Improve the Project | Rough Implementation Plan |
|---------|----------------------------------|---------------------------|
| **ETA refinement with live traffic** | Current ETA assumes 40 km/h constant speed — unrealistic for urban vs highway | Integrate Google Maps Directions API or Mapbox traffic-aware routing; update ETA via WebSocket every 30s |
| **Hospital capacity auto-decrement** | Dispatching to a hospital doesn't reduce its bed count — can over-dispatch | After dispatch, decrement `beds` by 1 in availability table; add auto-increment when case is closed |
| **Push notifications** | Hospital staff may not have the dashboard open when a case arrives | Add Firebase Cloud Messaging (FCM) or browser Push API for incoming case alerts |
| **Case timeline/audit log** | No history of case status changes (dispatched → en-route → arrived → treated) | Add `CaseEvent` model with status, timestamp, actor; display timeline in case detail view |
| **Multi-hospital fallback** | If the #1 hospital doesn't accept within 2 minutes, auto-escalate to #2 | Store top-3 hospital results; add timer-based re-dispatch with WebSocket notification |
| **Ambulance fleet management** | System dispatches cases but doesn't track which ambulance is free/busy | Add `Ambulance` model with status (available/en-route/at-scene); integrate into dispatch logic |

---

## 📈 Priority Roadmap

### Phase 1 — Immediate (Before Any Public Demo)

| # | Task | Severity | Effort |
|---|------|----------|--------|
| 1 | **Rotate Anthropic API key** and audit git history for accidental commits | CRITICAL | 10 min |
| 2 | **Restrict CORS origins** to specific frontends | CRITICAL | 5 min |
| 3 | **Add rate limiting** on `/api/auth/login` (5/min) and `/api/ai/*` (20/min) | HIGH | 30 min |
| 4 | **Fix admin stats authorization** — restrict to `role == "admin"` | HIGH | 5 min |
| 5 | **Fix IDOR** — add hospital ownership check in availability update | HIGH | 10 min |
| 6 | **Hide demo credentials** behind `DEV` environment flag | MEDIUM | 5 min |

### Phase 2 — Short-Term (Next 1-2 Sprints)

| # | Task | Severity | Effort |
|---|------|----------|--------|
| 7 | Add WebSocket authentication (token in query params) | HIGH | 2 hrs |
| 8 | Fix `ProtectedRoute` to validate JWT expiry and role | MEDIUM | 1 hr |
| 9 | Fix `AvailabilityUpdate` schema to make fields optional | MEDIUM | 30 min |
| 10 | Fix N+1 query in `get_hospitals()` | HIGH | 1 hr |
| 11 | Add `json` import to `generate_dataset.py` | HIGH | 1 min |
| 12 | Replace bare `except:` clauses with specific exceptions | MEDIUM | 30 min |
| 13 | Delete dead code: `scorer.py`, `pages/hospital/`, `App.css` | LOW | 15 min |
| 14 | Use `api` instance consistently (not raw `axios`) | LOW | 15 min |

### Phase 3 — Medium-Term (Architecture)

| # | Task | Severity | Effort |
|---|------|----------|--------|
| 15 | Initialize Alembic migrations | HIGH | 2 hrs |
| 16 | Add basic test suite (auth, dispatch, ML scorer) | HIGH | 8 hrs |
| 17 | Add Redis for WebSocket and caching | MEDIUM | 4 hrs |
| 18 | Add health check endpoint | MEDIUM | 30 min |
| 19 | Add structured logging | LOW | 2 hrs |
| 20 | Unify frontend design system | LOW | 4 hrs |

### Phase 4 — Long-Term (Features)

| # | Task |
|---|------|
| 21 | Hospital capacity auto-decrement on dispatch |
| 22 | Case timeline / audit log |
| 23 | Push notifications for incoming cases |
| 24 | Live traffic-aware ETA |
| 25 | Multi-hospital fallback with timer |

---

> **Bottom line:** MediRoute has a solid core architecture and impressive ML-driven dispatch logic for a hackathon project. The most critical issues are **exposed secrets**, **CORS wildcard**, and **missing rate limiting** — all fixable in under an hour. The architecture gaps (no tests, in-memory WS, no migrations) are expected for a hackathon but should be addressed before any production deployment.
