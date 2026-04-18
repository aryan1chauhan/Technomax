"""CLI entrypoint for weight version rollback.

Run:
  python -m learning.rollback --version <id>
"""

from __future__ import annotations

import argparse
import json

from .weight_trainer import rollback_to_version


def main() -> None:
    parser = argparse.ArgumentParser(description="Rollback active weights to a saved version")
    parser.add_argument("--version", required=True, help="Version id to rollback to")
    args = parser.parse_args()

    result = rollback_to_version(str(args.version))
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
