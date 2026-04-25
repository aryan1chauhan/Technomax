# Backend Graph Audit

## Executive Summary

The backend fragmentation shown in `graphify-out/GRAPH_REPORT.md` appears to be **partly real boundary drift and partly Graphify noise**.

The real signal is that the repository currently exposes **multiple parallel backend lanes** for the same concerns:

- API entrypoints in both `backend/app/main.py` and `backend/api/main.py`
- dispatch logic in both `backend/app/engine/dispatch_engine.py` and `backend/core/dispatch_engine.py`
- queue/task code in both `backend/async_queue/tasks.py` and `backend/queue/tasks.py`
- worker packaging in both `backend/worker/` and `backend/workers/`
- database wiring outside the `app` package in `backend/db/connection.py`

That overlap is consistent with the graph report’s high thin-community count: several modules are not just “small,” they sit in **competing ownership zones**.

At the same time, some fragmentation is expected noise. Files such as schema modules (for example `backend/app/schemas/case.py`) and single-purpose task/worker entrypoints will naturally look isolated in static analysis even when they are behaving correctly at runtime.

For Milestone 2 / Phase 6, the safest path is **not** a rewrite. The highest-value work is to **document and enforce one canonical lane**, then add small compatibility shims or deprecation notes around legacy paths.

## Confirmed Boundary/Ownership Problems

1. **Two FastAPI application lanes exist**
   - `backend/app/main.py`
   - `backend/api/main.py`
   These are separate top-level API surfaces, which creates uncertainty about the real production entrypoint, router ownership, middleware registration, and dependency wiring.

2. **Dispatch engine ownership is split**
   - `backend/app/engine/dispatch_engine.py`
   - `backend/core/dispatch_engine.py`
   Even if the implementations are not byte-for-byte duplicates, they represent the same domain concept under different package roots. That is a genuine architectural smell, not just a graph artifact.

3. **Queue responsibility is spread across multiple top-level packages**
   - `backend/async_queue/tasks.py`
   - `backend/queue/tasks.py`
   - `backend/worker/run.py`
   - `backend/workers/__init__.py`
   Task execution, queue registration, and worker bootstrapping are not co-located under one clearly owned namespace.

4. **Database wiring is outside the apparent canonical app tree**
   - `backend/db/connection.py`
   The `backend/app/...` package reads like the current structured application lane, but DB connection code still exists in a parallel top-level directory. That increases the chance of multiple session factories, config drift, or legacy imports surviving unnoticed.

5. **Service-layer ownership is mixed across package roots**
   - `backend/services/audit_service.py`
   - `backend/app/...`
   The repository has both `app`-scoped domain code and top-level `services/`, which makes it unclear whether business logic should live under `backend/app/services`, `backend/services`, or both.

## Suspected Duplication or Parallel Architecture Lanes

These are the most likely “same concept, different era” pairs. They should be treated as **hypotheses to verify**, but the repository shape strongly suggests parallel evolution.

- **API lane**
  - Likely newer/canonical: `backend/app/main.py`
  - Likely older/parallel: `backend/api/main.py`

- **Dispatch/domain lane**
  - Likely newer/canonical: `backend/app/engine/dispatch_engine.py`
  - Likely older/parallel: `backend/core/dispatch_engine.py`

- **Queue lane**
  - Possible split by implementation history rather than deliberate architecture:
    - `backend/async_queue/tasks.py`
    - `backend/queue/tasks.py`

- **Worker lane**
  - `backend/worker/run.py`
  - `backend/workers/`
  The singular vs plural package split is a classic indicator of incremental migration that stopped halfway.

- **Persistence/config lane**
  - `backend/db/connection.py`
  - any DB/session/config wiring under `backend/app/...`
  This should be checked for duplicated engine/session setup and competing environment loading.

## Graphify Noise vs Real Structural Problems

### Mostly real structural problems

- **Parallel package roots for the same concern** (`app`, `api`, `core`, `services`, `db`, `queue`, `worker`, `workers`, `async_queue`) are real repo-organization issues.
- The graph report’s fragmentation around backend orchestration code is likely meaningful because the codebase itself is split across multiple ownership zones.
- Any inferred-edge or knowledge-gap warnings around queue/worker wiring are likely symptoms of actual indirection and parallel entrypoints, not just parser limitations.

### Probably Graphify noise

- **Schema modules** such as `backend/app/schemas/case.py` may appear thin or isolated because Pydantic models are often imported widely but contain little outward logic.
- **Worker bootstrap files** and `__init__.py` modules often look under-connected in static graphs even when runtime usage is correct.
- **Task modules** can look isolated if queue discovery happens through strings, decorators, RQ registration, or CLI startup conventions rather than direct imports.
- Small utility or config files in FastAPI projects commonly become tiny communities without implying a design failure.

### Bottom line

The backend graph is **not mostly noise**. The thin communities are amplified by Graphify’s static view, but the directory layout confirms a real boundary problem: the codebase has not fully converged on one backend namespace.

## Top 5 Low-Risk Improvements

1. **Declare one canonical backend entrypoint in docs**
   - Add a short architecture note identifying whether `backend/app/main.py` or `backend/api/main.py` is the supported FastAPI app.
   - This is the safest immediate win because it reduces operator confusion without changing runtime behavior.

2. **Mark legacy lanes explicitly**
   - Add module docstrings or comments in likely legacy files such as `backend/api/main.py`, `backend/core/dispatch_engine.py`, `backend/db/connection.py`, `backend/queue/tasks.py`, and `backend/workers/__init__.py`.
   - Goal: “legacy/compatibility path; prefer X.”

3. **Create a Phase 6 backend ownership map**
   - One page listing:
     - API layer
     - schemas
     - engine/domain logic
     - services
     - DB/session
     - queue/tasks
     - worker bootstrap
   - This would help prevent new code from being added to the wrong top-level package.

4. **Consolidate imports without moving files yet**
   - Prefer importing dispatch, DB, and task code from the chosen canonical lane only.
   - Defer actual file moves until imports are audited.
   - This reduces future drift while staying compatible with the hackathon-era constraints.

5. **Audit startup and worker commands in Compose/scripts**
   - Verify which app module and which worker runner are actually used by Docker Compose, scripts, or deployment docs.
   - That will identify which directories are truly canonical before any cleanup.

## Canonical vs Legacy Candidates

These are confidence-based candidates, not absolute truth.

### Most likely canonical
- `backend/app/`
  - Reason: it is the most coherent application-style namespace and contains `backend/app/main.py`, `backend/app/engine/dispatch_engine.py`, and `backend/app/schemas/case.py`.
- `backend/app/main.py`
  - Reason: aligns with standard FastAPI app packaging and the more structured `app/...` tree.
- `backend/app/engine/dispatch_engine.py`
  - Reason: domain logic placed under a dedicated engine namespace is more consistent with a maturing app package.

### Most likely legacy or transitional
- `backend/api/main.py`
  - Reason: overlaps directly with `backend/app/main.py`.
- `backend/core/dispatch_engine.py`
  - Reason: overlaps directly with `backend/app/engine/dispatch_engine.py`.
- `backend/db/connection.py`
  - Reason: top-level DB wiring outside the `app` tree suggests pre-consolidation structure.
- `backend/queue/` and `backend/async_queue/`
  - Reason: two task lanes imply either unfinished migration or abandoned experimentation.
- `backend/worker/` and `backend/workers/`
  - Reason: singular/plural duplication strongly suggests drift rather than intentional separation.
- `backend/services/`
  - Reason: may still be active, but from a structural perspective it competes with `backend/app/...` ownership unless clearly documented.

## Recommended Phase 6 Scope

Keep Phase 6 narrow and compatibility-first:

1. **Confirm the canonical runtime path**
   - Determine the official FastAPI entrypoint.
   - Determine the official queue/task module.
   - Determine the official worker bootstrap.

2. **Document backend ownership**
   - Add a short backend architecture note describing where new code must live.
   - Include “do not add new modules under legacy lanes.”

3. **Deprecate, do not rewrite**
   - Leave compatibility files in place if they are still referenced by Compose/scripts/tests.
   - Add explicit comments and migration targets instead of moving everything at once.

4. **Reduce import drift**
   - In follow-up PRs, update imports to prefer the canonical lane whenever a touched file is already being edited for another reason.

5. **Re-run Graphify after documentation/import cleanup**
   - The next graph should show whether fragmentation drops once the repo converges around one namespace, even before any large refactor.

This scope fits Milestone 2 / Phase 6 well: it addresses real structural debt, lowers future confusion, and avoids a risky rewrite under existing project constraints.