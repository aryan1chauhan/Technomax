"""Queue package for slow-path tasks.

This package intentionally preserves stdlib ``queue`` compatibility because the
project root is on ``sys.path`` and would otherwise shadow Python's stdlib
module named ``queue``.
"""

from __future__ import annotations

import importlib.util
import sysconfig
from pathlib import Path


def _load_stdlib_queue_module():
    stdlib_path = Path(sysconfig.get_paths()["stdlib"]) / "queue.py"
    spec = importlib.util.spec_from_file_location("_stdlib_queue", str(stdlib_path))
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load stdlib queue module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_stdlib_queue = _load_stdlib_queue_module()

Empty = _stdlib_queue.Empty
Full = _stdlib_queue.Full
Queue = _stdlib_queue.Queue
LifoQueue = _stdlib_queue.LifoQueue
PriorityQueue = _stdlib_queue.PriorityQueue
SimpleQueue = getattr(_stdlib_queue, "SimpleQueue", None)

__all__ = [
    "Empty",
    "Full",
    "Queue",
    "LifoQueue",
    "PriorityQueue",
    "SimpleQueue",
]
