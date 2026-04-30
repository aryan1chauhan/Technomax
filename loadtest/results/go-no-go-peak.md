# Load Test Go/No-Go Report

- Profile: peak
- Verdict: NO-GO

## Dispatch Metrics

- p50: None ms
- p95: 61.341799999999964 ms
- p99: None ms
- HTTP failed rate: 0.004719061480109376

## WebSocket Metrics

- Connect success rate: 0
- Delivery success rate: 0
- Reconnects: 0
- Fanout p95 delay: None ms
- Out-of-order frames: 0
- Dropped frames: 0

## Threshold Failures

- WS connect success rate 0.0000 below 0.99
- WS delivery success rate 0.0000 below 0.99

## Top 3 Fixes

- Increase WebSocket worker capacity and tighten connection churn handling; profile broadcast loop and stale-connection cleanup.
- Capture per-endpoint traces and DB wait events during peak windows, then tune the top two bottlenecks before rerun.
- Capture per-endpoint traces and DB wait events during peak windows, then tune the top two bottlenecks before rerun.
