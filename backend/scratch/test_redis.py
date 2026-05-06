import os
import redis
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv("REDIS_URL")
print(f"Testing connection to: {redis_url}")

try:
    r = redis.from_url(redis_url)
    pong = r.ping()
    print(f"SUCCESS: Redis PING -> {pong}")
except Exception as e:
    print(f"FAILED: {e}")
