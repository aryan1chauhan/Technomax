"""Redis client scaffold for queue integration."""

from __future__ import annotations

import importlib
import os


def get_redis_client():
    redis_module = importlib.import_module("redis")
    redis_cls = getattr(redis_module, "Redis")
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise RuntimeError("REDIS_URL is not configured")
    return redis_cls.from_url(redis_url, decode_responses=True)
