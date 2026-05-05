"""Redis client for async queue operations."""

from __future__ import annotations

import importlib
import os


def _build_redis_client():
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise RuntimeError("REDIS_URL is not configured")

    redis_module = importlib.import_module("redis")
    redis_cls = getattr(redis_module, "Redis")
    return redis_cls.from_url(redis_url, decode_responses=True)


redis_client = _build_redis_client()
