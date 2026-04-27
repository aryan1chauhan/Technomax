# Load Testing Kit

This folder contains runnable load-testing artifacts for dispatch HTTP and realtime tracking WebSockets.

## What is included

- loadtest/config/profiles.json
  - Baseline, peak, spike, and soak profiles.
- loadtest/k6/dispatch-load.js
  - k6 dispatch load script with auth warmup in setup().
  - Uses Uttarakhand bounded coordinates (lat 29.5-31.5, lng 77.5-80.5).
- loadtest/ws/ws-track-load.mjs
  - Node WebSocket harness with real seeded case IDs.
  - Includes publishers, hospital/ambulance listeners, churn/reconnect, status events, and chat event POSTs.
- loadtest/ws/package.json
  - ws dependency and run scripts.
- loadtest/ops/capture-docker-stats.ps1
  - Soak-time telemetry capture (docker memory/CPU + Postgres connections).
- loadtest/report/build_go_no_go_report.py
  - Generates markdown go/no-go summary from dispatch + WS outputs.
- loadtest/run-load.ps1
  - One-command orchestrator for profile execution.

## Key design choices for reliability

1. Authentication is separated from hot load:
- k6 does token generation in setup(), not per-iteration.
- WS harness pre-creates users/tokens before opening sockets.

2. WebSocket case IDs are always real:
- WS harness seeds cases first via POST /api/dispatch/.
- Only uses returned case_id values for /ws/track/{case_id}.

3. Dispatch payload variation is geographically realistic:
- Coordinates are sampled only inside the configured regional bounding box.

4. Soak memory trend support is explicit:
- capture-docker-stats.ps1 logs container CPU/memory and Postgres connection counts at intervals.

## Prerequisites

- k6 installed and available on PATH.
- Node.js 18+.
- Python 3.10+.
- Backend running and reachable at API_BASE.

## Quick start

Run baseline:

powershell -ExecutionPolicy Bypass -File loadtest/run-load.ps1 -Profile baseline -ApiBase http://localhost:8000

Run peak:

powershell -ExecutionPolicy Bypass -File loadtest/run-load.ps1 -Profile peak -ApiBase http://localhost:8000

Run spike:

powershell -ExecutionPolicy Bypass -File loadtest/run-load.ps1 -Profile spike -ApiBase http://localhost:8000

Run soak (30 minutes):

powershell -ExecutionPolicy Bypass -File loadtest/ops/capture-docker-stats.ps1 -DurationMinutes 30 -IntervalSeconds 15 -OutputPrefix loadtest/results/soak
powershell -ExecutionPolicy Bypass -File loadtest/run-load.ps1 -Profile soak -ApiBase http://localhost:8000

## Output artifacts

- loadtest/results/dispatch-<profile>-timeseries.json
- loadtest/results/dispatch-<profile>-summary.json
- loadtest/results/ws-<profile>-summary.json
- loadtest/results/ws-<profile>-fanout.csv
- loadtest/results/go-no-go-<profile>.md
- loadtest/results/soak-docker-stats.csv
- loadtest/results/soak-pg-connections.csv

## Local vs staging notes

Local:
- Use lower profiles first (baseline).
- Ensure test data exists and backend has enough beds/capacity.

Staging:
- Keep identical scripts but point ApiBase to staging URL.
- Run baseline then peak before spike/soak.
- Keep telemetry capture enabled during soak.
