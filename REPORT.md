# MediRoute End-to-End Project Report

## 1. Project Overview
**What the project is:** MediRoute is a smart, real-time emergency medical dispatch and routing system.
**Why it exists:** To minimize the time it takes for emergency patients to receive appropriate care by intelligently routing ambulances based on real-time factors.
**The problem it solves:** Traditional dispatch systems often rely on static proximity or simple human judgment, ignoring real-time traffic congestion, hospital capability (e.g., ICU beds, trauma centers), and specific patient vitals. This leads to ambulances arriving at hospitals that either cannot treat the patient or are overcrowded.
**Who it is for:** Emergency Dispatchers, Paramedics/Ambulance Crews, and Hospital Emergency Department (ED) Administrators.
**Core value proposition:** Dynamic, traffic-aware ETA prediction combined with patient-stability-aware routing ensures patients are sent to the *right* hospital in the *fastest* possible time, saving lives.

## 2. Scope of the Project
**In-scope features:**
- Real-time GPS tracking of ambulances via WebSockets.
- Dynamic ETA prediction using external routing APIs (e.g., ORS) and traffic heuristics.
- Patient stability evaluation (vitals, condition type).
- Intelligent hospital scoring and selection engine.
- Audit logging for all dispatch decisions.
- Real-time dashboards for dispatchers, hospitals, and ambulances.
- Notification and webhook delivery system.

**Out-of-scope features:**
- In-ambulance patient monitoring hardware integration.
- Billing and insurance processing.
- Long-term electronic health record (EHR) storage.
- Non-emergency patient transport booking.

**Assumptions:**
- Ambulances are equipped with GPS-enabled devices capable of persistent internet connections.
- Hospitals regularly update their bed availability and capability status.

**Constraints:**
- Must operate effectively even with intermittent network connectivity from ambulances.
- Strict latency requirements for dispatch decisions (must be < 1 second).

**Dependencies:**
- OpenRouteService (ORS) API for base routing geometries.
- Firebase for push notifications (FCM).
- Redis for real-time caching and WebSocket state management.

## 3. User Requirements
**User roles:**
1. **Paramedic (Ambulance Driver):** Needs to receive dispatch orders, input patient vitals/conditions, and see the fastest route to the assigned hospital.
2. **Hospital Admin (ED Staff):** Needs to see incoming ambulances, patient conditions, and ETAs to prepare trauma/ICU beds.
3. **Dispatcher (Admin):** Needs a bird's-eye view of all active cases, ambulance locations, and system-wide metrics.

**User needs:**
- **Paramedics:** Hands-free or minimal-click interfaces, loud notifications, clear turn-by-turn or map-based ETAs.
- **Hospitals:** Audible alerts for incoming critical patients, visual dashboards of inbound ETAs.
- **Dispatchers:** System health metrics, manual override capabilities for routing.

**User pain points:**
- "We arrived at the hospital but they didn't have a trauma surgeon available."
- "The GPS said 10 minutes, but it took 25 because of sudden traffic, and the hospital wasn't updated."

**Expected user journeys:**
- Paramedic inputs patient status -> System calculates best hospital -> Hospital is notified -> Paramedic follows route -> ETA updates live on Hospital dashboard -> Paramedic arrives.

**Use cases:**
- Dispatching an ambulance to a critical trauma patient.
- Rerouting an ambulance if the target hospital suddenly goes on diversion.
- Reviewing historical dispatch decisions for QA and training.

## 4. Functional Requirements
**Feature: Smart ETA Prediction**
- *What it does:* Calculates expected arrival time and updates it live based on GPS pings.
- *Input:* Ambulance Lat/Lng, Destination Lat/Lng, Current Speed.
- *Process:* Fetches base route, applies traffic/speed heuristics, smooths data to avoid jitter.
- *Output:* Remaining minutes, remaining km, route geometry.
- *Edge cases:* Ambulance goes off-route, GPS signal lost.
- *Error scenarios:* ORS API down (fallback to haversine distance + average speed).

**Feature: Stability Engine & Hospital Scoring**
- *What it does:* Decides whether to "stabilize first" (nearest facility) or "transport now" (specialized facility), then scores candidates.
- *Input:* Patient vitals, condition type, hospital capabilities, live ETAs.
- *Process:* Evaluates if patient is stable. Filters hospitals by capability (e.g., needs ICU). Scores based on ETA, bed availability, and capability match.
- *Output:* Assigned Hospital ID, Score Breakdown.
- *Edge cases:* Multiple hospitals with identical scores (tie-breaker logic needed). No capable hospital within safe distance.
- *Error scenarios:* Database timeout when fetching hospitals.

**Feature: Real-time Tracking (WebSocket)**
- *What it does:* Broadcasts live locations to hospital and admin dashboards.
- *Input:* JSON payload with lat, lng, speed from ambulance client.
- *Process:* Validates token, updates ETA predictor, broadcasts payload to connected hospital/admin clients.
- *Output:* Live map updates on frontend.
- *Edge cases:* WebSocket disconnects temporarily.
- *Error scenarios:* Invalid JWT token (disconnects client).

## 5. Non-Functional Requirements
- **Performance:** Dispatch decision API must return in < 500ms. WebSockets must broadcast within < 100ms.
- **Security:** All endpoints protected by JWT. Patient data (vitals) protected in transit (WSS/HTTPS) and at rest.
- **Scalability:** Must support at least 1,000 concurrent active cases and WebSocket connections.
- **Reliability:** 99.9% uptime. System must degrade gracefully (e.g., if ORS fails, use straight-line math).
- **Maintainability:** Code must follow strict linting (Ruff), typing (MyPy), and maintain >90% test coverage.
- **Usability:** High-contrast UI for paramedics to use in bright sunlight or moving vehicles.
- **Accessibility:** Dashboard must support screen readers; alerts must be visual and auditory.

## 6. System Architecture
**High-level architecture:**
- Microservices-inspired monolithic backend (FastAPI) interacting with a React frontend (Vite).
- Event-driven WebSocket layer for real-time tracking.
- Asynchronous task queue (RQ/Redis) for audit logging and analytics processing.

**Components:**
- **Frontend:** React (Vite), TailwindCSS, Leaflet (Maps).
- **Backend:** FastAPI (Python 3.12+).
- **Database:** PostgreSQL 15 (Relational Data, JSONB for flexible payloads).
- **Cache/Queue:** Redis 7 (WebSocket state, RQ workers).

**Data flow:**
1. Frontend sends REST POST to `/api/dispatch`.
2. Backend queries DB (PostgreSQL) for hospitals, ORS for routes.
3. Backend calculates score, updates DB, returns Hospital.
4. Ambulance opens WSS to `/ws/track/{case_id}`.
5. Pings update Redis state and broadcast to Dashboard WSS.

**Technology choices:**
- *FastAPI:* Chosen for native async support, crucial for handling thousands of WebSockets.
- *PostgreSQL:* Chosen for ACID compliance and JSONB support for dynamic audit logs.
- *Redis:* Chosen for blazing-fast pub/sub and ephemeral location caching.

## 7. Database Design
**Database choice:** PostgreSQL
**Tables:**
1. `cases`: id, status, patient_condition, ambulance_lat, ambulance_lng, assigned_hospital_id.
2. `hospitals`: id, name, lat, lng, type, has_icu, total_beds, available_beds.
3. `audit_logs`: id, case_id, severity_score, selected_hospital_id, score_breakdown (JSONB), timestamp.
4. `webhook_deliveries`, `notification_deliveries`.

**Relationships:**
- `cases.assigned_hospital_id` -> `hospitals.id`
- `audit_logs.case_id` -> `cases.id`

**Indexing:**
- B-Tree index on `audit_logs.case_id`.
- Spatial index (PostGIS recommended for future) or standard indices on lat/lng for bounding box queries.

**Scaling considerations:**
- Audit logs will grow rapidly; partition `audit_logs` table by month.

## 8. API Design
**List of APIs:**
- `POST /api/dispatch`: Request a hospital assignment.
- `GET /api/analytics/metrics`: Fetch system-wide analytics.
- `GET /api/analytics/replay/{case_id}`: Fetch audit log for a case.
- `WS /ws/track/{case_id}`: Bidirectional WebSocket for GPS and ETA.

**Endpoint details (Example: POST /dispatch):**
- *Purpose:* Assigns the best hospital.
- *Request format:* `{"ambulance_lat": 28.6, "ambulance_lng": 77.2, "condition": "trauma", "vitals": {...}}`
- *Response format:* `{"hospital_id": 1, "hospital_name": "City General", "eta_minutes": 12, "route": [...]}`
- *Authentication:* Bearer Token (JWT).
- *Status codes:* 200 OK, 400 Bad Request, 401 Unauthorized, 500 Internal Server Error.

## 9. UI/UX Design
**Page-by-page breakdown:**
1. **Login:** Standard email/password or SSO.
2. **Dispatch / Paramedic View:** Large "Request Dispatch" button. Minimal form for patient condition. Map showing route to assigned hospital.
3. **Hospital Dashboard:** Kanban-style board of incoming ambulances (ETA < 5 min, ETA 5-15 min). Audible alerts for critical cases.
4. **Admin Dashboard:** System metrics (average response time, hospital load distribution), historical replays.

**Responsive behavior:**
- Paramedic view is mobile-first, designed for tablet/phone in ambulance.
- Admin/Hospital views are desktop-optimized with dense data tables.

## 10. Business Logic
**Decision Flow (Dispatch Engine):**
1. Check patient vitals -> calculate stability index.
2. If unstable -> Mode = "Stabilize First" (prioritize nearest hospital with basic ER).
3. If stable -> Mode = "Transport Now" (prioritize hospital with best capability match, e.g., Trauma Center, even if slightly further).
4. Filter hospitals based on hard constraints (e.g., must have ICU).
5. Apply ML/Heuristic Scoring: Score = (Base Capability * 0.5) - (ETA penalty * 0.3) + (Availability Bonus * 0.2).
6. Select top score.

**Special cases:**
- Traffic gridlock: If ORS returns an ETA > 60 mins for all hospitals, dispatch helicopter protocol or alert manual dispatcher.

## 11. Security
**Authentication & Authorization:**
- JWT-based authentication.
- Role-Based Access Control (RBAC): Paramedics cannot access Admin analytics; Hospitals can only see cases routed to them.

**Data protection:**
- TLS 1.3 for all in-transit data.
- Passwords hashed using bcrypt.
- PII (Patient Identifiable Information) stripped from `audit_logs` (only medical conditions and coordinates are saved).

**Preventive measures:**
- Rate limiting on API endpoints (via `slowapi`).
- SQL injection prevented by SQLAlchemy ORM.

## 12. Performance and Scalability
**Expected load:**
- 500 active ambulances sending GPS pings every 3 seconds = ~166 req/sec on WebSockets.

**Bottlenecks:**
- ORS API rate limits. (Mitigation: Cache route geometries in Redis, calculate ETA updates locally using observed speed vs route).
- PostgreSQL writes for high-frequency GPS. (Mitigation: Only save start/end/status changes to DB; ephemeral GPS lives only in Redis/WebSockets).

## 13. Testing Plan
- **Unit tests:** Pytest for pure functions (`haversine`, `vitals_decision`, `score_hospital`).
- **Integration tests:** API endpoints (`/dispatch`), Database migrations (Alembic).
- **Simulation/Adversarial tests:** Run 100s of synthetic cases through `dispatch_engine` to ensure no hospital receives 100% of cases (load balancing validation).
- **Test tags:** `@unit`, `@integration`, `@security`, `@simulation`, `@adversarial`.

## 14. Deployment Plan
**Environments:**
- *Development:* Docker Compose (App, Postgres, Redis).
- *Staging:* Kubernetes cluster mimicking production.
- *Production:* Multi-node Kubernetes, managed PostgreSQL (e.g., AWS RDS), managed Redis (Elasticache).

**CI/CD:**
- GitHub Actions: Run Ruff (linting), Pytest (tests), build Docker images, and push to container registry on merge to `main`.
- Deployment via ArgoCD or simple Docker Compose pull/restart for MVP.

## 15. Project Structure
- `backend/app/api`: FastAPI routes (`dispatch.py`, `tracking.py`).
- `backend/app/engine`: Core logic (`dispatch_engine.py`, `ml_scorer.py`).
- `backend/app/db`: Models and database config.
- `backend/app/services`: External integrations (`routing_service.py`).
- `frontend/src/components`: Reusable UI elements.
- `frontend/src/pages`: Main views (`Dispatch.jsx`, `HospitalDashboard.jsx`).

## 16. Timeline / Development Phases
- **Phase 1 (MVP - Month 1-2):** Core dispatch logic, DB setup, basic Paramedic/Hospital UI, Haversine distance (no live traffic).
- **Phase 2 (Month 3):** ORS Integration (live traffic), WebSocket tracking, smart ETA prediction.
- **Phase 3 (Month 4):** ML scoring refinement, Admin analytics dashboard, Adversarial testing suite.

## 17. Risks and Challenges
- **Technical Risk:** External routing API (ORS) goes down. *Mitigation: Built-in fallback to haversine distance.*
- **Product Risk:** Hospitals fail to update bed availability. *Mitigation: Default to average availability, implement "mark as busy" quick buttons for hospitals.*
- **Integration Risk:** GPS drift in urban canyons. *Mitigation: Route snapping and confidence scoring in `eta_minutes` calculation.*

## 18. Future Enhancements
- Integration with smart traffic lights to clear intersections for inbound ambulances.
- Real-time video feed from ambulance to hospital ER.
- Federated learning to improve ML scoring without centralizing patient data.

## 19. Final Summary
**Overall project strength:** MediRoute tackles a highly critical, high-value problem with a robust, modern tech stack (FastAPI/React/WebSockets). The architecture is sound, isolating complex dispatch logic from standard API plumbing.
**What is realistic:** The MVP tracking and routing is highly realistic and deployable.
**What is difficult:** Accurately determining patient stability via limited paramedic input, and predicting exact ETAs in chaotic traffic.
**What should be simplified first:** Defer advanced ML scoring to Phase 3; rely on strict deterministic rules (hard constraints + proximity + traffic) for the MVP to ensure trust and reliability.
