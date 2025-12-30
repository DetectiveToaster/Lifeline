import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict
from uuid import UUID

from .config import Settings
from .models import Session, SessionState
from .constants import SYSTEM_NO_VOLUNTEER_AVAILABLE, SYSTEM_SESSION_ENDED
from .metrics import available_volunteers, queue_depth, sessions_completed, sessions_failed_no_volunteer
from .storage import SessionStore
from .ws_manager import manager


def seconds_remaining(session: Session) -> int:
    if not session.expires_at:
        return 0
    delta = session.expires_at - datetime.now(timezone.utc)
    return max(0, int(delta.total_seconds()))


async def session_enforcer(store: SessionStore, settings: Settings):
    last_state: Dict[UUID, SessionState] = {}
    last_timer_emit: Dict[UUID, int] = {}
    while True:
        try:
            for session in store.iter_sessions():
                now = datetime.now(timezone.utc)
                # Handle matching window expiration
                if session.state == SessionState.MATCHING:
                    cutoff = session.created_at + timedelta(seconds=settings.matching_max_wait_seconds)
                    if cutoff <= now:
                        session = store.end_session(session.session_id, SessionState.FAILED_NO_VOLUNTEER) or session
                        sessions_failed_no_volunteer.inc()
                        await manager.broadcast(
                            session.session_id,
                            {
                                "type": "system",
                                "code": SYSTEM_NO_VOLUNTEER_AVAILABLE,
                                "content": "No one is currently available. Please try again.",
                            },
                        )
                    session = store.end_session(session.session_id, SessionState.FAILED_NO_VOLUNTEER) or session
                # Handle pending accept expiration
                if session.state == SessionState.PENDING_ACCEPT and session.expires_at and session.expires_at <= now:
                    session = store.end_session(session.session_id, SessionState.FAILED_NO_VOLUNTEER) or session
                    sessions_failed_no_volunteer.inc()
                    await manager.broadcast(
                        session.session_id,
                        {"type": "system", "code": SYSTEM_NO_VOLUNTEER_AVAILABLE, "content": "No volunteer accepted."},
                    )
                # Handle active timeout
                if session.state == SessionState.ACTIVE and session.expires_at and session.expires_at <= now:
                    session = store.end_session(session.session_id, SessionState.ENDED_TIMEOUT) or session
                    sessions_completed.inc()
                    await manager.broadcast(
                        session.session_id,
                        {
                            "type": "system",
                            "code": SYSTEM_SESSION_ENDED,
                            "content": "Time is up. Thank you for being here.",
                        },
                    )

                # Broadcast state change
                prev = last_state.get(session.session_id)
                if prev != session.state:
                    await manager.broadcast(
                        session.session_id,
                        {"type": "session_state", "state": session.state.value},
                    )
                    last_state[session.session_id] = session.state

                # Broadcast timer updates at configured interval when active
                if session.state == SessionState.ACTIVE and session.expires_at:
                    remaining = seconds_remaining(session)
                    last_sent = last_timer_emit.get(session.session_id, None)
                    if last_sent is None or remaining < last_sent:
                        await manager.broadcast(
                            session.session_id, {"type": "timer_update", "remaining_seconds": remaining}
                        )
                        last_timer_emit[session.session_id] = remaining

        except Exception:
            # Keep loop alive even if something goes wrong.
            pass
        await asyncio.sleep(1)


async def maintenance_worker(store: SessionStore, settings: Settings):
    while True:
        try:
            store.cleanup_expired(incident_retention_days=settings.incident_retention_days)
            queue_depth.set(store.queue_length())
            available_volunteers.set(store.available_volunteer_count())
        except Exception:
            pass
        await asyncio.sleep(60)
