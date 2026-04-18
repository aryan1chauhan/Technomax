"""Queue task scaffold.

This remains lightweight and non-blocking from FAST API callers.
"""

from __future__ import annotations

import json
from typing import Any

from .redis_client import get_redis_client


def enqueue_audit_log(data: dict[str, Any]) -> None:
    client = get_redis_client()
    client.lpush("audit_queue", json.dumps(data, ensure_ascii=True))
