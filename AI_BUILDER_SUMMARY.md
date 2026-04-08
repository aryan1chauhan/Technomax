# MediRoute — Project Summary for AI Builder

## 1. Project Overview
**MediRoute** is a real-time, ML-powered hospital-ambulance dispatch system originally built for a state-level hackathon. 

**Core Workflow:** An ambulance dispatcher inputs an emergency case (or uses Voice-to-Text via the Web Speech API). The system uses Anthropic Claude AI to parse raw voice transcripts into structured emergency conditions and recommended equipment. An ML scoring engine evaluates 188 local hospitals in real-time based on distance, beds, ICU capacity, and equipment match. The ambulance is then automatically routed to the best-suited hospital, with live GPS tracked via WebSockets.

## 2. Tech Stack
*   **Backend:** Python, FastAPI, SQLAlchemy, PostgreSQL, Pydantic, Uvicorn.
*   **Frontend:** React 19 (Vite), React Router v6, Leaflet (Maps), Axios, custom CSS.
*   **Machine Learning:** Scikit-Learn, RandomForest / XGBoost for predictive scoring of hospitals.
*   **AI Integration:** Anthropic Claude 3 Haiku for parsing unstructured voice transcripts.
*   **Infrastructure:** Docker Compose, Nginx, Render (Production).

## 3. Architecture & Components
*   **Backend (`/backend`)**:
    *   `/api/endpoints/dispatch.py`: Core routing logic.
    *   `/api/endpoints/tracking.py`: Real-time WebSocket endpoints mimicking moving ambulance GPS data.
    *   `/api/endpoints/hospitals.py`, `auth.py`, `cases.py`: CRUD, Auth (JWT-based RBAC), and case tracking.
    *   `/api/endpoints/ai.py`: Proxies calls to Claude, with deterministic rule-based fallback if the API fails.
    *   `app/engine/ml_scorer.py`: The hybrid matchmaking engine. Ranks hospitals using a trained XGBoost model (`hospital_model.pkl`), with rule-based fallback logic.
*   **Frontend (`/frontend/src`)**:
    *   Premium, dark "hacker-terminal" UI aesthetic.
    *   `Map.jsx`: 3D Leaflet map with WebSocket live-tracking rendered smoothly via `requestAnimationFrame`.
    *   `Dispatch.jsx`: The command center. Features Web Speech API integration.
    *   `Result.jsx`: Displays the chosen hospital, ML match reasoning, ETA, distance, etc.
    *   `HospitalDashboard.jsx` / `AdminDashboard.jsx`: Live polling/dashboards for incoming cases and district capacity.

## 4. Current State & Recent Production Fixes
The project was recently heavily audited and upgraded to be production-ready (Render deployment). Recent stability fixes include:
*   **Security & Env Configuration:** Remedied exposed secrets (`.env`), fixed wildcard CORS configurations, and ensured secure database bindings.
*   **WebSocket Resiliency:** Fixed `RuntimeError` unaccepted socket connection logic and connection drops during real-time tracking broadcasts (`app/api/endpoints/tracking.py`).
*   **Database & API Optimizations:** Eradicated massive N+1 query bottlenecks in hospital-availability retrieval using optimized SQLAlchemy JOINs, removing 189 unnecessary round trips (`dispatch.py`).
*   **ML Integration:** Re-balanced the ML engine by ensuring data normalization matched exactly between training (`generate_dataset.py`) and inference (`ml_scorer.py`). Distance calculation (`distance_km`) is now the heaviest weight.
*   **AI Resilience:** Hardened AI fallback logic to handle `invalid_request_error` (depleted Anthropic credits or missing API keys) smoothly, ensuring UI integrity. 
*   **UI Parity:** Enforced parity between frontend React ML feature dropdown arrays (`Dispatch.jsx`) and the backend validation engine conditions. Added error handling for `401 Unauthorized` responses in the dashboard.

## 5. Known Quirks / AI Handoff Notes
*   **Role-based Auth:** Handled via custom JWT decoding on the frontend. The backend `/api/auth/login` returns an access token; React uses `jwt-decode` to extract `role` for view-routing (`ProtectedRoute.jsx`).
*   **AI Fallbacks:** If you're building/modifying the AI parser (`/api/ai/equipment-recommend`), ensure the fallback remains pure JSON so frontend components receiving unexpected formats don't crash.
*   **Dependencies & Pickling:** Uses `psycopg2-binary` for dockerized Postgres. When retraining the ML model, ensure the `scikit-learn` version matches perfectly to prevent `pickle.load` RCE or `ValueError` deserialization errors.
*   **Maps API:** Maps default to Dehradun/Roorkee coordinates if browser GPS permissions are rejected.

## 6. Priority Roadmap (For Future AI / Dev Tasks)
Based on the latest automated audit, the remaining high-priority technical debt items are:
*   Add **rate limiting** to API endpoints to prevent API/DB exhaustion (e.g., `slowapi`).
*   Refactor the in-memory WebSocket `ConnectionManager` to use **Redis pub/sub** for horizontal scaling.
*   Introduce **Alembic migrations** (Currently tables are created manually via `models.Base.metadata.create_all()`).
*   Add **test coverage** for core endpoints (currently at 0%).
*   Fix **IDOR vulnerabilities** on hospital availability updates securely.
