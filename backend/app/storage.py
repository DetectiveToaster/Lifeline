import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import redis

from .db import Persistence
from .models import Session, SessionState


class SessionStore:
    """
    Redis-backed session store with simple matching queue.
    Falls back to in-memory dicts if redis_client is None (dev only).
    """

    def __init__(
        self,
        redis_client: redis.Redis | None = None,
        persistence: Persistence | None = None,
        token_hash_secret: str = "",
        ban_retention_days: int = 365,
    ):
        self.redis = redis_client
        self.persistence = persistence
        self.token_hash_secret = token_hash_secret.encode() if token_hash_secret else b""
        self.ban_retention_days = ban_retention_days
        self._sessions: dict[UUID, Session] = {}
        self._available_volunteers: set[str] = set()
        self._strikes: dict[str, int] = {}
        self._self_harm_counts: dict[str, int] = {}
        self._banned: dict[str, datetime] = {}
        self._incidents: list[dict] = []

    def _session_key(self, session_id: UUID) -> str:
        return f"session:{session_id}"

    def _queue_key(self) -> str:
        return "queue:seekers"

    def _available_key(self) ->awwwwqeee str:
        return "volunteers:available"

    def save_session(self, session: Session) -> None:
        if self.redis:
            self.redis.set(self._session_key(session.session_id), json.dumps(session.to_dict()))
        else:
            self._sessions[session.session_id] = session

    def get_session(self, session_id: UUID) -> Optional[Session]:
        if self.redis:
            raw = self.redis.get(self._session_key(session_id))
            if not raw:
                return None
            data = json.loads(raw)
            return Session.from_dict(data)
        return self._sessions.get(session_id)

    def create_session(self, seeker_token: str, estimated_wait_seconds: int) -> Session:
        session = Session(seeker_token=seeker_token, estimated_wait_seconds=estimated_wait_seconds)
        session.state = SessionState.MATCHING
        self.save_session(session)
        # enqueue
        if self.redis:
            self.redis.rpush(self._queue_key(), str(session.session_id))
        else:
            # maintain order in memory by dict insertion; fine for dev
            pass
        return session

    def cancel_session(self, session_id: UUID) -> Optional[Session]:
        session = self.get_session(session_id)
        if not session:
            return None
        session.state = SessionState.CANCELLED_BY_SEEKER
        self.save_session(session)
        return session

    def enqueue_volunteer(self, token: str, available: bool) -> None:
        if self.redis:
            if available:
                self.redis.sadd(self._available_key(), token)
            else:
                self.redis.srem(self._available_key(), token)
        else:
            if available:
                self._available_volunteers.add(token)
            else:
                self._available_volunteers.discard(token)

    def pop_available_volunteer(self) -> Optional[str]:
        if self.redis:
            token = self.redis.spop(self._available_key())
            if token:
                return token.decode() if isinstance(token, bytes) else token
            return None
        if not self._available_volunteers:
            return None
        return self._available_volunteers.pop()

    def pop_oldest_pending_session(self) -> Optional[UUID]:
        if self.redis:
            session_id = self.redis.lpop(self._queue_key())
            if session_id:
                return UUID(session_id.decode() if isinstance(session_id, bytes) else session_id)
            return None
        # naive: pick first key in order; not stable but fine for dev
        for sid, session in self._sessions.items():
            if session.state == SessionState.MATCHING:
                return sid
        return None

    def queue_length(self) -> int:
        if self.redis:
            return int(self.redis.llen(self._queue_key()))
        return len([s for s in self._sessions.values() if s.state == SessionState.MATCHING])

    def available_volunteer_count(self) -> int:
        if self.redis:
            return int(self.redis.scard(self._available_key()))
        return len(self._available_volunteers)

    def mark_pending_accept(self, session_id: UUID, volunteer_token: str, timeout_seconds: int) -> Optional[Session]:
        session = self.get_session(session_id)
        if not session:
            return None
        session.pending_volunteer_token = volunteer_token
        session.state = SessionState.PENDING_ACCEPT
        session.expires_at = datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds)
        self.save_session(session)
        if self.redis:
            # Remove from seeker queue if it is still present.
            self.redis.lrem(self._queue_key(), 0, str(session_id))
        return session

    def accept_session(self, session_id: UUID, volunteer_token: str, duration_seconds: int) -> Optional[Session]:
        session = self.get_session(session_id)
        if not session:
            return None
        session.volunteer_token = volunteer_token
        session.pending_volunteer_token = None
        session.activate(duration_seconds)
        self.save_session(session)
        return session

    def end_session(self, session_id: UUID, end_state: SessionState) -> Optional[Session]:
        session = self.get_session(session_id)
        if not session:
            return None
        session.state = end_state
        self.save_session(session)
        return session

    def iter_sessions(self):
        if self.redis:
            for key in self.redis.scan_iter(match="session:*"):
                raw = self.redis.get(key)
                if not raw:
                    continue
                data = json.loads(raw)
                yield Session.from_dict(data)
        else:
            yield from list(self._sessions.values())

    # Moderation helpers
    def increment_strike(self, token: str, amount: int = 1) -> int:
        token_key = self._hash_token(token)
        if self.redis:
            count = self.redis.hincrby("strikes", token_key, amount)
        else:
            count = self._strikes.get(token_key, 0) + amount
            self._strikes[token_key] = count
        if self.persistence:
            count = self.persistence.increment_strike(token_key, amount)
        return count

    def increment_self_harm(self, token: str, amount: int = 1) -> int:
        token_key = self._hash_token(token)
        if self.redis:
            count = self.redis.hincrby("self_harm", token_key, amount)
        else:
            count = self._self_harm_counts.get(token_key, 0) + amount
            self._self_harm_counts[token_key] = count
        if self.persistence:
            count = self.persistence.increment_self_harm(token_key, amount)
        return count

    def ban_token(self, token: str) -> None:
        token_key = self._hash_token(token)
        if self.redis:
            self.redis.set(f"ban:{token_key}", "1", ex=self.ban_retention_days * 86400)
        else:
            self._banned[token_key] = datetime.now(timezone.utc) + timedelta(days=self.ban_retention_days)
        if self.persistence:
            self.persistence.ban_token(token_key, reason="ABUSE_THRESHOLD", retention_days=self.ban_retention_days)

    def is_banned(self, token: str) -> bool:
        token_key = self._hash_token(token)
        if self.redis:
            if self.redis.get(f"ban:{token_key}"):
                return True
        if token_key in self._banned:
            if self._banned[token_key] > datetime.now(timezone.utc):
                return True
            self._banned.pop(token_key, None)
        if self.persistence:
            return self.persistence.is_banned(token_key)
        return False

    def log_incident(self, incident: dict, retention_days: int) -> None:
        incident["timestamp"] = datetime.now(timezone.utc).isoformat()
        if "token" in incident:
            incident["token_hash"] = self._hash_token(str(incident.pop("token")))
        if self.redis:
            key = "incidents"
            self.redis.lpush(key, json.dumps(incident))
            self.redis.expire(key, retention_days * 86400)
        else:
            self._incidents.append(incident)
        if self.persistence:
            self.persistence.log_incident(
                incident_type=incident.get("type", "UNKNOWN"),
                token_hash=incident.get("token_hash", ""),
                role=incident.get("role"),
                metadata_value=incident.get("code"),
            )

    def cleanup_expired(self, incident_retention_days: int) -> None:
        now = datetime.now(timezone.utc)
        if self.persistence:
            self.persistence.cleanup_expired(incident_retention_days=incident_retention_days)
        # In-memory ban cleanup happens during is_banned checks.

    def list_bans(self) -> list[dict]:
        results: dict[str, dict] = {}
        if self.redis:
            for key in self.redis.scan_iter(match="ban:*"):
                token_hash = key.decode().split("ban:", 1)[1]
                ttl = self.redis.ttl(key)
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl) if ttl and ttl > 0 else None
                results[token_hash] = {"token_hash": token_hash, "expires_at": expires_at}
        if self.persistence:
            for row in self.persistence.list_bans():
                results[row["token_hash"]] = row
        else:
            for token_hash, expires_at in self._banned.items():
                results[token_hash] = {"token_hash": token_hash, "expires_at": expires_at}
        return list(results.values())

    def lift_ban(self, token_hash: str) -> None:
        if self.redis:
            self.redis.delete(f"ban:{token_hash}")
        self._banned.pop(token_hash, None)
        if self.persistence:
            self.persistence.lift_ban(token_hash)

    def list_incidents(self, limit: int = 100) -> list[dict]:
        results: list[dict] = []
        if self.redis:
            items = self.redis.lrange("incidents", 0, max(0, limit - 1))
            for raw in items:
                try:
                    data = json.loads(raw)
                    results.append(data)
                except Exception:
                    continue
        if self.persistence:
            results.extend(self.persistence.list_incidents(limit=limit))
        else:
            results.extend(self._incidents[:limit])
        return results

    def _hash_token(self, token: str) -> str:
        if not self.token_hash_secret:
            return token
        return hmac.new(self.token_hash_secret, token.encode(), digestmod="sha256").hexdigest()
