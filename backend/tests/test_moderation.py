import os

os.environ.setdefault("JWT_SECRET", "test-secret")

from app.config import Settings
from app.moderation import moderate_message
from app.storage import SessionStore


def test_pii_block():
    store = SessionStore(redis_client=None)
    settings = Settings(jwt_secret="test-secret")
    decision = moderate_message(
        token="t1", role="seeker", content="contact me at test@example.com", store=store, settings=settings
    )
    assert decision.allow is False
    assert decision.block_code == "PERSONAL_INFO_BLOCKED"


def test_abuse_strike_and_ban():
    store = SessionStore(redis_client=None)
    settings = Settings(jwt_secret="test-secret", abuse_ban_threshold=2, abuse_end_session_threshold=1)
    decision1 = moderate_message(
        token="t2", role="seeker", content="you are stupid", store=store, settings=settings
    )
    assert decision1.allow is False
    assert decision1.end_session is True
    decision2 = moderate_message(
        token="t2", role="seeker", content="idiot", store=store, settings=settings
    )
    assert decision2.banned is True
    assert store.is_banned("t2") is True


def test_self_harm_crisis_flag():
    store = SessionStore(redis_client=None)
    settings = Settings(jwt_secret="test-secret", self_harm_crisis_threshold=2)
    decision1 = moderate_message(
        token="t3", role="seeker", content="i want to end it all", store=store, settings=settings
    )
    decision2 = moderate_message(
        token="t3", role="seeker", content="i will kill myself", store=store, settings=settings
    )
    assert decision1.crisis is False
    assert decision2.crisis is True
