"""Closed-loop learning and auto-tuning utilities."""

from .learning_dataset import build_learning_dataset, load_learning_dataset
from .weight_trainer import (
    WeightTrainer,
    apply_scenario_weight_adjustment,
    get_active_weights,
    get_recent_weight_updates,
    get_weight_versions,
    rollback_to_version,
    run_targeted_learning_update,
    run_periodic_learning_update,
)

__all__ = [
    "build_learning_dataset",
    "load_learning_dataset",
    "WeightTrainer",
    "get_active_weights",
    "apply_scenario_weight_adjustment",
    "get_weight_versions",
    "get_recent_weight_updates",
    "rollback_to_version",
    "run_targeted_learning_update",
    "run_periodic_learning_update",
]
