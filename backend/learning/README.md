# learning

Closed-loop learning and auto-tuning for MediRoute decision scoring weights.

## Overview

This module turns audit data into safe, reversible weight updates.

1. Builds a training dataset from audited decisions.
2. Learns improved weight tendencies with gradient boosting.
3. Applies smoothed updates with strict guardrails.
4. Stores versioned weight history with rollback.

## Components

- `learning_dataset.py`: Extracts `features + label + metadata` from audit logs.
- `weight_trainer.py`: Trains, validates, applies, versions, and rolls back weights.
- `train.py`: Manual training CLI (`python -m learning.train`).
- `rollback.py`: Rollback CLI (`python -m learning.rollback --version <id>`).

## Safety Guardrails

Before applying new weights, the trainer validates on recent decisions and rejects updates unless:

1. Mean replay score does not decrease.
2. Fallback rate does not increase.
3. Safety violations remain zero.

## Runtime Integration

`dispatch_engine.run_dispatch` now triggers learning updates when:

1. `total_decisions % 1000 == 0` (periodic retraining), or
2. drift alerts are produced (immediate drift-aware retraining).

## CLI

```bash
python -m learning.train
python -m learning.rollback --version <version_id>
```

## Artifacts

Generated files are written under `learning/artifacts/`:

- `learning_dataset.jsonl`
- `weight_versions.jsonl`
- `weight_update_log.jsonl`

## Related

- [DESIGN.md](DESIGN.md)
