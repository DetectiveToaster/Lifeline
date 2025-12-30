from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..auth import decode_token, get_current_token
from ..constants import (
    SYSTEM_NO_VOLUNTEER_AVAILABLE,
    SYSTEM_SEEKER_LEFT,
    SYSTEM_SESSION_CANCELLED,
    SYSTEM_VOLUNTEER_LEFT,
)
from ..deps import get_matching_service, get_session_store
from ..matching import MatchingService
from ..models import Role, Session, SessionState, SessionStore
from ..metrics import (
    sessions_cancelled,
    sessions_ended_seeker_left,
    sessions_ended_volunteer_left,
    sessions_failed_no_volunteer,
    sessions_created,
)
from ..ws_manager import manager
from ..utils import log_event

router = APIRouter(prefix="/v1/session", tags=["session"])


class SessionRequestBody(BaseModel):
    client_capabilities: dict = Field(default_factory=dict)


class SessionResponse(BaseModel):
    session_id: UUID
    status: SessionState
    estimated_wait_seconds: int


class SessionCancelRequest(BaseModel):
    session_id: UUID


@router.post("/request", response_model=SessionResponse)
def request_session(
    payload: SessionRequestBody,
    token: str = Depends(get_current_token),
    matcher: MatchingService = Depends(get_matching_service),
) -> SessionResponse:
    claims = decode_token(token)
    if matcher.store.is_banned(token):  # type: ignore[attr-defined]
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Banned")
    if claims.get("role") != Role.seeker.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role not allowed")
    session: Session = matcher.request_session(token)
    sessions_created.inc()
    log_event("session.requested", session_id=str(session.session_id), token=token)
    return SessionResponse(
        session_id=session.session_id,
        status=session.state,
        estimated_wait_seconds=session.estimated_wait_seconds,
    )


@router.post("/cancel", response_model=SessionResponse)
async def cancel_session(
    payload: SessionCancelRequest,
    token: str = Depends(get_current_token),
    store: SessionStore = Depends(get_session_store),
) -> SessionResponse:
    decode_token(token)
    session = store.get_session(payload.session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.seeker_token != token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot cancel this session")
    if session.state == SessionState.ACTIVE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Active sessions must use /leave")
    store.cancel_session(payload.session_id)
    sessions_cancelled.inc()
    log_event("session.cancelled", session_id=str(session.session_id), token=token)
    await_broadcast = (
        {"type": "system", "code": SYSTEM_SESSION_CANCELLED, "content": "The seeker cancelled the request."}
    )
    await manager.broadcast(session.session_id, await_broadcast)
    await manager.broadcast(session.session_id, {"type": "session_state", "state": session.state.value})
    return SessionResponse(
        session_id=session.session_id,
        status=session.state,
        estimated_wait_seconds=session.estimated_wait_seconds,
    )


class SessionLeaveRequest(BaseModel):
    session_id: UUID


@router.post("/leave", response_model=SessionResponse)
async def leave_session(
    payload: SessionLeaveRequest,
    token: str = Depends(get_current_token),
    store: SessionStore = Depends(get_session_store),
) -> SessionResponse:
    claims = decode_token(token)
    session = store.get_session(payload.session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if token not in (session.seeker_token, session.volunteer_token, session.pending_volunteer_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized for this session")

    if claims.get("role") == Role.seeker.value:
        if session.state in {SessionState.MATCHING, SessionState.PENDING_ACCEPT}:
            session = store.end_session(payload.session_id, SessionState.CANCELLED_BY_SEEKER) or session
            sessions_cancelled.inc()
            log_event("session.cancelled", session_id=str(session.session_id), token=token)
            await manager.broadcast(
                session.session_id,
                {"type": "system", "code": SYSTEM_SESSION_CANCELLED, "content": "The seeker cancelled the request."},
            )
        elif session.state == SessionState.ACTIVE:
            session = store.end_session(payload.session_id, SessionState.ENDED_SEEKER_LEFT) or session
            sessions_ended_seeker_left.inc()
            log_event("session.seeker_left", session_id=str(session.session_id), token=token)
            await manager.broadcast(
                session.session_id,
                {"type": "system", "code": SYSTEM_SEEKER_LEFT, "content": "The seeker left the conversation."},
            )
    else:
        if session.state == SessionState.ACTIVE:
            session = store.end_session(payload.session_id, SessionState.ENDED_VOLUNTEER_LEFT) or session
            sessions_ended_volunteer_left.inc()
            log_event("session.volunteer_left", session_id=str(session.session_id), token=token)
            await manager.broadcast(
                session.session_id,
                {"type": "system", "code": SYSTEM_VOLUNTEER_LEFT, "content": "The volunteer left the conversation."},
            )
        elif session.state == SessionState.PENDING_ACCEPT and session.pending_volunteer_token == token:
            session = store.end_session(payload.session_id, SessionState.FAILED_NO_VOLUNTEER) or session
            sessions_failed_no_volunteer.inc()
            log_event("session.no_volunteer", session_id=str(session.session_id), token=token)
            await manager.broadcast(
                session.session_id,
                {
                    "type": "system",
                    "code": SYSTEM_NO_VOLUNTEER_AVAILABLE,
                    "content": "No volunteer accepted.",
                },
            )

    await manager.broadcast(session.session_id, {"type": "session_state", "state": session.state.value})
    return SessionResponse(
        session_id=session.session_id,
        status=session.state,
        estimated_wait_seconds=session.estimated_wait_seconds,
    )


class SessionStatusResponse(BaseModel):
    session_id: UUID
    status: SessionState
    estimated_wait_seconds: int | None = None
    expires_at: datetime | None = None


@router.get("/{session_id}/status", response_model=SessionStatusResponse)
def get_session_status(
    session_id: UUID,
    token: str = Depends(get_current_token),
    store: SessionStore = Depends(get_session_store),
) -> SessionStatusResponse:
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if token not in (session.seeker_token, session.volunteer_token, session.pending_volunteer_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized for this session")
    return SessionStatusResponse(
        session_id=session.session_id,
        status=session.state,
        estimated_wait_seconds=session.estimated_wait_seconds,
        expires_at=session.expires_at,
    )
