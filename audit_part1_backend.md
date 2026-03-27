# MediRoute Technical Audit Report - Part 1 (Backend)

## 1. FILE PATH — backend/.env
**PURPOSE:** Stores environment variables including database credentials, JWT secrets, and API keys.
**DEPENDENCIES:** None.
**KEY LOGIC:** Defines key-value pairs for configuration.
**INPUTS & OUTPUTS:** Inputs: System environment or manual edits. Outputs: Strings read by the application.
**INTEGRATION POINTS:** Read by `app/core/config.py` using `pydantic-settings` and by ML scripts via `python-dotenv`.
**KNOWN ISSUES:** Contains sensitive production keys (`SECRET_KEY`, `CLAUDE_API_KEY`). Ensure this file is never committed to version control.
**TEST CASES:**
1. **Load DB URL:** Preconditions: Valid `.env`. Steps: Initialize `Settings`. Expected Result: `DATABASE_URL` is parsed correctly.
2. **Missing Key:** Preconditions: Remove `SECRET_KEY`. Steps: Initialize `Settings`. Expected Result: Pydantic raises a ValidationError.
3. **Optional Key:** Preconditions: Remove `CLAUDE_API_KEY`. Steps: Initialize `Settings`. Expected Result: Parses successfully with `claude_api_key=None`.

## 2. FILE PATH — backend/app/main.py
**PURPOSE:** The main entry point for the FastAPI application that configures middleware, database initialization, and routing.
**DEPENDENCIES:** `fastapi`, `fastapi.middleware.cors`, `app.db`, `app.api.endpoints`.
**KEY LOGIC:** Instantiates the `FastAPI` object, configures CORS, runs SQLAlchemy `create_all()`, and registers all APIRouters. Provides a simple health check `/` route.
**INPUTS & OUTPUTS:** Inputs: HTTP requests. Outputs: JSON responses.
**INTEGRATION POINTS:** Binds all API routes together and connects the application to the database engine.
**KNOWN ISSUES:**
- `allow_origins=["*"]` is overly permissive. In production, this should be restricted to the frontend URL.
- Using `models.Base.metadata.create_all` is okay for hackathons but prevents graceful schema migrations. Use Alembic.
**TEST CASES:**
1. **Health Check:** Preconditions: Server running. Steps: GET `/`. Expected Result: Status 200, Body: `{"status": "MediRoute API is running"}`.
2. **CORS Headers:** Preconditions: Server running. Steps: Send OPTIONS request from `http://example.com`. Expected Result: Response includes `Access-Control-Allow-Origin: *`.
3. **Router Inclusion:** Preconditions: Server running. Steps: GET `/api/hospitals/`. Expected Result: Status 200 or 401/403 (not 404), indicating the route exists.

## 3. FILE PATH — backend/app/core/config.py
**PURPOSE:** Validates and loads environment variables into a strongly-typed configuration object using Pydantic.
**DEPENDENCIES:** `pydantic_settings`.
**KEY LOGIC:** Defines a `Settings` class inheriting from `BaseSettings`. Specifies types for keys and default values for `algorithm` and `access_token_expire_minutes`.
**INPUTS & OUTPUTS:** Inputs: Environment variables. Outputs: A singleton `settings` object.
**INTEGRATION POINTS:** Imported universally (e.g., `security.py`, `database.py`, `ai.py`) to retrieve configuration securely.
**KNOWN ISSUES:** None. Standard dependency injection pattern.
**TEST CASES:**
1. **Instantiate Settings:** Preconditions: Complete `.env`. Steps: Create `Settings()`. Expected Result: Returns object with correctly typed fields.
2. **Default Fallbacks:** Preconditions: `ALGORITHM` absent in `.env`. Steps: Create `Settings()`. Expected Result: `settings.algorithm == "HS256"`.
3. **Type Coercion:** Preconditions: `.env` has `ACCESS_TOKEN_EXPIRE_MINUTES="120"`. Steps: Create `Settings()`. Expected Result: `settings.access_token_expire_minutes` is `int(120)`.

## 4. FILE PATH — backend/app/core/security.py
**PURPOSE:** Handles password hashing, JWT creation, and dependency injection for authenticated users.
**DEPENDENCIES:** `jose`, `passlib`, `fastapi.security`, `app.db.database`, `app.db.models`, `app.core.config`.
**KEY LOGIC:**
- `hash_password` / `verify_password`: Uses bcrypt.
- `create_access_token`: Generates JWTs signed with `SECRET_KEY`.
- `get_current_user`: FastAPI dependency that intercepts the Bearer token, decodes the JWT, extracts the `sub` (email), queries the DB, and returns the User object.
**INPUTS & OUTPUTS:** Inputs: Plaintext passwords, User dicts for tokens, HTTP Authorization headers. Outputs: Hashes, JWT strings, `User` objects.
**INTEGRATION POINTS:** Used by auth routes (for login) and protected routes (as a dependency).
**KNOWN ISSUES:**
- In `get_current_user`, if the user is deleted but the token is unexpired, it throws 401, but there is no mechanism for token revocation (logout is strictly client-side).
**TEST CASES:**
1. **Password Hashing:** Preconditions: None. Steps: Hash "password", verify against "password". Expected Result: Returns True. Verify against "wrong" returns False.
2. **Token Creation:** Preconditions: Valid payload. Steps: Generate token. Expected Result: Decodes correctly with valid `sub` and `exp` claims.
3. **Retrieve User (Valid Token):** Preconditions: Active user, DB session. Steps: Call `get_current_user(token)`. Expected Result: Returns the correct `User` DB object.

## 5. FILE PATH — backend/app/db/database.py
**PURPOSE:** Establishes the connection session to the PostgreSQL database via SQLAlchemy.
**DEPENDENCIES:** `sqlalchemy`, `app.core.config`.
**KEY LOGIC:** Constructs the `engine`, defines a thread-local `SessionLocal` factory, creates the declarative `Base`, and provides a `get_db()` generator dependency for route handlers.
**INPUTS & OUTPUTS:** Inputs: DB credentials. Outputs: SQLAlchemy `Session` objects.
**INTEGRATION POINTS:** Used by `main.py` for schema creation and every API endpoint via `Depends(get_db)`.
**KNOWN ISSUES:**
- Synchronous engine. Fine for typical hackathon load, but limits FastAPI's async concurrency benefits for DB-heavy operations.
**TEST CASES:**
1. **Dependency Yield:** Preconditions: Running DB. Steps: Consume `get_db()`. Expected Result: Yields a valid `Session` object.
2. **Connection Closure:** Preconditions: Consumer finishes. Steps: Inspect generator tear-down. Expected Result: `db.close()` is executed preventing connection leaks.
3. **Invalid URL:** Preconditions: Malformed `DATABASE_URL`. Steps: Attempt connection. Expected Result: Yields predictable operational error on first query.

## 6. FILE PATH — backend/app/db/models.py
**PURPOSE:** Defines the ORM schema mapped to the underlying PostgreSQL tables.
**DEPENDENCIES:** `sqlalchemy`, `app.db.database`.
**KEY LOGIC:** Defines `User`, `Hospital`, `Availability`, and `Case` classes inheriting from `Base`. Maps foreign keys and default values (like `func.now()`).
**INPUTS & OUTPUTS:** N/A (Declarative definitions).
**INTEGRATION POINTS:** Directly manipulated by CRUD operations in endpoint files.
**KNOWN ISSUES:**
- `User.hospital_id` has no cascading delete configured.
- `Case.ambulance_lat`/`lng` is hardcoded to store point-in-time floats rather than utilizing PostGIS which would make spatial queries native.
**TEST CASES:**
1. **User Creation Constraints:** Preconditions: DB setup. Steps: Create two Users with same email. Expected Result: IntegrityError (unique constraint violation).
2. **Default Timestamps:** Preconditions: DB setup. Steps: Insert `Case` missing `created_at`. Expected Result: DB assigns current timestamp automatically.
3. **Foreign Key Integrity:** Preconditions: DB setup. Steps: Insert `Availability` pointing to non-existent `hospital_id`. Expected Result: IntegrityError.

## 7. FILE PATH — backend/app/schemas/user.py
**PURPOSE:** Defines Pydantic validation schemas for user input and output.
**DEPENDENCIES:** `pydantic`, `typing`, `datetime`.
**KEY LOGIC:** Validation for `UserCreate` (ensures role is strictly 'ambulance' or 'hospital' via `Field` descriptions), `UserLogin`, and `UserOut` formatting.
**INPUTS & OUTPUTS:** Validates raw JSON into Pydantic models.
**INTEGRATION POINTS:** Used heavily by `auth.py`.
**KNOWN ISSUES:**
- `role: str = Field(..., description="...")` does *not* enforce the constraint at validation time. It just updates OpenAPI docs. The actual restriction is handled in the route logic.
**TEST CASES:**
1. **Valid UserCreate:** Preconditions: None. Steps: Parse valid dict. Expected Result: Model instantiated successfully.
2. **Invalid Type:** Preconditions: None. Steps: Pass integer as email. Expected Result: ValidationError.
3. **ORM Conversion:** Preconditions: None. Steps: `UserOut.model_validate(orm_obj)`. Expected Result: Correctly serialized JSON dict including `from_attributes=True` behavior.

## 8. FILE PATH — backend/app/schemas/hospital.py
**PURPOSE:** Defines data validation and serialization shapes for hospitals and their availability statuses.
**DEPENDENCIES:** `pydantic`, `typing`, `datetime`.
**KEY LOGIC:** `HospitalBase`, `AvailabilityUpdate`, `AvailabilityOut`. Includes nested schema `HospitalOut` referencing `AvailabilityOut`.
**INPUTS & OUTPUTS:** Validates incoming array updates and formats outgoing DB models.
**INTEGRATION POINTS:** Defines payloads for `/api/hospitals` routes.
**KNOWN ISSUES:** None.
**TEST CASES:**
1. **Nested Serialization:** Preconditions: None. Steps: Validate `HospitalOut` with an embedded `availability` dict. Expected Result: Correctly structures nested objects.
2. **Missing Optional Field:** Preconditions: None. Steps: Validate `HospitalOut` missing `availability`. Expected Result: Parsed successfully with `availability=None`.
3. **Strict Array Typing:** Preconditions: None. Steps: Pass `equipment="string"` instead of `["string"]` into `AvailabilityUpdate`. Expected Result: ValidationError.

## 9. FILE PATH — backend/app/schemas/dispatch.py
**PURPOSE:** Validates incoming dispatch requests and structures the complex API response back to the client.
**DEPENDENCIES:** `pydantic`, `typing`, `datetime`.
**KEY LOGIC:** `DispatchRequest` takes lat/lng and condition. `DispatchResponse` maps out ML reasoning, matched equipment, and scores. `CaseOut` formats historical case data.
**INPUTS & OUTPUTS:** HTTP body validation and response serialization.
**INTEGRATION POINTS:** Used primarily by `app/api/endpoints/dispatch.py` and `cases.py`.
**KNOWN ISSUES:** None.
**TEST CASES:**
1. **Valid Dispatch Request:** Preconditions: None. Steps: Validate standard request. Expected Result: Success.
2. **Extraneous Fields:** Preconditions: None. Steps: Pass extra fields. Expected Result: Success (ignored by default).
3. **Response Serialization:** Preconditions: Mismatched list types. Steps: Return float instead of list for `equipment_missing`. Expected Result: ValidationError.

## 10. FILE PATH — backend/app/engine/haversine.py
**PURPOSE:** Calculates the great-circle distance between two GPS coordinates in kilometers.
**DEPENDENCIES:** `math`.
**KEY LOGIC:** Implements standard spherical trigonometry haversine formula with Earth's radius configured as 6371.0 km.
**INPUTS & OUTPUTS:** Inputs: `lat1, lon1, lat2, lon2` (floats). Output: `distance_km` (float, rounded to 2 decimals).
**INTEGRATION POINTS:** Scorer logic, ML inference fallback, dataset generation scripts.
**KNOWN ISSUES:** Calculations assume a perfect sphere and straight-line paths. Driving distance (ETA) later calculated as simply (dist / 40kmph) * 60, which ignores road networks.
**TEST CASES:**
1. **Zero Distance:** Preconditions: None. Steps: Calculate distance between identical points. Expected Result: `0.0`.
2. **Known Distance:** Preconditions: None. Steps: Calculate dist from Dehradun to Roorkee coordinates. Expected Result: Approximately correct real-world straight-line distance.
3. **Negative Coordinates:** Preconditions: None. Steps: Calculate distance across equator/prime meridian. Expected Result: Correct positive distance.

## 11. FILE PATH — backend/app/engine/scorer.py
**PURPOSE:** The fallback rule-based hospital scoring engine.
**DEPENDENCIES:** `app.engine.haversine`.
**KEY LOGIC:** `score_hospital` combines availability, distance, and equipment match into a weighted sum `(0.4A + 0.35D + 0.25E)`. Returns None if `accepting=False` or `beds=0`.
**INPUTS & OUTPUTS:** Maps list of raw hospital dicts into a ranked list, returning the top match.
**INTEGRATION POINTS:** Called by `ml_scorer.py` as a fallback mechanism if the ML model fails to load.
**KNOWN ISSUES:**
- `score_hospital` divides by 10 to normalize beds (`min(beds/10, 1.0)`). A hospital with 10 beds maxes out this score, effectively treating a tiny clinic identical to a super-specialty hospital for capacity scale.
**TEST CASES:**
1. **Score Zero Capacity:** Preconditions: Hospital with 0 beds. Steps: `score_hospital`. Expected Result: Returns `None`.
2. **Score Decline Rule:** Preconditions: Hospital `accepting=False`. Steps: `score_hospital`. Expected Result: Returns `None`.
3. **Equipment Match Calculation:** Preconditions: Need ["A", "B"], Has ["A"]. Steps: `score_hospital`. Expected Result: `equipment_score = 0.5`.

## 12. FILE PATH — backend/app/engine/ml_scorer.py
**PURPOSE:** Loads the trained scikit-learn model and executes inference to find the optimal hospital.
**DEPENDENCIES:** `pickle`, `os`, `numpy`, `app.engine.haversine`.
**KEY LOGIC:**
- Tries to unpickle an XGBoost/RandomForest model file on import.
- Maps patient `condition` string to a 1-3 severity scale.
- Builds a 15-dimensional feature vector for each candidate hospital.
- Computes `predict_proba`. Applies scaling around the computed optimal `_threshold` to keep scores strictly ordered between 0-0.5 and 0.5-1.0.
- Falls back to `_rule_fallback` if model fails to load.
**INPUTS & OUTPUTS:** Inputs: raw variables from the request (lat/lng, condition, hospital list). Outputs: A fully hydrated "best" hospital dict with reasoning appended.
**INTEGRATION POINTS:** Directly invoked during POST `/api/dispatch/`.
**KNOWN ISSUES:**
- Global state `_model` initialized at import time. Could cause blocking I/O unpickling 5MB file on worker startup.
- Feature extraction logic (e.g., `min(beds/30, 1.0)`) is replicated exactly from the training generation script, creating a fragile coupling (Feature Drift risk).
**TEST CASES:**
1. **Valid Prediction:** Preconditions: Valid model loaded. Steps: Call `predict_best_hospital` with typical variables. Expected Result: Yields a dict containing `ml_reasoning` and a floating `final_score`.
2. **Missing Model Fallback:** Preconditions: Delete `hospital_model.pkl`. Steps: Start app, call `predict`. Expected Result: Functions normally, outputting a valid dict scored by `_rule_fallback`.
3. **Empty Hospital Pool:** Preconditions: Pass empty `hospitals` list. Steps: Call `predict`. Expected Result: Returns `None`.

## 13. FILE PATH — backend/app/api/endpoints/auth.py
**PURPOSE:** Routes for User registration and JWT-based Login.
**DEPENDENCIES:** FastAPI, SQLAlchemy, core security, schemas.
**KEY LOGIC:**
- `/register`: Verifies email unique, hashes password, saves to DB. Verifies role is within allowed set ("ambulance", "hospital", "admin").
- `/login`: Looks up user, verifies hash, mints and returns access token payload containing `sub`, `role`, and `hospital_id`.
**INPUTS & OUTPUTS:** Takes credentials payloads, provides JSON messages or JWT tokens.
**INTEGRATION POINTS:** Accessed globally by frontend clients.
**KNOWN ISSUES:**
- Lacks rate-limiting, making it vulnerable to brute-force authentication attacks.
**TEST CASES:**
1. **Successful Reg:** Preconditions: Clean DB. Steps: POST valid payload with role "ambulance". Expected Result: 201 Created.
2. **Invalid Role:** Preconditions: Clean DB. Steps: POST with role "doctor". Expected Result: 400 Bad Request.
3. **Successful Login:** Preconditions: Valid credentials. Steps: POST login. Expected Result: 200 OK with `access_token` and `token_type` body.

## 14. FILE PATH — backend/app/api/endpoints/hospitals.py
**PURPOSE:** Routes for listing available hospitals and updating their dynamic capacities.
**DEPENDENCIES:** FastAPI, SQLAlchemy, core security context.
**KEY LOGIC:**
- `/`: Public/User route. Joins `Hospital` mapping data to the *latest* `Availability` row via `.order_by(desc)` subquery logic.
- `/{id}/availability`: Protected (hospital role only). UPSERT pattern: finds existing availability row, updates it. If missing, inserts fresh.
**INPUTS & OUTPUTS:** JSON lists of hospitals & stats, JSON body for updates.
**INTEGRATION POINTS:** Consumed by Map and Dispatch frontends, updated by Hospital Dashboard frontend.
**KNOWN ISSUES:**
- N+1 query issue in GET `/`. `db.query(Hospital).all()` followed by a loop querying `Availability` for *every* hospital individually. Severely degrades performance with large numbers of hospitals.
- BOLA Vulnerability: `update_availability` does not check if `current_user.hospital_id == hospital_id`. ANY authenticated hospital account can modify ANY OTHER hospital's availability data.
**TEST CASES:**
1. **Get All Hospitals:** Preconditions: Seeded DB. Steps: GET `/api/hospitals/`. Expected Result: Array of hospital objects containing nested `availability` dictionaries.
2. **Unauthorized Update:** Preconditions: Context is 'ambulance' role. Steps: PUT to update route. Expected Result: 403 Forbidden ("Only hospital accounts...").
3. **Upsert Functionality:** Preconditions: Context is 'hospital' role. Steps: PUT update to assigned hospital. Expected Result: `updated_at` changes in DB, response is 200 OK.

## 15. FILE PATH — backend/app/api/endpoints/dispatch.py
**PURPOSE:** The core business logic endpoint orchestrating ambulance case creation and intelligent routing.
**DEPENDENCIES:** FastAPI, SQLAlchemy, `predict_best_hospital` from ML engine.
**KEY LOGIC:**
- Validates user role ('ambulance').
- Fetches all hospitals and their latest availability statuses.
- Passes array of structured hospital dictionary representations to the ML Scoring Engine.
- If match found, persists a new `Case` record to PostgreSQL containing the binding (Ambulance <-> Hospital) and calculated metrics (ETA, Score, Dist).
**INPUTS & OUTPUTS:** Inputs: `DispatchRequest` (Condition, location). Outputs: `DispatchResponse` (Highly detailed routing instruction).
**INTEGRATION POINTS:** Connects UI (`Dispatch.jsx`) to ML (`ml_scorer.py`) and DB (`cases`).
**KNOWN ISSUES:**
- Suffers the exact same N+1 query performance bottleneck as `hospitals.py` when building the candidate pool.
**TEST CASES:**
1. **Successful Dispatch:** Preconditions: Valid hospitals in DB, Ambulance user. Steps: POST valid case. Expected Result: 200 OK, returns `DispatchResponse` with `case_id`.
2. **No Suitable Hospital:** Preconditions: All hospitals `accepting=False`. Steps: POST valid case. Expected Result: 404 Not Found ("No suitable hospital found").
3. **Role Validation:** Preconditions: Auth as 'hospital'. Steps: POST case. Expected Result: 403 Forbidden.

## 16. FILE PATH — backend/app/api/endpoints/cases.py
**PURPOSE:** Retrieve historical and active tracking data for dispatches.
**DEPENDENCIES:** FastAPI, SQLAlchemy aggregations (`func`, `desc`).
**KEY LOGIC:**
- `/`: Fetches all historical cases logged by the current user (ambulance).
- `/hospital`: Limits retrieval to cases assigned to the user's `hospital_id` created within the last 24 hours.
- `/admin/stats`: Heavy aggregation route. Sums beds, groups by lat boundaries to simulate districts, and pulls the 15 most recent cases globally.
**INPUTS & OUTPUTS:** GET requests returning array of `CaseOut` objects or aggregated stats dict.
**INTEGRATION POINTS:** Admin Dashboard, Hospital Dashboard.
**KNOWN ISSUES:**
- `/admin/stats`: The `district_map` hardcodes primary key IDs (`"id_min": 66, "id_max": 92`). If DB seeds change IDs or new hospitals are added, this entire admin block breaks silently or returns nonsense data. It should group by a `district` column on the Hospital table instead.
**TEST CASES:**
1. **Ambulance Case History:** Preconditions: Authenticated as amb1. Steps: GET `/`. Expected Result: Array of their previous cases sorted by desc.
2. **Hospital Recent Cases:** Preconditions: Authenticated as hosp. Steps: GET `/hospital`. Expected Result: Only cases mapped to their `hospital_id` within 24h.
3. **Admin District Stability:** Preconditions: Auth as admin. Steps: GET `/admin/stats`. Expected Result: Responds with correctly summed aggregates, verifying the fragile ID mapping hasn't broken.

## 17. FILE PATH — backend/app/api/endpoints/tracking.py
**PURPOSE:** Real-time bi-directional WebSocket connection for broadcasting ambulance coordinates.
**DEPENDENCIES:** FastAPI `WebSocket`, `WebSocketDisconnect`.
**KEY LOGIC:**
- `ConnectionManager`: Statefully holds active socket connections in memory, grouped by `case_id` into distinct dictionaries (`ambulance_connections`, `hospital_connections`).
- `ws/ambulance/{case_id}`: Ambulance pushes data in infinite loop, `forward_location` beams it immediately to matching hospital socket.
- `ws/hospital/{case_id}`: Hospital maintains passive listening socket just to receive pushed data.
**INPUTS & OUTPUTS:** WebSocket streams containing JSON (`{lat, lng, eta_minutes}`).
**INTEGRATION POINTS:** Connects `Map.jsx` (sender) directly to `HospitalTrack.jsx` (receiver).
**KNOWN ISSUES:**
- In-memory state. If the backend scales to multiple processes/workers (e.g. Uvicorn with >1 worker), WebSockets connected to different workers will not be able to talk to each other. Requires a Redis Pub/Sub backplane for production.
- Broad access: Any client can connect to any `case_id` socket; no JWT token validation is performed during handshake setup.
**TEST CASES:**
1. **Connection Lifecycle:** Preconditions: Server running. Steps: Connect client A as ambulance to case 1, client B as hosp to case 1. Expected Result: Handled without disconnects.
2. **Cross-Talk Verification:** Preconditions: Clients active. Steps: Client A sends coord payload. Expected Result: Client B receives exact JSON payload immediately. Client C listening on case 2 receives nothing.
3. **Graceful Disconnect:** Preconditions: Clients active. Steps: Terminate Client A. Expected Result: Exception caught internally, dictionary cleaned, Client B remains open.

## 18. FILE PATH — backend/app/api/endpoints/ai.py
**PURPOSE:** Exposes a Claude 3 Haiku integration to enhance the dispatch engine via natural language processing of unstructured case text.
**DEPENDENCIES:** `anthropic`, `fastapi`, `app.core.config`.
**KEY LOGIC:**
- Pre-screens input with a fast Rule Engine to set base severity.
- Calls Anthropics Claude 3 Haiku, passing the raw input and rule-base context, demanding a strict JSON output matching the expected format.
- Normalizes parsed equipment names using a strict dictionary mapping (e.g. "brain scan" -> "ct_scan") to align with database enum schemas.
**INPUTS & OUTPUTS:** Inputs: raw unstructured voice transcription or typed text string. Outputs: normalized JSON payload with conditions and equipment lists ready.
**INTEGRATION POINTS:** An auxiliary endpoint that could be consumed by a hypothetical mobile app voice transcription feature.
**KNOWN ISSUES:**
- Vulnerable to prompt injections disguised as patient cases (e.g., "Ignore all previous instructions...").
- Hard fails to 500 error if Claude returns malformed JSON despite prompt instructions.
**TEST CASES:**
1. **Valid Analysis:** Preconditions: Valid Claude API key. Steps: POST "Patient collapsed, grabbing chest." Expected Result: Returns condition="cardiac arrest", severity="CRITICAL", equipment=["defibrillator"].
2. **No API Key:** Preconditions: Remove `.env` key. Steps: POST case. Expected Result: 500 Internal Server error ("CLAUDE_API_KEY is not configured in .env").
3. **Normalization Override:** Preconditions: Valid key. Steps: POST "Need a heart monitor and oxygen". Expected Result: Normalizes to `ecg` and `ventilator`.

## 19. FILE PATH — backend/ml_training/generate_synthetic.py
**PURPOSE:** Seeds the database with hundreds of synthetic case dispatches pointing to various hospitals for dataset creation.
**DEPENDENCIES:** `sqlalchemy`, `random`, `dotenv`.
**KEY LOGIC:**
- Sweeps through 20 different condition profiles. For each profile, randomly places an ambulance inside bounding box coordinates of 5 known districts.
- Evaluates the "optimal" pseudo-choice using a rudimentary weighted formula adding chaotic noise (`random.uniform(-0.05, 0.05)`).
- Bulk inserts the chosen dispatch events into the `cases` Postgres table as `user_id = 4`.
**INPUTS & OUTPUTS:** Interacts directly with PostgreSQL via raw SQL strings.
**INTEGRATION POINTS:** First step in the isolated 3-step ML pipeline.
**KNOWN ISSUES:**
- Drops all `user_id = 4` records on every run. Fragile hardcoded ID dependency.
**TEST CASES:** N/A (Offline pipeline script).

## 20. FILE PATH — backend/ml_training/generate_dataset.py
**PURPOSE:** Transforms the raw SQL historical case logs into a flattened CSV format suitable for Random Forest training, implementing hard-negative sampling.
**DEPENDENCIES:** `pandas`, `sqlalchemy`, `dotenv`.
**KEY LOGIC:**
- Iterates over every dispatch. The assigned hospital becomes the Positive (`was_selected=1`).
- Samples 7 Negative hospitals (`was_selected=0`). Crucially, intentionally biases towards *nearby* but *incorrect* hospitals to force the ML model to learn complex feature separations rather than just picking "lowest distance".
- Outputs raw features (15 items) and binary label to `training_data.csv`.
**INPUTS & OUTPUTS:** Input: SQL DataFrames. Output: `training_data.csv`.
**INTEGRATION POINTS:** Bridge between DB and SKLearn pipeline.
**KNOWN ISSUES:**
- Feature building logic (`build_features`) must exactly match the feature extraction logic deployed in `ml_scorer.py`. High coupling penalty leading to silent drifts in production if one is updated but not the other.
**TEST CASES:** N/A (Offline pipeline script).

## 21. FILE PATH — backend/ml_training/train_model.py
**PURPOSE:** Trains, tunes, evaluates, and serializes the Sklearn ML pipeline.
**DEPENDENCIES:** `pandas`, `sklearn`, `numpy`, `pickle`.
**KEY LOGIC:**
- Fits a `RandomForestClassifier` with `class_weight="balanced"`.
- Loops through thresholds (0.1 to 0.9) to dynamically find the decision boundary maximizing the F1 score against the validation set.
- Pickles a dictionary containing the model artifact, tuned threshold, and explicitly ordered list of feature column strings.
**INPUTS & OUTPUTS:** Input: CSV file. Output: `hospital_model.pkl`.
**INTEGRATION POINTS:** Generates the artifact consumed by `ml_scorer.py`.
**KNOWN ISSUES:**
- Overwriting the model file in-place (`hospital_model.pkl`) provides no versioning mechanism. Model rollback is impossible.
**TEST CASES:** N/A (Offline pipeline script).
