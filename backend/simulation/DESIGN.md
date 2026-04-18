# simulation Design

## Goals

- Validate dispatch behavior against high-risk scenario families using the real dispatch engine.
- Produce actionable scenario intelligence: metrics, mismatch alerts, worst-case examples, and root-cause labeling.
- Trigger targeted learning updates when scenario failures exceed threshold.

## Non-Goals

- Replacing production dispatch scoring logic.
- Persisting scenario data in a separate database.
- Real-time online training in request path.

## Architecture

```text
scenario_library -> scenario_generator -> run_dispatch (real engine) -> scenario_evaluator
			 |                    |                         |                     |
			 |                    |                         |                     +-> failure analysis
			 |                    |                         |                     +-> behavior validation
			 |                    |                         |                     +-> worst-case extraction
			 |                    |                         |
			 |                    |                         +-> audit + learning hooks (already in engine)
			 |                    |
			 +-> expected behavior + failure modes

scenario_evaluator --(failure_rate > threshold)--> run_targeted_learning_update
```

## Core Components

- `scenario_library.py`
	- Defines structured scenario templates and metadata.
	- Provides lookup and listing helpers.
- `scenario_generator.py`
	- Generates deterministic synthetic cases using seed and controlled perturbations.
	- Produces dispatch-compatible payloads.
- `scenario_evaluator.py`
	- Executes generated cases through `run_dispatch`.
	- Computes per-scenario metrics and validates behavior rules.
	- Performs failure-mode and root-cause analysis.
	- Triggers targeted learning when scenario degradation crosses threshold.
- `run.py`
	- CLI driver for full simulation reports and optional JSON output.

## Behavioral Rules

- `cardiac_emergency`: enforce time-critical + stabilization logic.
- `stroke_specialty`: require stroke/neuro capability alignment.
- `trauma_stabilization`: prefer stabilization-first when unstable and transfer is long.
- `respiratory_failure`: enforce required-equipment compatibility.
- `mixed_chaos`: require safe constraint handling under contradictory signals.

## Key Decisions

| Date | Decision | Rationale | Impact |
|------|----------|-----------|--------|
| 2026-04-10 | Use real `run_dispatch` instead of test stubs | Preserves production behavior fidelity | Higher confidence in scenario findings |
| 2026-04-10 | Seeded deterministic generation | Reproducible evaluations and regressions | Repeatable CI and local diagnostics |
| 2026-04-10 | Trigger targeted learning via threshold | Converts simulation failures into adaptation signal | Safe feedback loop with guardrails |

## Constraints and Trade-Offs

- Scenario labeling is synthetic and currently not persisted into training dataset schema.
- ETAs may rely on cached/fallback routing behavior from existing engine services.
- Behavior checks use rule-based validation by scenario type, not a learned oracle.

## Security Considerations

### Threats

- Scenario payload tampering could bias evaluation outcomes.
- Unbounded simulation volume could generate operational load spikes.

### Controls

- Input normalization is delegated to existing dispatch engine validators.
- CLI exposes bounded case counts and deterministic seed controls.
- Learning updates remain guardrail-gated by existing trainer validation.

## Change Log

- 2026-04-10
	- Implemented scenario library, generator, evaluator, and CLI runner.
	- Added behavior mismatch alerts, failure analysis, and worst-case extraction.
	- Added integration to trigger targeted learning and scenario-specific guarded weight adjustment.
