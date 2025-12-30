from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from .config import Settings
from .models import Session, SessionState
from .metrics import matching_wait_seconds
from .storage import SessionStore


class MatchingService:
    def __init__(self, store: SessionStore, settings: Settings):
        self.store = store
        self.settings = settings

    def request_session(self, seeker_token: str) -> Session:
        session = self.store.create_session(seeker_token=seeker_token, estimated_wait_seconds=15)
        # Try to assign an available volunteer immediately.
        self._try_assign_volunteer(session.session_id)
        return self.store.get_session(session.session_id) or session

    def set_volunteer_available(self, volunteer_token: str, available: bool) -> None:
        self.store.enqueue_volunteer(volunteer_token, available)
        if available:
            # Try to match with oldest waiting seeker.
            self._try_assign_oldest_session()

    def volunteer_accept(self, session_id: UUID, volunteer_token: str) -> Optional[Session]:
        session = self.store.get_session(session_id)
        if not session:
            return None
        if session.state not in {SessionState.PENDING_ACCEPT, SessionState.MATCHING}:
            return None
        # If pending volunteer exists and doesn't match, reject.
        if session.pending_volunteer_token and session.pending_volunteer_token != volunteer_token:
            return None
        accepted = self.store.accept_session(session_id, volunteer_token, self.settings.session_duration_seconds)
        if accepted:
            wait_seconds = (datetime.now(timezone.utc) - accepted.created_at).total_seconds()
            matching_wait_seconds.observe(max(0.0, wait_seconds))
        return accepted

    def _try_assign_volunteer(self, session_id: UUID) -> None:
        volunteer_token = self.store.pop_available_volunteer()
        if not volunteer_token:
            # Session remains in MATCHING
            return
        self.store.mark_pending_accept(
            session_id=session_id,
            volunteer_token=volunteer_token,
            timeout_seconds=self.settings.pending_accept_timeout_seconds,
        )

    def _try_assign_oldest_session(self) -> None:
        session_id = self.store.pop_oldest_pending_session()
        if not session_id:
            return
        self._try_assign_volunteer(session_id)
