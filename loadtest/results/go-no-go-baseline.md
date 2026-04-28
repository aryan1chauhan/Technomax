# Load Test Go/No-Go Report

- Profile: baseline
- Verdict: NO-GO

## Dispatch Metrics

- p50: None ms
- p95: 3445.607649999998 ms
- p99: None ms
- HTTP failed rate: 0

## WebSocket Metrics

- Connect success rate: 0.8202247191011236
- Delivery success rate: 1
- Reconnects: 29
- Fanout p95 delay: 8 ms
- Out-of-order frames: 17679
- Dropped frames: 0

## Threshold Failures

- Dispatch p95 latency 3445.607649999998ms exceeded limit 800ms
- WS connect success rate 0.8202 below 0.99

## Top 3 Fixes

- Scale API workers and tune DB pool size; validate dispatch query/index plans under load.
- Increase WebSocket worker capacity and tighten connection churn handling; profile broadcast loop and stale-connection cleanup.
- Capture per-endpoint traces and DB wait events during peak windows, then tune the top two bottlenecks before rerun.
