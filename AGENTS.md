# Agents Overview

This project uses an AI agent architecture for development and automation.

## AI Test Contract

All AI tools working in this repository must use this section as the shared testing language.

### 1) Test Tags

Use one or more tags for every generated test and test plan.

| Tag | Purpose | Typical Paths |
| --- | --- | --- |
| `@unit` | Isolated function/class behavior with minimal dependencies | `backend/tests/test_*.py` |
| `@integration` | Cross-module behavior (DB, queue, API wiring) | `backend/tests/test_dispatch.py`, `backend/tests/test_routing_service.py` |
| `@api` | HTTP contract, status codes, validation, auth | `backend/tests/test_auth.py`, API route tests |
| `@security` | AuthZ/AuthN, rate limits, abuse/misuse vectors | `backend/tests/test_auth.py`, `backend/tests/test_rate_limits.py` |
| `@queue` | Async queue/task semantics, retries, idempotency | `backend/queue/`, `backend/async_queue/` tests |
| `@simulation` | Scenario generation, replay, evaluator behavior | `backend/simulation/`, `backend/tests/test_cases.py` |
| `@adversarial` | Failure-inducing, worst-case and trust-stress scenarios | `backend/tests/adversarial_dataset.py` |
| `@validation` | Determinism, distribution checks, regression harness | `backend/tests/test_validation.py`, `backend/tests/quick_validation_test.py` |
| `@learning` | Training data, rollback, artifact guardrails | `backend/learning/`, `backend/ml_training/` tests |
| `@db` | Model constraints, migrations, persistence behavior | `backend/db/`, `backend/alembic/` tests |
| `@performance` | Runtime/throughput/latency regressions | Simulation and dispatch benchmarks |
| `@regression` | Repro for previously fixed bug; must stay green | Any test file near bug fix |
| `@smoke` | Fast confidence checks for CI gates | `backend/tests/quick_validation_test.py` |

### 2) Mandatory Rules For AI Tools

1. Every code change must map to at least one test tag and at least one concrete test case.
2. For decision/dispatch logic changes, include `@validation` and either `@simulation` or `@adversarial`.
3. For auth, rate-limit, input validation, secrets, or permission changes, include `@security`.
4. For persistence or migration changes, include `@db` plus `@integration`.
5. For queue/task behavior changes, include `@queue` with idempotency and retry assertions.
6. For ML/learning pipeline changes, include `@learning` and regression checks on artifacts/metrics.
7. Each new test must be deterministic: explicit seed, stable fixtures, no wall-clock dependence.
8. If a bug is fixed, add one `@regression` test that fails before fix and passes after.
9. Prefer small, focused tests first (`@unit`) and add integration coverage only where interface boundaries exist.
10. When uncertain, generate the smallest safe test set that still proves correctness and safety.

### 3) Test Case Schema (AI Output Format)

When generating tests, AI tools should provide each test case with this schema:

- `id`: stable identifier (example: `DISPATCH-EDGE-LOWBEDS-001`)
- `tags`: list from the tag table
- `goal`: what behavior is being proven
- `setup`: fixtures, seed, mocks, dataset
- `input`: request payload or function args
- `expected`: exact assertions, invariants, and forbidden outcomes
- `failure_signal`: how the test should fail when behavior regresses

### 4) Required Edge-Case Coverage

AI tools must include edge cases relevant to touched modules:

1. Empty, null, malformed, and type-mismatch input payloads.
2. No viable hospital / no-match scenarios.
3. Bed restoration and stale bed metadata transitions.
4. Equal-score tie situations and tie-breaker stability.
5. Extreme ETA variance, GPS anomaly, and partial telemetry.
6. High load saturation and rapid state changes.
7. Duplicate queue messages, retry storms, and idempotency collisions.
8. Replay determinism: same seed/input must produce stable outcomes.
9. Learning guardrails: candidate model update should not violate safety floor.
10. Auth edge cases: expired token, missing token, invalid scope/role, rate limit boundary.

### 5) Project Test Patterns

Use these patterns consistently across AI-generated tests:

1. Deterministic seed pattern
	- Always pass explicit seed values in simulation/adversarial flows.
2. Safety-floor assertion pattern
	- Assert minimum acceptable score thresholds and disallow unsafe fallbacks.
3. Decision-invariant pattern
	- Assert decision type, destination validity, and reason consistency.
4. Differential regression pattern
	- Compare before/after behavior for known bug classes.
5. Distribution sanity pattern
	- Validate component distribution drift and detect dominance anomalies.
6. Oscillation detection pattern
	- Repeat same input and assert stable output hash/decision.
7. Contract-first API pattern
	- Assert status code, response schema, and error payload shape.
8. Queue resilience pattern
	- Assert retry caps, dead-letter behavior, and deduplicated side effects.
9. Artifact integrity pattern
	- Assert model/hash/log artifacts exist and remain consistent across runs.
10. Minimal-smoke gate pattern
	- Keep a fast smoke subset for confidence checks before full suites.

### 6) Recommended Mapping By Area

- Dispatch engine edits: `@unit`, `@validation`, `@simulation`, `@regression`
- API route edits: `@api`, `@security`, `@integration`
- Queue/task edits: `@queue`, `@integration`, `@regression`
- Learning/training edits: `@learning`, `@validation`, `@performance`
- DB/migration edits: `@db`, `@integration`, `@regression`

### 7) Definition Of Done For AI-Generated Changes

A change is not complete unless all are true:

1. Test tags are declared.
2. At least one happy-path and one edge-case test exists.
3. Regression test is added for bug-fix work.
4. Tests are deterministic and reproducible.
5. Assertions include both expected outcomes and forbidden unsafe outcomes.
