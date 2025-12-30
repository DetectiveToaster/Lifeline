from app.rate_limit import RateLimiter


def test_rate_limit_allows_then_blocks():
    limiter = RateLimiter(redis_client=None)
    key = "ratelimit:test"
    result1 = limiter.check(key=key, limit=2, window_seconds=60)
    result2 = limiter.check(key=key, limit=2, window_seconds=60)
    result3 = limiter.check(key=key, limit=2, window_seconds=60)
    assert result1.allowed is True
    assert result2.allowed is True
    assert result3.allowed is False
