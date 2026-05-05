"""CLI entrypoint for manual learning retraining.

Run:
  python -m learning.train
"""

from __future__ import annotations

import argparse
import json

from .weight_trainer import WeightTrainer


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and apply safe auto-tuned weights")
    parser.add_argument("--reason", default="manual_cli", help="Reason tag for this training run")
    parser.add_argument("--total-decisions", type=int, default=0, help="Decision count marker for versioning")
    parser.add_argument("--prioritize-recent", action="store_true", help="Bias training toward recent data")
    args = parser.parse_args()

    trainer = WeightTrainer()
    result = trainer.train_and_maybe_apply(
        reason=str(args.reason),
        total_decisions=max(0, int(args.total_decisions)),
        prioritize_recent=bool(args.prioritize_recent),
    )
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
