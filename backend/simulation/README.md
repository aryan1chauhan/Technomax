# simulation

Scenario-based validation layer for dispatch intelligence.

## Overview

The simulation module stress-tests the real dispatch engine with structured scenarios that represent critical behavior patterns. It detects failure modes, validates expected decision behavior, and can trigger targeted learning updates when a scenario degrades.

## Features

- Scenario library with standardized metadata: `name`, `priority_type`, `expected_behavior`, and `failure_modes`.
- Deterministic scenario generation using seed-based variability for severity, vitals, and hospital constraints.
- Per-scenario evaluation metrics:
	- `scenario_mean_score`
	- `scenario_failure_rate`
	- `fallback_rate`
	- `correct_behavior_rate`
- Behavior validation rules for cardiac, stroke, trauma, respiratory, and mixed-chaos scenarios.
- Failure intelligence with dominant failure mode, root-cause mapping, mismatch alerts, and worst 5 cases.
- Learning integration that triggers targeted retraining and guarded scenario-weight adjustment when failure exceeds threshold.

## Usage

Run all scenarios:

```bash
python -m simulation.run --seed 42 --cases 100 --failure-threshold 0.10
```

Run selected scenarios only:

```bash
python -m simulation.run --scenario cardiac_emergency --scenario stroke_specialty --cases 80
```

Write JSON output:

```bash
python -m simulation.run --cases 120 --output logs/simulation_report.json
```

## Directory

```text
simulation/
	__init__.py
	scenario_library.py
	scenario_generator.py
	scenario_evaluator.py
	run.py
	README.md
	DESIGN.md
```

## Related

- [Design Doc](DESIGN.md)
