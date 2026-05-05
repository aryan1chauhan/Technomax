# Load Test Go/No-Go Report

- Profile: baseline
- Verdict: GO

## Dispatch Metrics

- p50: None ms
- p95: 54.6125 ms
- p99: None ms
- HTTP failed rate: 0

## WebSocket Metrics

- Connect success rate: 0.9947089947089947
- Delivery success rate: 1
- Reconnects: 90
- Fanout p95 delay: 29 ms
- Out-of-order frames: 35657
- Dropped frames: 0

## Top 3 Fixes

- Capture per-endpoint traces and DB wait events during peak windows, then tune the top two bottlenecks before rerun.
- Capture per-endpoint traces and DB wait events during peak windows, then tune the top two bottlenecks before rerun.
- Capture per-endpoint traces and DB wait events during peak windows, then tune the top two bottlenecks before rerun.
