import hashlib
import time
from dataclasses import dataclass

import redis


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset: int


class RateLimiter:
    def __init__(self, redis_client: redis.Redis | None = None):
        self.redis = redis_client
        self._local: dict[str, tuple[int, int]] = {}

    def hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def check(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = int(time.time())
        reset = now + window_seconds
        if self.redis:
            count = self.redis.incr(key, 1)
            if count == 1:
                self.redis.expire(key, window_seconds)
            ttl = self.redis.ttl(key)
            reset = now + (ttl if ttl > 0 else window_seconds)
            remaining = max(0, limit - count)
            return RateLimitResult(allowed=count <= limit, limit=limit, remaining=remaining, reset=reset)
        count, stored_reset = self._local.get(key, (0, reset))
        if now > stored_reset:
            count = 0
            stored_reset = reset
        count += 1
        self._local[key] = (count, stored_reset)
        remaining = max(0, limit - count)
        return RateLimitResult(allowed=count <= limit, limit=limit, remaining=remaining, reset=stored_reset)
