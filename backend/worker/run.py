#!/usr/bin/env python3
"""
MediRoute — Worker entrypoint
Usage:
    export DATABASE_URL=postgresql://postgres:postgres@localhost:<PORT>/mediroute
    export REDIS_URL=redis://localhost:6379/0
    python3 -m worker.run
"""
import os
import sys
import logging

import redis
from rq import Worker, Queue

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [worker] %(levelname)s %(message)s")

REDIS_URL    = os.environ.get("REDIS_URL",    "redis://localhost:6379/0")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/mediroute")

if __name__ == "__main__":
    log.info("═" * 60)
    log.info("MediRoute Worker starting")
    log.info("  REDIS_URL    = %s", REDIS_URL)
    log.info("  DATABASE_URL = %s", DATABASE_URL)
    log.info("═" * 60)

    # Self-test before accepting any jobs
    from worker.tasks import worker_selftest
    try:
        worker_selftest()
    except Exception as e:
        log.error("Self-test FAILED — worker will not start: %s", e)
        log.error("  Check that DATABASE_URL points to the right Postgres instance.")
        log.error("  If Postgres is in Docker, use:  docker port <container> 5432")
        log.error("  to find the mapped host port, then update DATABASE_URL.")
        sys.exit(1)

    conn   = redis.from_url(REDIS_URL)
    queues = [Queue("mediroute", connection=conn), Queue("default", connection=conn)]
    worker = Worker(queues, connection=conn)
    log.info("Listening on queues: %s", [q.name for q in queues])
    worker.work(with_scheduler=True)
