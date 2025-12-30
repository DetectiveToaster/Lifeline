import redis

from .config import settings
from .db import Persistence, init_engine
from .matching import MatchingService
from .rate_limit import RateLimiter
from .storage import SessionStore

# Initialize Redis client (may be None if URL not provided).
redis_client = redis.Redis.from_url(settings.redis_url) if settings.redis_url else None
engine = init_engine(settings.db_url) if settings.db_url else None
persistence = Persistence(engine) if engine else None
session_store = SessionStore(
    redis_client=redis_client,
    persistence=persistence,
    token_hash_secret=settings.jwt_secret,
    ban_retention_days=settings.ban_retention_days,
)
matching_service = MatchingService(session_store, settings)
rate_limiter = RateLimiter(redis_client=redis_client)


def get_settings():
    return settings


def get_session_store():
    return session_store


def get_matching_service():
    return matching_service


def get_rate_limiter():
    return rate_limiter
