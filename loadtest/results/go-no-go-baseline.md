# Load Test Go/No-Go Report

- Profile: baseline
- Verdict: NO-GO

## Dispatch Metrics

- p50: None ms
- p95: 60000.65037 ms
- p99: None ms
- HTTP failed rate: 0.9845360824742269

## WebSocket Metrics

- Connect success rate: 0
- Delivery success rate: 0
- Reconnects: 0
- Fanout p95 delay: None ms
- Out-of-order frames: 0
- Dropped frames: 0

## Threshold Failures

- Dispatch p95 latency 60000.65037ms exceeded limit 800ms
- HTTP non-2xx rate 0.9845360824742269 exceeded limit 0.01
- WS connect success rate 0.0000 below 0.99
- WS delivery success rate 0.0000 below 0.99

## Top 3 Fixes

- Scale API workers and tune DB pool size; validate dispatch query/index plans under load.
- Audit 4xx/5xx mix by endpoint and status code; separate auth warmup from hot path and raise dispatch quotas only for load environments.
- Increase WebSocket worker capacity and tighten connection churn handling; profile broadcast loop and stale-connection cleanup.
