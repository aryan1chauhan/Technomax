# Frontend Graph Audit

## Executive Summary

The frontend fragmentation shown in `graphify-out/GRAPH_REPORT.md` is currently hard to validate directly because the working tree does **not** contain a populated `frontend/src/` directory. In the current checkout, the strongest frontend signals come from:

- `graphify-out/GRAPH_REPORT.md`
- `.planning/PROJECT.md`
- `.planning/ROADMAP.md`
- `frontend/package.json`
- the absence of on-disk frontend source under `frontend/src/`

Given that constraint, the most defensible conclusion is:

- the graph’s thin frontend communities are **partly likely to be benign React route/component leaf behavior**,
- but the repo also has a **real structural visibility problem** because the expected frontend source tree is missing from the current working copy,
- so any stronger claims about route/component/API coupling would be speculative.

For Milestone 2 / Phase 6, the frontend priority should be **structural clarity and recoverability**, not redesign.

## Confirmed Structural Issues

1. **Frontend source visibility is broken in the current checkout**
   - `frontend/package.json` exists, but `frontend/src/` is empty or absent in the current working tree.
   - That is itself a structural problem: the repo cannot currently support normal frontend review, maintenance, or graph-based boundary analysis from source.

2. **Graph output and filesystem state are out of sync**
   - `graphify-out/GRAPH_REPORT.md` indicates frontend nodes and communities, but the current checkout does not expose the corresponding `frontend/src/` files for verification.
   - This creates audit ambiguity and makes it difficult to distinguish legacy graph residue from current architecture.

3. **The frontend architecture is under-documented relative to project intent**
   - `.planning/PROJECT.md` and `.planning/ROADMAP.md` imply an existing frontend direction and ongoing structural optimization work.
   - Without the source tree present, there is no local canonical reference for route ownership, shared components, or API access patterns.

4. **Phase 6 optimization cannot be executed safely without restoring canonical frontend files**
   - Low-risk cleanup depends on being able to inspect and compare actual route, component, and API modules.
   - In the current state, even small structural recommendations must remain conservative.

## Thin Communities That Are Probably Benign

1. **Route-page leaf nodes in the graph**
   - If the frontend is a normal React Router app, many graph-thin communities around pages would be expected.
   - Page modules often connect mainly through a central app shell and therefore look isolated in import graphs.

2. **Small presentational component communities**
   - Thin communities around status badges, wrappers, and layout primitives are usually normal in React codebases.
   - Graph tools often overstate their isolation because the real reuse value is visual composition, not deep code-level dependency fan-out.

3. **CSS-driven coupling that Graphify undercounts**
   - Even if the frontend uses a shared visual system, graph extraction typically does a weak job representing cross-cutting styling relationships.
   - That means some fragmentation in the report is probably extraction noise rather than architectural failure.

4. **Feature-specific UI islands**
   - Mapping, tracking, or dashboard-like views often form narrow communities naturally because they encapsulate specialized dependencies.
   - Without the source tree present, those should be treated as likely benign until proven otherwise.

## Route/Component/API Connectivity Findings

- **Installed stack is clear even though source is not**
  - `frontend/package.json` confirms a conventional React/Vite stack with React, React Router, Axios, Leaflet, Tailwind, ESLint, and Vitest.
  - That supports the expectation of a standard route/component/API frontend shape.

- **Current direct verification of route composition is not possible**
  - Because `frontend/src/` is not available in the current working copy, route-shell concentration cannot be confirmed from `main.jsx` or `App.jsx`.

- **Current direct verification of shared-component reuse is not possible**
  - The graph suggests component-level fragmentation, but actual shared primitives cannot be validated from disk at this time.

- **Current direct verification of API-lane centralization is not possible**
  - The package stack supports an Axios-based client layer, but there is no on-disk `frontend/src/api/` implementation to inspect in this checkout.

- **Overall assessment of fragmentation**
  - The frontend graph fragmentation is **probably a mix of benign React leaf-node behavior and Graphify extraction limits**, but the more important real issue is that the current repo state does not provide the frontend source needed to validate or safely optimize those boundaries.

## Top 5 Low-Risk Improvements

1. **Restore or confirm the canonical `frontend/src/` tree**
   - Before any Phase 6 cleanup, verify whether the frontend source is missing, excluded, generated elsewhere, or stored on another branch.
   - This is the highest-value low-risk step because it re-enables normal structural work.

2. **Document the canonical frontend entrypoints**
   - Once restored, explicitly identify the expected bootstrap file, app shell, shared component directory, pages directory, and API client location in a short frontend structure note under `.planning/`.

3. **Re-run Graphify after frontend source is confirmed**
   - The current graph cannot be reconciled cleanly against the filesystem.
   - Refreshing the graph after source recovery will separate stale analysis noise from real architecture.

4. **Establish one canonical API access lane**
   - When the source tree is available, confirm that frontend network calls go through a single documented API module rather than page-local request code.

5. **Add a minimal structural test anchor**
   - Once the frontend files are restored, add one app-shell test and one route-level integration test so future graph fragmentation has a clearer architectural baseline.

## Recommended Next Phase Scope for Milestone 2 / Phase 6

Recommended frontend scope for Phase 6:

1. **Repository-state correction first**
   - Treat missing `frontend/src/` visibility as a blocker for structural optimization.
   - Confirm whether this is a checkout issue, a legacy move, or an undocumented alternate location.

2. **Canonical frontend map**
   - After source recovery, document the real locations of:
     - bootstrap entrypoint,
     - route composition,
     - shared UI/layout primitives,
     - page modules,
     - API client/services.

3. **Graph-to-filesystem reconciliation**
   - Compare the refreshed `graphify-out/GRAPH_REPORT.md` against the restored source tree and classify thin communities into:
     - benign React leaves,
     - shared UI primitives,
     - true structural hotspots.

4. **Low-risk boundary cleanup only**
   - Limit work to route-shell thinning, API-lane normalization, and component ownership clarification.
   - Avoid redesigning state management or introducing broad framework changes.

5. **Phase 6 success criterion**
   - By the end of this phase, the frontend should have a visible canonical source tree, a documented composition root, and a graph report that can be meaningfully validated against the actual codebase.

Recommended framing for the parent review: **the current frontend graph fragmentation is less urgent than the frontend source visibility mismatch; Phase 6 should first restore/confirm the canonical frontend tree, then perform small structural cleanups based on a refreshed graph.**