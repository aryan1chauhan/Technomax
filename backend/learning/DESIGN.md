# learning DESIGN

## Goals

1. Build a feedback dataset from audited dispatch decisions.
2. Learn safer weight updates automatically over time.
3. Apply updates only when guardrails pass.
4. Keep updates versioned and reversible.

## Non-Goals

1. Replacing dispatch logic.
2. Mutating historical decision records.
3. Introducing non-determinism within a fixed weight version.

## Architecture

```text
audit.decisions
  -> learning.learning_dataset.build_learning_dataset()
		 -> learning/artifacts/learning_dataset.jsonl
  -> learning.weight_trainer.WeightTrainer.train_and_maybe_apply()
		 -> gradient boosting feature-importance derived target weights
		 -> smooth update: 0.8 * old + 0.2 * learned
		 -> guardrails validation on recent replay window
		 -> accepted: apply + version
		 -> rejected: log rejection reason

dispatch_engine._finalize_and_audit()
  -> periodic trigger every 1000 decisions
  -> immediate trigger when drift alerts are present
```

## Core Components

1. `learning_dataset.py`
	- Extracts decision features and metadata from audit logs.
	- Produces JSONL or CSV datasets.

2. `weight_trainer.py`
	- Trains `GradientBoostingRegressor`.
	- Derives candidate weight vector from component feature importances.
	- Applies smoothing and bound clamps.
	- Validates guardrails and writes version/update logs.

3. CLI Entrypoints
	- `learning.train`: manual retraining.
	- `learning.rollback`: version rollback.

## Key Design Decisions

| Date | Decision | Reason | Impact |
|------|----------|--------|--------|
| 2026-04-11 | Use gradient boosting for weight signal extraction | Handles nonlinear feature-quality relationships | Stable learned tendencies from real outcomes |
| 2026-04-11 | Smooth updates (`0.8 old + 0.2 learned`) | Prevent abrupt behavior shifts | Reduced oscillation risk |
| 2026-04-11 | Gate with replay-based validation before apply | Safety-first closed loop | Rejects degrading updates |
| 2026-04-11 | JSONL artifact versioning | Simple append-only traceability | Fast rollback and auditability |

## Guardrails

Candidate weights are rejected unless all checks pass:

1. Candidate mean replay score >= baseline mean replay score.
2. Candidate fallback rate <= baseline fallback rate.
3. Safety violations == 0.

## Constraints and Tradeoffs

1. Fallback-rate simulation uses existing fallback outcomes because weight changes do not alter constraint filters directly.
2. Feature-importance based weight learning is explainable but less expressive than end-to-end policy learning.
3. Update cadence is discrete (per 1000 decisions or drift trigger), not continuously online.

## Security Considerations

1. No external model download or remote execution.
2. Dataset artifacts are local and append-only.
3. Weight rollback ensures quick recovery from bad updates.

## Change Log

### 2026-04-11

1. Added closed-loop dataset builder.
2. Added auto-trainer with smoothing and safety guardrails.
3. Added weight versioning and rollback.
4. Wired periodic and drift-aware retraining into dispatch finalization.
