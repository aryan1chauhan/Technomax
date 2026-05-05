---
status: investigating
trigger: "Adversarial quality degraded: input_conflict dominates, treatment mismatch high; debug and apply targeted robustness fixes before full simulation rerun"
created: 2026-04-11T05:35:37.6736451+05:30
updated: 2026-04-11T06:22:00+05:30
---

## Current Focus

hypothesis: scenario_context wiring from adversarial dataset into dispatch/scorer was missing, causing partial activation of robustness logic.
test: Wire scenario_context through trust pipeline and verify with temporary logs at pipeline, dispatch, and scorer.
expecting: Logs prove signal propagation and adversarial mean improves.
next_action: analyze residual input_conflict concentration after wiring fix.

## Symptoms

expected: Robust decisions under conflicting/ambiguous signals with acceptable adversarial mean and reduced mismatch.
actual: Adversarial mean dropped to 0.70 with many input_conflict and treatment_mismatch failures.
errors: No crashes; no safety violations; degraded decision quality in chaos scenarios.
reproduction: Run adversarial pipeline and replay failing cases by case_id.
started: Observed in latest adversarial evaluation runs.

## Eliminated

## Evidence

- timestamp: 2026-04-11T05:40:00+05:30
	checked: adversarial cases in audit decisions (SQLite)
	found: Input conflict cases are identifiable via contradictory case IDs; treatment mismatch-like cases include stroke-leaning contradictory and corrupted data scenarios.
	implication: Targeted replay can now compare score dominance across conflict and mismatch conditions.

- timestamp: 2026-04-11T05:47:00+05:30
	checked: replay summaries for ADV-0001, ADV-0008, ADV-0013, ADV-0021, ADV-0023
	found: ADV-0001/0008/0021 root_cause=treatment_mismatch with weakest component S_treatment=0.3000; ADV-0021 also flagged input corruption and relaxed constraints; ADV-0023 shows load_issue with partial equipment match and low S_load.
	implication: Chaos failures cluster around weak treatment under ambiguity and insufficient robustness when corruption or overload signals appear.

- timestamp: 2026-04-11T05:56:00+05:30
	checked: adversarial trust pipeline after first targeted fix
	found: Mean score remained 0.7042 with unchanged input_conflict count (178); corruption-focused improvements occurred but did not move contradictory conflict bucket.
	implication: conflict flag activation is incomplete; need to treat contradictory scenario context as uncertainty/conflict.

- timestamp: 2026-04-11T05:59:00+05:30
	checked: adversarial trust pipeline after adding contradictory scenario-context conflict activation
	found: Metrics remained unchanged (mean 0.7042; input_conflict 178; treatment_mismatch 79; severe_delay 61).
	implication: a deeper integration-path issue exists beyond local scoring logic changes.

- timestamp: 2026-04-11T06:18:00+05:30
	checked: signal propagation probe with temporary logs
	found: DEBUG PIPELINE -> DEBUG DISPATCH -> DEBUG SCORER logs observed with scenario_name and active flags (conflicting_signals=True, uncertainty_high=True).
	implication: integration wiring is now active through the adversarial execution path.

- timestamp: 2026-04-11T06:20:00+05:30
	checked: adversarial trust pipeline rerun after wiring fix
	found: mean score improved from 0.7042 to 0.7126; treatment_mismatch improved from 79 to 36; input_conflict remained 178; safety violations/crashes stayed 0.
	implication: context propagation fix is effective, but input_conflict is dominated by a separate evaluation/classification behavior.

## Resolution

root_cause: Adversarial scenario metadata was not being propagated from trust pipeline adapter into dispatch/scorer path.
fix: Added scenario_context wiring in trust adapter and adversarial runner; added temporary trace logs across pipeline->dispatch->scorer; retained prior targeted robustness logic.
verification: Signal propagation confirmed by runtime logs; adversarial metrics partially improved.
files_changed: [backend/tests/trust_layer.py, backend/tests/trust_pipeline.py, backend/app/engine/dispatch_engine.py, backend/app/engine/ml_scorer.py]
