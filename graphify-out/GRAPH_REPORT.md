# Graph Report - C:\Users\ARYAN\OneDrive\Desktop(1)\team tech  (2026-04-18)

## Corpus Check
- 144 files · ~85,966 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1148 nodes · 2215 edges · 87 communities detected
- Extraction: 70% EXTRACTED · 30% INFERRED · 0% AMBIGUOUS · INFERRED: 656 edges (avg confidence: 0.64)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 86|Community 86]]

## God Nodes (most connected - your core abstractions)
1. `SyntheticCaseGenerator` - 55 edges
2. `Availability` - 41 edges
3. `CaseEvent` - 33 edges
4. `score_hospital()` - 32 edges
5. `DecisionType` - 30 edges
6. `CaseInput` - 30 edges
7. `run_dispatch()` - 29 edges
8. `Priority` - 29 edges
9. `Case` - 24 edges
10. `ExpectationLibrary` - 21 edges

## Surprising Connections (you probably didn't know these)
- `User` --calls--> `test_arrived_transition_triggers_fcm()`  [INFERRED]
  C:\Users\ARYAN\OneDrive\Desktop(1)\team tech\backend\app\db\models.py → C:\Users\ARYAN\OneDrive\Desktop(1)\team tech\backend\tests\test_fcm.py
- `User` --calls--> `test_arrived_transition_multiple_hospital_tokens()`  [INFERRED]
  C:\Users\ARYAN\OneDrive\Desktop(1)\team tech\backend\app\db\models.py → C:\Users\ARYAN\OneDrive\Desktop(1)\team tech\backend\tests\test_fcm.py
- `AuditLog` --uses--> `Replay service for decision debugging.`  [INFERRED]
  C:\Users\ARYAN\OneDrive\Desktop(1)\team tech\backend\db\models.py → C:\Users\ARYAN\OneDrive\Desktop(1)\team tech\backend\services\replay_service.py
- `Background workers package (slow path).` --uses--> `WeightTrainer`  [INFERRED]
  C:\Users\ARYAN\OneDrive\Desktop(1)\team tech\backend\workers\__init__.py → C:\Users\ARYAN\OneDrive\Desktop(1)\team tech\backend\learning\weight_trainer.py
- `dispatch.py — Core endpoint for the MediRoute Dispatch ML Pipeline.  Refactored` --uses--> `User`  [INFERRED]
  C:\Users\ARYAN\OneDrive\Desktop(1)\team tech\backend\app\api\endpoints\dispatch.py → C:\Users\ARYAN\OneDrive\Desktop(1)\team tech\backend\app\db\models.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.04
Nodes (59): Base, dispatch_case_factory(), Callable factory for tests that need to control dispatch timing., Apply tie-breaker logic to prevent score collapse.          When two hospitals, Safety layer: ensures downstream ranking/ML never bypasses hard constraints., Run migrations in 'offline' mode., Run migrations in 'online' mode., run_migrations_offline() (+51 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (79): AdversarialCase, _base_hospitals(), _critical_vitals(), generate_adversarial_case(), generate_adversarial_dataset(), _inject_all_overloaded(), _inject_gps_corruption(), _inject_incorrect_labels() (+71 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (46): _base_speed_kmh(), _CaseState, _confidence(), _eta_minutes(), ETAPredictor, ETAUpdate, _fallback_route(), _fetch_ors_route() (+38 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (55): AdversarialCaseGenerator, AutoWeightOptimizer, calculate_decision_quality(), DecisionQualityMetrics, DistributionAlertSystem, DynamicExpectation, generate_all_chaos_cases(), generate_conflicting_symptoms_case() (+47 more)

### Community 4 - "Community 4"
Cohesion: 0.08
Nodes (49): _as_float(), _build_feature_vector(), _clamp(), _coerce_probability(), _condition_group(), _delay_penalty_multiplier(), distance_to_eta_minutes(), _equipment_sets() (+41 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (35): _load_stdlib_queue_module(), Background workers package (slow path)., Replay worker scaffold., Worker entrypoint placeholder., run(), _aggregate_seed_reports(), _comparison(), _load_baseline() (+27 more)

### Community 6 - "Community 6"
Cohesion: 0.09
Nodes (50): build_learning_dataset(), _clamp(), _decision_quality_score(), _extract_root_cause(), load_learning_dataset(), Build structured learning datasets from decision audit logs., Build learning dataset from recent audit entries and write to disk., Load learning dataset rows from JSONL or CSV. (+42 more)

### Community 7 - "Community 7"
Cohesion: 0.06
Nodes (41): BaseModel, CaseEventOut, CaseStatusUpdate, CaseOut, Dispatch(), dispatch_ambulance(), DispatchRequest, DispatchResponse (+33 more)

### Community 8 - "Community 8"
Cohesion: 0.05
Nodes (34): _extract_score_from_output(), Audit persistence helpers backed by SQLAlchemy., store_case(), process_audit(), Audit worker for async queue consumption.  This worker runs on the slow path a, Process queued audit event and persist audit + observability data., _RedisError, run_worker() (+26 more)

### Community 9 - "Community 9"
Cohesion: 0.12
Nodes (45): _apply_behavior_corrections(), _apply_hard_constraints(), _apply_tiebreaker(), _best_effort_rank(), _build_critical_safe_pool(), _categorize_required_equipment(), _classify_fallback_triggers(), _compute_equipment_match_score() (+37 more)

### Community 10 - "Community 10"
Cohesion: 0.09
Nodes (31): Quick validation without async dispatch calls, run_quick_validation(), main(), Test Validation Runner =====================  Execute all 40 cases, assert ex, Execute all 40 test cases, Generate comprehensive validation report, Execute validation harness against dispatch engine, Execute one case through dispatch engine (+23 more)

### Community 11 - "Community 11"
Cohesion: 0.08
Nodes (10): generate(), haversine(), log_normalize_beds(), FIX: Must match ml_scorer.py exactly so training data = inference., make_hospital(), tests/test_ml_scorer.py ----------------------- Pytest suite for the hybrid hosp, TestBuildFeatureVector, TestConditionSeverityMap (+2 more)

### Community 12 - "Community 12"
Cohesion: 0.06
Nodes (19): tests/test_auth.py — Authentication endpoint tests.  Covers: - Successful regist, Login with non-existent email should return 401., Hospital login should include hospital_id in response., Tests for authentication-required endpoints., Accessing dispatch without token should return 401., Accessing cases without token should return 401., Non-admin user should be rejected from admin stats., Admin user should access admin stats. (+11 more)

### Community 13 - "Community 13"
Cohesion: 0.09
Nodes (16): _build_app(), _parse_limit(), tests/test_rate_limits.py ------------------------- Pytest suite for MediRoute, Build an app that keys by IP.  Two different IPs should each get         their, Verify that the correct limit applies to the right route category., 10/minute' -> (10, 'minute'), Build a throwaway FastAPI app with a single GET route decorated with     `limit, All limit strings must be parseable by slowapi. (+8 more)

### Community 14 - "Community 14"
Cohesion: 0.12
Nodes (18): analyze_case(), CaseInput, _categorize_equipment(), get_client(), _has_key(), _is_medical(), _non_medical_response(), normalize_equipment_list() (+10 more)

### Community 15 - "Community 15"
Cohesion: 0.09
Nodes (26): admin_headers(), auth_headers(), client(), db_session(), dispatch_case(), hospital_headers(), Shared test fixtures for MediRoute API test suite. Uses a real test database wit, Helper fixture to dispatch a case safely across any tests. (+18 more)

### Community 16 - "Community 16"
Cohesion: 0.08
Nodes (14): test_dispatch_additions.py  Tests for the enriched DispatchResponse schema. U, Explicitly passing severity override should not crash., triage dict should reflect the submitted condition and severity., Tests for the new enriched DispatchResponse fields., selected_hospital should be a nested object, not a flat field., score_breakdown must contain all four sub-score keys., alternatives must be a list (empty or populated)., Each alternative must include score_breakdown. (+6 more)

### Community 17 - "Community 17"
Cohesion: 0.16
Nodes (11): build_features(), extract_equipment(), generate_dataset(), haversine_distance(), log_normalize_beds(), normalize_distance(), normalize_icu(), Matches ml_scorer._log_normalize_beds exactly. (+3 more)

### Community 18 - "Community 18"
Cohesion: 0.2
Nodes (1): TestScoreHospital

### Community 19 - "Community 19"
Cohesion: 0.26
Nodes (15): calculate_equipment_risk(), calculate_vitals_risk(), clamp(), estimate_survival_time(), evaluate_stability(), normalize_condition_type(), normalize_severity_score(), parse_systolic_bp() (+7 more)

### Community 20 - "Community 20"
Cohesion: 0.17
Nodes (10): get_redis_client(), Redis client scaffold for queue integration., audit_log(), enqueue_audit_log(), _get_conn(), MediRoute — RQ Worker Tasks Fixed version: explicit DATABASE_URL validation, con, Call once at worker startup to verify DB connectivity and schema.     Returns Tr, Open a psycopg2 connection and log the actual host/port/db we landed on.     aut (+2 more)

### Community 21 - "Community 21"
Cohesion: 0.24
Nodes (10): _coerce_float(), _fallback_eta_minutes(), get_eta(), _haversine_km(), Return ETA in minutes using OSRM public API, falling back to haversine., Enable/disable deterministic haversine-only ETA mode for simulations/tests., set_haversine_only_mode(), test_get_eta_falls_back_on_malformed_osrm_payload() (+2 more)

### Community 22 - "Community 22"
Cohesion: 0.25
Nodes (7): generate_graph_json(), generate_mermaid_diagram(), generate_summary_report(), graphify.py - Generate a visual graph of code review findings This creates a st, Generate the review graph as JSON., Generate Mermaid diagram showing issue relationships., Generate a summary report.

### Community 23 - "Community 23"
Cohesion: 0.32
Nodes (5): login(), register(), create_access_token(), hash_password(), verify_password()

### Community 24 - "Community 24"
Cohesion: 0.25
Nodes (0): 

### Community 25 - "Community 25"
Cohesion: 0.47
Nodes (4): _key_func(), rate_limit_exceeded_handler(), app/middleware/rate_limit.py ---------------------------- Centralised rate-lim, Client key for throttling.     - Uses X-Forwarded-For first for reverse-proxy d

### Community 26 - "Community 26"
Cohesion: 0.33
Nodes (2): MetricsStore, In-memory metrics store for observability layer.  Lightweight by design: - No

### Community 27 - "Community 27"
Cohesion: 0.4
Nodes (3): add audit_logs table  Revision ID: a1f3c9e72d04 Revises: 8f3b4b5d9c21 Create Dat, Create audit_logs table (idempotent — safe if hand-created in prior session)., upgrade()

### Community 28 - "Community 28"
Cohesion: 0.4
Nodes (2): Mirrors the worker's audit_log task — if THIS fails, the bug is in task logic., simulate_worker_commit()

### Community 29 - "Community 29"
Cohesion: 0.5
Nodes (1): add case status and events  Revision ID: 64384652098e Revises: b8905846aa73 Crea

### Community 30 - "Community 30"
Cohesion: 0.5
Nodes (1): add hospital_type and has_icu to hospitals  Revision ID: 8f3b4b5d9c21 Revises

### Community 31 - "Community 31"
Cohesion: 0.5
Nodes (1): initial schema  Revision ID: b8905846aa73 Revises:  Create Date: 2026-03-31 05:3

### Community 32 - "Community 32"
Cohesion: 0.5
Nodes (3): Learning worker scaffold., Worker entrypoint placeholder., run()

### Community 33 - "Community 33"
Cohesion: 0.67
Nodes (1): MediRoute — FastAPI application entry point Run with:     uvicorn api.main:app -

### Community 34 - "Community 34"
Cohesion: 0.67
Nodes (2): BaseSettings, Settings

### Community 35 - "Community 35"
Cohesion: 0.67
Nodes (2): Runtime settings scaffold., Settings

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (2): CaseTimeline(), getValidNextTransitionLabel()

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): Run once after first docker compose up:   docker exec mediroute_backend python s

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): Audit API route scaffold (slow-path backed).

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (0): 

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (0): 

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (1): Core dispatch wrapper to preserve validated logic.

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): # NOTE: Features are ALREADY normalized in generate_dataset.py

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (0): 

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (0): 

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (0): 

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (0): 

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (0): 

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (0): 

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (0): 

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (0): 

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (0): 

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (0): 

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (0): 

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (0): 

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (0): 

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (0): 

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (0): 

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (0): 

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (0): 

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (0): 

### Community 61 - "Community 61"
Cohesion: 1.0
Nodes (0): 

### Community 62 - "Community 62"
Cohesion: 1.0
Nodes (1): Accept int (1=low, 2=moderate, 3=critical) or string severity.

### Community 63 - "Community 63"
Cohesion: 1.0
Nodes (0): 

### Community 64 - "Community 64"
Cohesion: 1.0
Nodes (0): 

### Community 65 - "Community 65"
Cohesion: 1.0
Nodes (0): 

### Community 66 - "Community 66"
Cohesion: 1.0
Nodes (0): 

### Community 67 - "Community 67"
Cohesion: 1.0
Nodes (1): 10 cases: cardiac arrest, severe stroke, major trauma

### Community 68 - "Community 68"
Cohesion: 1.0
Nodes (1): 10 cases: survival ≈ ETA, mixed capabilities

### Community 69 - "Community 69"
Cohesion: 1.0
Nodes (1): 10 cases: stable/mild, clear optimal choice

### Community 70 - "Community 70"
Cohesion: 1.0
Nodes (1): 10 cases: equipment missing everywhere, force best-effort

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (1): Generate all 40 test cases

### Community 72 - "Community 72"
Cohesion: 1.0
Nodes (1): Get expectation for a case, or return None if not defined

### Community 73 - "Community 73"
Cohesion: 1.0
Nodes (1): Add/update an expectation

### Community 74 - "Community 74"
Cohesion: 1.0
Nodes (0): 

### Community 75 - "Community 75"
Cohesion: 1.0
Nodes (0): 

### Community 76 - "Community 76"
Cohesion: 1.0
Nodes (0): 

### Community 77 - "Community 77"
Cohesion: 1.0
Nodes (0): 

### Community 78 - "Community 78"
Cohesion: 1.0
Nodes (0): 

### Community 79 - "Community 79"
Cohesion: 1.0
Nodes (0): 

### Community 80 - "Community 80"
Cohesion: 1.0
Nodes (0): 

### Community 81 - "Community 81"
Cohesion: 1.0
Nodes (0): 

### Community 82 - "Community 82"
Cohesion: 1.0
Nodes (0): 

### Community 83 - "Community 83"
Cohesion: 1.0
Nodes (0): 

### Community 84 - "Community 84"
Cohesion: 1.0
Nodes (0): 

### Community 85 - "Community 85"
Cohesion: 1.0
Nodes (0): 

### Community 86 - "Community 86"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **159 isolated node(s):** `graphify.py - Generate a visual graph of code review findings This creates a st`, `Generate the review graph as JSON.`, `Generate Mermaid diagram showing issue relationships.`, `Generate a summary report.`, `Run once after first docker compose up:   docker exec mediroute_backend python s` (+154 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 37`** (2 nodes): `seed.py`, `Run once after first docker compose up:   docker exec mediroute_backend python s`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (2 nodes): `Audit API route scaffold (slow-path backed).`, `audit.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (2 nodes): `database.py`, `get_db()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (2 nodes): `haversine.py`, `calculate_distance()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (2 nodes): `dispatch_engine.py`, `Core dispatch wrapper to preserve validated logic.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (2 nodes): `train_model.py`, `# NOTE: Features are ALREADY normalized in generate_dataset.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (2 nodes): `App()`, `App.jsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (2 nodes): `ProtectedRoute.jsx`, `ProtectedRoute()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (2 nodes): `StatusBadge.jsx`, `StatusBadge()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (2 nodes): `TerminalBox.jsx`, `TerminalBox()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (2 nodes): `TerminalLayout.jsx`, `TerminalLayout()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (2 nodes): `AdminDashboard()`, `AdminDashboard.jsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (2 nodes): `HospitalDashboard.jsx`, `HospitalDashboard()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (2 nodes): `HospitalTrack.jsx`, `HospitalTrack()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (2 nodes): `Login.jsx`, `Login()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (1 nodes): `extract.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `extract2.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `seed_db.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `seed_specialists.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 61`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 62`** (1 nodes): `Accept int (1=low, 2=moderate, 3=critical) or string severity.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 63`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 64`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 65`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 66`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 67`** (1 nodes): `10 cases: cardiac arrest, severe stroke, major trauma`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 68`** (1 nodes): `10 cases: survival ≈ ETA, mixed capabilities`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 69`** (1 nodes): `10 cases: stable/mild, clear optimal choice`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 70`** (1 nodes): `10 cases: equipment missing everywhere, force best-effort`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (1 nodes): `Generate all 40 test cases`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 72`** (1 nodes): `Get expectation for a case, or return None if not defined`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 73`** (1 nodes): `Add/update an expectation`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 74`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 75`** (1 nodes): `run.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 76`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 77`** (1 nodes): `eslint.config.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 78`** (1 nodes): `postcss.config.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 79`** (1 nodes): `tailwind.config.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 80`** (1 nodes): `vite.config.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 81`** (1 nodes): `firebase-messaging-sw.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 82`** (1 nodes): `App.test.jsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 83`** (1 nodes): `firebase.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 84`** (1 nodes): `main.jsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 85`** (1 nodes): `setupTests.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 86`** (1 nodes): `axios.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `score_hospital()` connect `Community 4` to `Community 1`, `Community 18`?**
  _High betweenness centrality (0.084) - this node is a cross-community bridge._
- **Why does `track_case()` connect `Community 0` to `Community 1`, `Community 2`?**
  _High betweenness centrality (0.079) - this node is a cross-community bridge._
- **Why does `update_case_status()` connect `Community 8` to `Community 0`, `Community 1`?**
  _High betweenness centrality (0.079) - this node is a cross-community bridge._
- **Are the 89 inferred relationships involving `str` (e.g. with `metrics()` and `replay()`) actually correct?**
  _`str` has 89 INFERRED edges - model-reasoned connections that need verification._
- **Are the 53 inferred relationships involving `SyntheticCaseGenerator` (e.g. with `DynamicExpectation` and `DecisionQualityMetrics`) actually correct?**
  _`SyntheticCaseGenerator` has 53 INFERRED edges - model-reasoned connections that need verification._
- **Are the 39 inferred relationships involving `Availability` (e.g. with `Run migrations in 'offline' mode.` and `Run migrations in 'online' mode.`) actually correct?**
  _`Availability` has 39 INFERRED edges - model-reasoned connections that need verification._
- **Are the 31 inferred relationships involving `CaseEvent` (e.g. with `Apply tie-breaker logic to prevent score collapse.          When two hospitals` and `Safety layer: ensures downstream ranking/ML never bypasses hard constraints.`) actually correct?**
  _`CaseEvent` has 31 INFERRED edges - model-reasoned connections that need verification._