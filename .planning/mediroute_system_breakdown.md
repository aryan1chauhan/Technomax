# MediRoute System Breakdown

## 1. SYSTEM OVERVIEW

MediRoute is a production-grade, real-time emergency medical dispatch system designed to optimally route ambulances to the best-suited hospitals. 

**Functional Purpose:**
The system evaluates emergency cases in real-time, matching patient severity, vitals, condition type, and live location with a network of hospitals. It calculates ETAs, evaluates hospital capabilities (equipment, ICU, beds, specialists), and ranks hospitals using a hybrid Machine Learning (ML) + rules-based engine.

**End-to-End Flow:**
1. **Request:** A client (e.g., dispatcher dashboard) submits a payload containing patient condition, vitals, ambulance location, and required equipment. It can optionally transcribe voice to extract condition via an AI helper.
2. **Decision (Fast Path):** The FastAPI backend receives the request and immediately invokes the `dispatch_engine`. The engine fetches ETAs, filters hospitals by hard constraints (beds, accepting status), and scores viable hospitals using a RandomForest ML model (or a deterministic fallback). 
3. **Queue (Offload):** The resulting decision payload is synchronously returned to the caller. Concurrently, the system uses a non-blocking background task to queue an audit log into a Redis list (`audit_queue`).
4. **Logging (Async Path):** A dedicated worker pulls from Redis, parses the decision, and persists the payload, inputs, outputs, and scores into PostgreSQL.
5. **Analysis:** Background workers calculate streaming metrics, detect concept drift, and allow deterministic "replay" of historical cases to test changes to the ML model.

**Core Philosophy (Real-Time vs Async Split):**
To guarantee bounded latency during critical emergencies, MediRoute strictly isolates the **hot path** (API + Dispatch + Scoring) from the **cold path** (Audit DB writes, Metrics, AI-based learning). The API must *never* block on DB writes, Redis failures, or heavy reporting queries.

---

## 2. ARCHITECTURE DIAGRAM (TEXT)

```text
[Frontend React Dashboard] --(HTTP POST)--> [FastAPI Backend (/dispatch)]
                                                    |
                                                    v
[ML Scorer / Rules Engine] <--(Haversine/ETA Cache)-+-(Fetch live constraints)
                                                    |
[FastAPI returns JSON immediately] <----------------+
                                                    |
                                              (Background Task)
                                                    |
                                            (Redis: lpush 'audit_queue')
                                                    |
                                              [Redis Queue]
                                                    |
                             (Redis: brpop) --------+
                                    |
                            [Worker Process]
                                    |
            +-----------------------+-----------------------+
            |                       |                       |
            v                       v                       v
      [PostgreSQL]          [Metrics Store]         [Drift Detector]
      (audit_logs)          (In-Memory/Global)    (Alerts on score drops)
            ^
            |
    [Replay System]
   (Fetches historical cases
    & compares new rules)
```

**Flow & Failure handling:**
- **Control Flow:** Dispatch API acts as orchestrator -> calls Scorer -> returns JSON -> queues event.
- **Data Flow:** JSON (request) -> memory structures (Scorer) -> JSON (response) -> JSON string (Redis) -> parsed Dict (Worker) -> ORM Model (PostgreSQL).
- **Failure Paths:** If Redis is down, the background task swallows the `RedisError` and the API succeeds (at the cost of dropping standard audits). If DB is down, the worker sleeps and retries.

---

## 3. BACKEND STRUCTURE (FILES + RESPONSIBILITIES)

### `api/`
- **Purpose:** FastAPI routing and HTTP presentation layer. Strictly forbids heavy logic.
- **Key Files:** 
  - `main.py`: App initialization, health checks (API, Redis, DB).
  - `routes/dispatch.py`: Core endpoint `POST /dispatch`. Maps payload to dispatch engine and triggers background Redis tasks.
  - `routes/metrics.py`: Exposes system performance data.
  - `routes/replay.py`: Endpoints for simulating historical cases.

### `core/`
- **Purpose:** Exposes functional interfaces for the rest of the application.
- **Key Files:** 
  - `dispatch_engine.py`: A lean wrapper importing from `app/engine`.
  - `ml_scorer.py`: A lean wrapper for the ML inference logic.

### `app/engine/`
- **Purpose:** The true heart of the application logic. Contains the heavy computation for routing.
- **Key Files:**
  - `dispatch_engine.py` (70KB): Enforces hard constraints, categorizes equipment (critical vs optional), caches ETA, calls the ML scorer, and handles post-ranking filtering.
  - `ml_scorer.py` (47KB): Performs exact feature conversion for ML model inference. Contains a massive fallback logic `_fallback_rule_based_score` if the pickle model is absent. Calculates estimated survival times and degradation curves.

### `async_queue/`
- **Purpose:** The messaging layer bridging the fast and slow paths.
- **Key Files:**
  - `tasks.py`: Contains `enqueue_audit_log(data: dict)`. Implements a strict `try/except` contract to fail silently on the API thread if Redis acts up.
  - `redis_client.py`: Singleton Redis connection setup.

### `workers/`
- **Purpose:** Long-running processes executing background tasks off the queue.
- **Key Files:**
  - `audit_worker.py`: The main loop (`brpop`). Parses JSON events, marshals to SQLAlchemy `AuditLog` models, saves to DB, updates in-memory metrics, and runs drift checks.
  - `drift_worker.py`: Monitors the rolling mean score of dispatch decisions and alerts if it drops below thresholds.

### `db/`
- **Purpose:** Persistence layer mapping.
- **Key Files:**
  - `connection.py`: SQLAlchemy Engine and `SessionLocal` factories.
  - `models.py`: Declarative base and ORM mappings (e.g., `AuditLog`).

### `services/`
- **Purpose:** Domain-level abstractions over data.
- **Key Files:**
  - `metrics_service.py`: A lightweight, lock-free, in-memory dataclass tracking `total`, `total_score`, and `failures`.

---

## 4. DISPATCH ENGINE (CRITICAL)

The Dispatch Engine orchestrates hospital selection. 

**Inputs:**
- Patient condition (e.g., "cardiac_arrest"), Severity score (1-10), Vitals (O2, Pulse, BP).
- Required equipment list.
- Ambulance lat/lng.
- Hospital list (static or dynamic).

**Decision Logic:**
1. **Pre-processing:** Categorizes condition. Determines necessary equipment using strict static rules (`CONDITION_REQUIRED_EQUIPMENT`). Categorizes required equipment into `critical`, `important`, and `optional`.
2. **ETA Resolution:** Generates an ETA map asynchronously across all supplied hospitals. Computes Haversine distance, caches ETAs to reduce computation payload, and applies basic anomaly detection (GPS swapping).
3. **Hard Constraint Filtering:** Rejects hospitals if:
   - Not accepting patients (`accepting=False`).
   - `available_beds <= 0`.
   - Missing `critical_equipment`.
   - Hospital type actively completely mismatches the payload directives.
4. **Scoring:** Routes the remaining candidates to `ml_scorer.py`.

**Scoring Logic:**
- **ML Path:** Loads features into an array (ETA normalized, beds logged, etc.) and runs inference using an XGBoost/RF pickle named `hospital_model.pkl`.
- **Fallback Rule-Based Path:** If ML is down, computes score via weights (`w_survival`, `w_treatment`, `w_equipment`, `w_eta`, `w_load`). It calculates a realistic patient survival degradation score based on `EXP(-deficit/tau)` formulas and checks if stabilization is feasible.

**Outputs:**
A list of ranked hospitals natively padded with computed `eta_minutes`, `ml_score`, and `match_reasons`. 

**Conflict Handling:**
Tie-breakers exist explicitly to prevent score collapse when ML returns similar scores (differing by < 0.05). It prefers the hospital with a higher treatment matching capability.

---

## 5. ASYNC SYSTEM

**Redis Usage:**
Used purely as a simple List queue implementation. The system does not currently use complex Streams or PubSub. 

**Queue Structure:**
Key: `audit_queue`. Value: A raw JSON string payload representing the entire state of the dispatch operation.

**Enqueue Flow:**
1. `POST /dispatch` completes computation.
2. Constructs audit dict.
3. Passes to `BackgroundTasks.add_task`.
4. The background thread executes `redis_client.lpush("audit_queue", payload)`. 
5. Any `RedisError` is explicitly caught and swallowed (`pass`). This completely isolates the API from broker unavailability.

**Worker Consumption Loop:**
The worker uses `redis_client.brpop("audit_queue")` (blocking pop). This means it waits idly with almost zero CPU overhead until an item arrives.

**Failure Handling (Redis Down):**
If the worker loop loses Redis connectivity, it catches `RedisError`, falls into a `time.sleep(1)`, and loops again continuously until connectivity is restored.

---

## 6. WORKER SYSTEM

The core worker system (`workers/audit_worker.py`) is a detached process.

**Exact Flow:**
1. `run_worker()` connects to Redis.
2. Blocks on `brpop`.
3. Unpacks JSON payload.
4. Extracts complex nested information from the payload tree (it checks 9 distinct structural paths for `score` or `final_score` due to historical dataset variations).
5. Invokes `SessionLocal()`.
6. Instantiates an `AuditLog` ORM model.
7. Executes `session.merge(log)` and `session.commit()`.
8. Triggers `metrics.record(...)`.
9. Triggers `check_drift()`.

**Drift Detection Triggers:**
After recording the metric, `check_drift()` computes the global `mean_score`. If the sample size is > 50 and the mean score drops below `0.80 * 0.9` (i.e., < `0.72`), it logs a drift anomaly, indicating potential issues in hospital availability or model degradation.

---

## 7. DATABASE DESIGN

The system relies on PostgreSQL via SQLAlchemy.

**Schema (`AuditLog`):**
- `case_id` (String, Primary Key, Indexed): UUID correlating the dispatch event.
- `input_payload` (JSON): The exact Request body payload sent by the frontend/caller.
- `output_payload` (JSON): The exact Response object emitted by the dispatch engine.
- `score` (Float): The final top-candidate score, used for evaluating pipeline health.
- `created_at` (DateTime, defaults to UTC now).

**Indexing Logic:**
`case_id` is indexed for rapid retrieval during replay debugging. JSON columns allow schemaless inspection of historical events without requiring costly DB migrations.

**Data Use:**
Replay logic directly queries `audit_logs`. It extracts the `input_payload` and re-runs the current `dispatch_engine` against it. It then extracts `output_payload` to deterministically verify if the newer engine behavior improved or degraded the outcome compared to history.

---

## 8. METRICS SYSTEM

**How Metrics Are Computed:**
Stored entirely in memory via `MetricsStore` inside `services/metrics_service.py`. A simple initialized counter array keeping track of `total` dispatches and a cumulative `total_score`.

**Mean Score Logic:**
Provides a property `mean_score` which simply computes `total_score / total`.

**Failure Distribution:**
Tracks failure strings (e.g., "no_beds") in a `failures` dictionary.

**Limitations:**
1. **Memory Binding:** The metric store loses state instantly upon worker restart/crash.
2. **Global Roll-Up:** It currently calculates a monolithic `mean_score` from the dawn of process uptime. There is no rolling window (e.g., "last 60 minutes"), which means historical bias massively dilutes new anomalies as uptime grows.

---

## 9. REPLAY SYSTEM

**Purpose:**
A testing and validation harness that runs on top of production data.

**How Cases are Retrieved:**
Through `replay_service.py`, leveraging the `case_id` or just querying a time window of `AuditLog` objects.

**Deterministic Recomputation:**
It acts like a sandbox. It feeds the historical `input_payload` straight back into `dispatch_engine.py` (which runs purely in memory). 

**Comparison Logic:**
The replay system compares the "historical chosen hospital" vs "currently chosen hospital" and "historical score" vs "current score". This generates reports indicating if a rule/code change improved outcomes across a massive corpus of historical incidents.

---

## 10. API LAYER

All endpoints served by FastAPI.

- **`POST /dispatch`**
  - *Input*: `DispatchPayload` (lat, lng, condition, severity, vitals, equipment).
  - *Internal Flow*: Validates Pydantic model -> calls `run_dispatch` -> constructs audit object -> adds `_enqueue_audit_log_non_blocking` to background tasks -> answers client.
  - *Outputs*: JSON Object mapping case ID, input, and sorted `hospitals`.
  - *Performance*: Strictly blocking mostly on ETA functions. Extremely fast when ETA cache hits.
  
- **`GET /health`**
  - *Input*: None.
  - *Internal Flow*: Checks Redis `ping()` and DB `SELECT 1`.
  - *Outputs*: dict with status of `api`, `redis`, `db`.
  
- **`GET /metrics`** (Assumed based on routes structure)
  - *Input*: None.
  - *Outputs*: Exposes `metrics.summary()` locally, or queries DB.
  
- **`GET /replay/{id}` / `POST /replay`**
  - *Input*: Case ID / Date range.
  - *Outputs*: Simulated comparison JSON.

---

## 11. FRONTEND DASHBOARD

**Overview:**
React-based web client built with Vite and TailwindCSS for the presentation layer.

**Components (`src/pages/`):**
- `Dispatch.jsx`: Primary interface. Tracks patient condition, collects voice input via `SpeechRecognition` API (which goes to a backend AI analyzer that returns condition + severity + needed equipment), and manually maps required equipment constraints.
- `Result.jsx`: Renders the sorted breakdown of the chosen hospital via `dispatch.py`.
- `Map.jsx` / `HospitalTrack.jsx`: Live tracking visualization.
- `AdminDashboard.jsx` / `HospitalDashboard.jsx`: Metrics rendering interfaces.

**Interaction Flow:**
1. Operator inputs data (or uses `analyzeWithAI` voice feature).
2. React state synchronizes constraint arrays.
3. User clicks "Dispatch Emergency".
4. Axios issues a strict HTTP POST to `/api/dispatch/`.
5. Application forcibly navigates to `Result.jsx` utilizing `react-router-dom` state passing.
6. The UI uses polling arrays (in dashboards) fetching from the `/metrics` API route to draw live graphs.

---

## 12. CONFIGURATION SYSTEM

Using environment variables entirely. 

**Variables:**
- `REDIS_URL`: Endpoint for queueing connections.
- `DATABASE_URL`: Typically a Postgres link `postgresql://user:pass@host/db`.
- `MODEL_SHA256`: Security check to validate model integrity upon instantiation.

**Config Flow:**
`connection.py` directly binds `DATABASE_URL` via `os.getenv`. `redis_client.py` binds `REDIS_URL`.

**Production vs Local:**
Locally, developers might use a SQLite string `audit_logs_test.db`. In production, standard Docker-compose arrays inject the environment variables natively into the backend container.

---

## 13. FAILURE MODES

1. **Redis Down:**
   - *Behavior:* Background queue function `lpush` fails. Exception caught silently. Client gets valid hospital output. No state saved. System silently degrades to memory-leak-free API operation.
2. **Worker Crash:**
   - *Behavior:* Redis fills up (`audit_queue` elongates). The worker must be restarted. Since it's a separate container/process, the API remains unbothered.
3. **Database Failure:**
   - *Behavior:* The `audit_worker` `session.commit()` fails. The db write throws `SQLAlchemyError`. `audit_worker` handles standard retries, but if it's dead, the case is dropped or remains stalled depending on how `brpop` is acknowledged contextually.
4. **API Slowdown / ETA Spikes:**
   - *Behavior:* ML and rules are hyper-fast. The only blocking IO is Haversine and mapping APIs. To combat this, `_ETA_CACHE` natively caches distance routing, preventing cascading failures under load.
5. **Incorrect Scoring / Model Absence:**
   - *Behavior:* The API catches the `FileNotFoundError` or `pickle.UnpicklingError` at boot time and seamlessly enables the deterministic `_fallback_rule_based_score` rules engine. The user notices purely slightly less optimal scoring.

---

## 14. PERFORMANCE CHARACTERISTICS

**Latency:**
Target latency for `/dispatch` API is < 20ms under load due to complete absence of synchronous I/O other than internal cache-lookups.

**Async vs Sync Separation:**
Fast processing (rules, ML inference) executes on the event loop (Sync logic bound locally). Slow processing (writing to persistent volume) entirely stripped from caller timeline. 

**Bottlenecks:**
1. ML Inference times (pickled sklearn/XGBoost models scale linearly with hospital array size).
2. DB size scaling (unindexed JSON query scans in historical `AuditLogs` for reporting dashboards will eventually cause massive latency for the `/replay` endpoint).

---

## 15. SYSTEM GUARANTEES

1. **Non-blocking Dispatch:** The API provides an ironclad guarantee that emergency routing will never drop or block on audit logging DB outages.
2. **Eventual Consistency:** Dispatches made by the system will *eventually* populate the UI metric dashboard once traversing the Redis queue.
3. **Replayability:** Deterministic outputs are guaranteed on exactly matched `input_payloads` provided the ML weights or hospital static catalogs have not changed.
4. **Resiliency:** The system guarantees a route calculation using fallback protocols even if the ML model is deleted or corrupted.

---

## 16. KNOWN LIMITATIONS

*(Brutally honest)*
1. **At-Most-Once Queue Loss:** If Redis is down, we `pass` and swallow the queue command. We lose the audit record entirely. There is no dead-letter queue (DLQ) or retry buffer stored in API memory.
2. **In-Memory Metrics Vaporization:** `MetricsStore` resides purely in worker memory. If the worker container halts, global averages are destroyed and reset to 0. 
3. **No Rolling Window:** Drift detection relies exclusively on an infinite sum limit. In 5 years, `total=10,000,000`, making drift completely statically impossible to trigger, rendering the feature useless at scale.
4. **Polling Driven Front-End:** React relies on Axios polling, causing unnecessary server load compared to a WebSocket/SSE integration.

---

## 17. HOW TO REBUILD FROM SCRATCH

**1. Setup Backend Foundation:**
Start with python, `fastapi`, and `uvicorn`. Create `api/main.py`. Ensure standard route mapping. Instantiate `pydantic` schemas for requests.

**2. Implement Dispatch Logic:**
Build `dispatch_engine.py`. Filter incoming hospitals manually using hard conditions (e.g. `accepting`, `icu_beds`). Calculate rough distance via `haversine` formula. Calculate deterministic degradation weights (`time` vs `survival`). Build tie-breaker functions.

**3. Inject Machine Learning:**
Create `ml_scorer.py`. Take filtered arrays, build 20-feature vectors per hospital. Map into `.pkl` file. Inject fallback rules if `pkl` is missing. 

**4. Build Queue System:**
Create an `async_queue` folder. Initiate a global `redis` client. Build an `lpush` wrapper using pure `try/except` mapping to ensure absolute non-blocking behaviors for the API threads.

**5. Add Worker Layer:**
Create a separate process script (`workers/audit_worker.py`). Set up a permanent `while True` loop utilizing `brpop` to poll the Redis queue. 

**6. Setup Persistent Database:**
Utilize `sqlalchemy`. Construct an ORM linking a `String` ID to `JSON` payload inputs/outputs. Connect the worker layer to directly commit to this Postgres instance after interpreting queue data.

**7. Add Metrics & Observability:**
Inside the worker sequence, intercept the extracted `score`. Call an in-memory python class tracking global aggregations. Integrate a `drift_worker` that monitors this mean against hard thresholds.

**8. Construct Replay Framework:**
Add local API route triggering DB pulls. Pipe fetched DB sequences back into the dispatch engine logic. Compute metric deltas comparing old results vs current local outputs.

**9. Scaffold Frontend:**
Employ `vite` + `react`. Connect API requests using `axios`. Create dynamic forms mapping patient conditions to hardware dependencies (e.g., Cardiac Arrest -> Defibrillator). Build a grid interface sorting outputs utilizing the payload provided natively by the new Dispatch Engine.
