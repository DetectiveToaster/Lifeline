from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from uuid import UUID

from ..auth import decode_token, get_current_token
from ..constants import SYSTEM_NO_VOLUNTEER_AVAILABLE
from ..deps import get_matching_service, get_session_store
from ..matching import MatchingService
from ..metrics import sessions_failed_no_volunteer
from ..models import Role, SessionState
from ..storage import SessionStore
from ..ws_manager import manager
from ..utils import log_event

router = APIRouter(prefix="/v1/volunteer", tags=["volunteer"])


class VolunteerStatusRequest(BaseModel):
    available: bool


class VolunteerStatusResponse(BaseModel):
    status: str


class VolunteerPendingSession(BaseModel):
    session_id: UUID
    status: SessionState
    estimated_wait_seconds: int


@router.post("/status", response_model=VolunteerStatusResponse)
def set_status(
    payload: VolunteerStatusRequest,
    token: str = Depends(get_current_token),
    matcher: MatchingService = Depends(get_matching_service),
) -> VolunteerStatusResponse:
    claims = decode_token(token)
    if matcher.store.is_banned(token):  # type: ignore[attr-defined]
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Banned")
    if claims.get("role") != Role.volunteer.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role not allowed")
    matcher.set_volunteer_available(token, payload.available)
    return VolunteerStatusResponse(status="ok")


@router.get("/pending", response_model=list[VolunteerPendingSession])
def pending_sessions(
    token: str = Depends(get_current_token),
    store: SessionStore = Depends(get_session_store),
) -> list[VolunteerPendingSession]:
    claims = decode_token(token)
    if store.is_banned(token):
        raise HTTPException(status_code=403, detail="Banned")
    if claims.get("role") != Role.volunteer.value:
        raise HTTPException(status_code=403, detail="Role not allowed")
    return [
        VolunteerPendingSession(
            session_id=session.session_id,
            status=session.state,
            estimated_wait_seconds=session.estimated_wait_seconds,
        )
        for session in store.pending_sessions_for_volunteer(token)
    ]



class VolunteerAcceptRequest(BaseModel):
    session_id: UUID


class VolunteerAcceptResponse(BaseModel):
    status: SessionState


@router.post("/accept", response_model=VolunteerAcceptResponse)
async def accept_session(
    payload: VolunteerAcceptRequest,
    token: str = Depends(get_current_token),
    matcher: MatchingService = Depends(get_matching_service),
) -> VolunteerAcceptResponse:
    claims = decode_token(token)
    if matcher.store.is_banned(token):  # type: ignore[attr-defined]
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Banned")
    if claims.get("role") != Role.volunteer.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role not allowed")
    accepted = matcher.volunteer_accept(payload.session_id, token)
    if not accepted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session not available")
    log_event("volunteer.accepted", session_id=str(payload.session_id), token=token)
    # Notify connected clients that session is active.
    await manager.broadcast(
        payload.session_id, {"type": "session_state", "state": accepted.state.value}, exclude=None
    )
    return VolunteerAcceptResponse(status=accepted.state)


class VolunteerDeclineRequest(BaseModel):
    session_id: UUID


@router.post("/decline", response_model=VolunteerAcceptResponse)
async def decline_session(
    payload: VolunteerDeclineRequest,
    token: str = Depends(get_current_token),
    store: SessionStore = Depends(get_session_store),
) -> VolunteerAcceptResponse:
    claims = decode_token(token)
    if store.is_banned(token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Banned")
    if claims.get("role") != Role.volunteer.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role not allowed")
    session = store.get_session(payload.session_id)
    if not session or session.state != SessionState.PENDING_ACCEPT:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.pending_volunteer_token != token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not assigned to this session")
    session = store.end_session(payload.session_id, SessionState.FAILED_NO_VOLUNTEER) or session
    sessions_failed_no_volunteer.inc()
    log_event("volunteer.declined", session_id=str(payload.session_id), token=token)
    await manager.broadcast(
        session.session_id,
        {"type": "system", "code": SYSTEM_NO_VOLUNTEER_AVAILABLE, "content": "No volunteer accepted."},
    )
    await manager.broadcast(session.session_id, {"type": "session_state", "state": session.state.value})
    return VolunteerAcceptResponse(status=session.state)
