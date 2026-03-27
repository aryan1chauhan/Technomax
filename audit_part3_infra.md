# MediRoute Technical Audit Report - Part 3 (Infra & System)

## 35. FILE PATH — docker-compose.yml
**PURPOSE:** Orchestrates the multi-container development and production deployment environment binding the DB, API, and Frontend.
**DEPENDENCIES:** Docker Engine, Docker Compose plugin v2+.
**KEY LOGIC:**
- Defines three distinct services: `db` (PostgreSQL 15), `backend` (FastAPI), and `frontend` (Nginx serving built React files).
- Configures Docker networking inherently across domains allowing `http://db:5432` internally.
- Mounts named volumes (`pg_data`) for strict relational persistence independent of container lifecycles.
- Re-binds crucial backend environment overrides injected via compose string literals.
- Mounts `./backend/ml_training` dynamically assuring model weights (`.pkl`) persist and cross directories cleanly.
**INPUTS & OUTPUTS:** Docker manifests defining infrastructure as code.
**INTEGRATION POINTS:** Ties the entire project together on a single host.
**KNOWN ISSUES:**
- PostgreSQL passwords and `SECRET_KEY` are hardcoded directly into the compose file syntax. This is highly discouraged for production servers. Environments should load these keys locally securely using `.env` referencing.
**TEST CASES:**
1. **Container Start:** Preconditions: Clean daemon. Steps: `docker-compose up -d`. Expected Result: Orchestrator downloads dependencies and correctly runs 3 healthy services linked together on bridge network.
2. **Persistence Check:** Preconditions: DB has generated synthetic cases. Steps: `docker-compose down && docker-compose up -d`. Expected Result: Data cleanly persists natively into new Postgres instance.

## 36. FILE PATH — frontend/Dockerfile & frontend/nginx.conf
**PURPOSE:** Packages the React SPA into a highly optimized, static Nginx web server container ready for remote deployment.
**DEPENDENCIES:** Node 20 (builder), Nginx Alpine.
**KEY LOGIC:**
- Uses a multi-stage build process. First stage uses alpine-node installing packages (`npm ci`) then compiling raw javascript logic bundles via `npm run build`.
- Second stage copies only the output `/dist` folder directly into a tiny Nginx instance drastically shrinking the resulting image size by stripping all dev-dependencies.
- Overrides Nginx `default.conf` using a custom routing structure ensuring React Router works. Crucially utilizes `try_files $uri $uri/ /index.html;` to rewrite deep-link URLs (e.g., `/dispatch` resolving virtually to index.html avoiding 404s).
- Acts as a reverse Proxy bridging `/api/.*` to the `http://backend:8000/api` internal docker network resolving CORS naturally for same-domain deployment architectures.
**INPUTS & OUTPUTS:** React static build logic.
**INTEGRATION POINTS:** Web server hosting and entry-level proxying.
**KNOWN ISSUES:**
- `/ws/` reverse proxy config implicitly trusts upgrading WS connections directly to the backend bypassing any ingress level WAF constraints theoretically possible inside Nginx.
**TEST CASES:**
1. **Container Build Test:** Preconditions: valid React codebase. Steps: `docker build -t frontend_test .`. Expected Result: Builds successfully without node_modules errors or missing CSS dependencies.
2. **React Router Binding:** Preconditions: Running container. Steps: curl `localhost:3000/some-random-page`. Expected Result: Returns standard `index.html` allowing React Router to process Client-side 404s vs Server-side.

---

# SYSTEM LEVEL AUDIT SUMMARIES

## A. Architecture Overview
MediRoute operates on a standard 3-tier monolithic architecture designed specifically for real-time edge responses during high pressure hackathons.
*   **Database Tier:** PostgreSQL 15 deployed relationally handling standard row storage mapped securely via SQLAlchemy mappings.
*   **API Tier:** Python FastAPI acting as the highly concurrent workhorse, bridging REST requests, WebSocket GPS streams, and Scikit-Learn inference pipelines.
*   **Client Tier:** React 19 single-page application heavily customized using Hacker-aesthetic CSS bindings, leveraging Axios interceptors and Google Maps API 3D integrations natively.
*   **Deployment:** Dockerized using Compose for rapid local iteration mapping `/api` traffic through an Nginx proxy to sidestep CORS friction in production footprints.

## B. API Contract Audit
The system primarily exposes:
1.  **Auth Space:** standard JWT bearer token generation logic utilizing Bcrypt hashing.
    *   `POST /api/auth/register`, `POST /api/auth/login`
2.  **Dispatch Engine:** Complex payloads integrating 15-dimensional ML requests mapping ambulance requirements securely to candidate hospital pools.
    *   `POST /api/dispatch/`
3.  **Entity Management:** Aggregation lists filtering real-time capacities.
    *   `GET /api/hospitals/`, `PUT /api/hospitals/{id}/availability`
4.  **Tracking & Metrics:** Historical views and real-time streaming sockets.
    *   `GET /api/cases/`, `GET /api/cases/hospital`, `GET /api/cases/admin/stats`
    *   `WS /ws/ambulance/{case_id}`, `WS /ws/hospital/{case_id}`

## C. Database Schema Summary
*   `users`: Core authentication entity storing `id, email, password_hash, role`. Optionally links to `hospital_id`.
*   `hospitals`: Master catalog of regional infrastructure capturing fixed properties (`lat, lng, total_beds, name, district`).
*   `availability`: Dynamic mapping indicating real-time toggles matching hospital primary key: (`accepting, beds_available, equipment_jsonb, last_updated`). Connected 1:1 using explicit Upserting patterns historically.
*   `cases`: Massive logging table representing dispatch history securely bridging `hospital_id`, `ambulance_user_id`, raw GPS locations uniquely, scoring, conditions logically, and timestamps uniquely mapping time-to-delivery workflows.

## D. Machine Learning Pipeline Analysis
The intelligence engine handles complex variable assignment far exceeding "closest hospital" mapping.
1.  **Data Generator (`generate_synthetic.py`):** In lieu of real historical regional data, it simulates 20 realistic medical emergency types across broad geographical bounded coordinates intelligently scoring results locally with added stochastic noise.
2.  **Trainer (`train_model.py`):** Transforms relational datasets linearly matching negative sampling paradigms (comparing 1 chosen hospital against 7 locally proximate but incorrect choices). Uses RandomForest optimized via Grid searches maximizing precision globally.
3.  **Inference (`ml_scorer.py`):** Ingests live production API parameters rebuilding the identical 15-dimensional column feature list dynamically. Outputs prediction arrays securely overriding standard rule-based heuristics only when predictions meet high-confidence boundary rules natively globally mapping results cleanly to React.

## E. Security & Privacy Audit (Internal Report)
Major risks identified suitable for hackathon mitigation prioritization:
*   **CORS:** `app.main` binds `allow_origins=["*"]`. Must narrow significantly before un-proxied internet exposure.
*   **BOLA (Broken Object Level Authorization):** Endpoints managing hospitals (`update_availability`) inherently lack multi-tenant isolation. Any authenticated hospital operator can query bounds guessing external ID keys mapped natively out of bounds securely.
*   **Environment Leakage:** Hardcoded `SECRET_KEY` inside `docker-compose.yml`.
*   **WebSocket Identity:** `ConnectionManager` handles sockets broadly lacking specific validation hooks on initial handshake connections assuming standard HTTP Bearer tokens correctly parsed previously.

## F. Performance Assessment
*   The fundamental limiting factor is the N+1 query structures executing deep within the generic `hospitals` route explicitly and inherently within the `dispatch` candidate pooling map explicitly. This causes minor latency under 200 items but scales linearly resulting natively in severe blocking queries beyond 10,000 requests.
*   Frontend animations driving `Map.jsx` operate outside the standard React rendering pipeline (using `requestAnimationFrame` securely mutating refs avoiding generic virtual DOM diffing entirely) maximizing frames per second inherently maintaining 60fps on lowest-tier presentation laptops successfully securely mapping tracking paths efficiently.

## G. Hackathon Deployment Checklist
1. [ ] Generate secure long random string for Production `.env` (`SECRET_KEY`).
2. [ ] Ensure `VITE_GOOGLE_MAPS_KEY` accurately locks `Referrers` mapping locally to custom presentation domain successfully inside GCP UI.
3. [ ] Run `python backend/ml_training/generate_synthetic.py` creating the master PostgreSQL tables completely.
4. [ ] Run `python backend/ml_training/generate_dataset.py` mapping flat features cleanly out to `csv` files accurately.
5. [ ] Run `python backend/ml_training/train_model.py` locking `hospital_model.pkl` to directory safely before boot execution.
6. [ ] Seed admin user optionally via `create_admin.py` guaranteeing login capability natively.
7. [ ] Execute `docker-compose up --build -d`.

**— END OF REPORT —**
