"""Async queue task enqueuers.

Failure-safe contract:
- Queue failures must never break FAST API responses.
"""

from __future__ import annotations

import json
from typing import Any

from redis.exceptions import RedisError

from .redis_client import redis_client


def enqueue_audit_log(data: dict[str, Any]) -> None:
    try:
        redis_client.lpush("audit_queue", json.dumps(data, ensure_ascii=True))
    except (RedisError, OSError, RuntimeError, ValueError, TypeError, KeyError):
        # API path must remain non-blocking and failure-safe.
        pass
