"""Redis client scaffold for queue integration."""

from __future__ import annotations

import importlib
import os


def get_redis_client():
    redis_module = importlib.import_module("redis")
    redis_cls = getattr(redis_module, "Redis")
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    db = int(os.getenv("REDIS_DB", "0"))
    return redis_cls(host=host, port=port, db=db, decode_responses=True)
