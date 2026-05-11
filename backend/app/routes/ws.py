import asyncio
import json
import time
from uuid import UUID

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status

from ..auth import decode_token
from ..config import Settings
from ..deps import get_session_store, get_settings
from ..constants import (
    ERROR_INVALID_JSON,
    ERROR_INVALID_SESSION,
    ERROR_MESSAGE_TOO_LARGE,
    ERROR_UNKNOWN_TYPE,
    ERROR_MESSAGES,
    WARNING_BANNED,
    WARNING_CRISIS_LANGUAGE_DETECTED,
    WARNING_RATE_LIMITED,
    WARNING_MESSAGES,
    SYSTEM_CRISIS_RESOURCES,
    SYSTEM_NO_VOLUNTEER_AVAILABLE,
    SYSTEM_SEEKER_LEFT,
    SYSTEM_SESSION_CANCELLED,
    SYSTEM_VOLUNTEER_LEFT,
)
from ..metrics import (
    sessions_cancelled,
    sessions_ended_seeker_left,
    sessions_ended_volunteer_left,
    sessions_failed_error,
    sessions_failed_no_volunteer,
    ws_errors,
    ws_message_handle_seconds,
    ws_warnings,
)
from ..moderation import moderate_message
from ..models import Role, SessionState
from ..storage import SessionStore
from ..ws_manager import manager
from ..utils import log_event

router = APIRouter(tags=["websocket"])

TERMINAL_STATES = {
    SessionState.ENDED_TIMEOUT,
    SessionState.ENDED_SEEKER_LEFT,
    SessionState.ENDED_VOLUNTEER_LEFT,
    SessionState.FAILED_NO_VOLUNTEER,
    SessionState.CANCELLED_BY_SEEKER,
    SessionState.FAILED_ERROR,
}


async def handle_session_exit(
    session_id: UUID, role: str, token: str, store: SessionStore
) -> None:
    session = store.get_session(session_id)
    if not session or session.state in TERMINAL_STATES:
        return

    if role == Role.seeker.value and session.seeker_token == token:
        if session.state == SessionState.ACTIVE:
            session = store.end_session(session_id, SessionState.ENDED_SEEKER_LEFT) or session
            sessions_ended_seeker_left.inc()
            log_event("session.seeker_left", session_id=str(session_id), token=token)
            await manager.broadcast(
                session_id,
                {
                    "type": "system",
                    "code": SYSTEM_SEEKER_LEFT,
                    "content": "The seeker left the conversation.",
                },
            )
        elif session.state in {SessionState.MATCHING, SessionState.PENDING_ACCEPT}:
            session = store.end_session(session_id, SessionState.CANCELLED_BY_SEEKER) or session
            sessions_cancelled.inc()
            log_event("session.cancelled", session_id=str(session_id), token=token)
            await manager.broadcast(
                session_id,
                {"type": "system", "code": SYSTEM_SESSION_CANCELLED, "content": "The seeker cancelled the request."},
            )
        await manager.broadcast(session_id, {"type": "session_state", "state": session.state.value})
        return

    if role == Role.volunteer.value:
        if session.state == SessionState.ACTIVE and session.volunteer_token == token:
            session = store.end_session(session_id, SessionState.ENDED_VOLUNTEER_LEFT) or session
            sessions_ended_volunteer_left.inc()
            log_event("session.volunteer_left", session_id=str(session_id), token=token)
            await manager.broadcast(
                session_id,
                {
                    "type": "system",
                    "code": SYSTEM_VOLUNTEER_LEFT,
                    "content": "The volunteer left the conversation.",
                },
            )
            await manager.broadcast(session_id, {"type": "session_state", "state": session.state.value})
            return
        if session.state == SessionState.PENDING_ACCEPT and session.pending_volunteer_token == token:
            session = store.end_session(session_id, SessionState.FAILED_NO_VOLUNTEER) or session
            sessions_failed_no_volunteer.inc()
            log_event("session.no_volunteer", session_id=str(session_id), token=token)
            await manager.broadcast(
                session_id,
                {
                    "type": "system",
                    "code": SYSTEM_NO_VOLUNTEER_AVAILABLE,
                    "content": "No volunteer accepted.",
                },
            )
            await manager.broadcast(session_id, {"type": "session_state", "state": session.state.value})


@router.websocket("/v1/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str,
    session_id: str,
    role: str,
    locale: str | None = None,
    store: SessionStore = Depends(get_session_store),
    settings: Settings = Depends(get_settings),
):
    claims = decode_token(token)
    session_uuid = UUID(session_id)
    session = store.get_session(session_uuid)
    if not session:
        ws_errors.labels(code=ERROR_INVALID_SESSION).inc()
        await websocket.accept()
        await manager.send(
            websocket,
            {"type": "error", "code": ERROR_INVALID_SESSION, "message": ERROR_MESSAGES.get(ERROR_INVALID_SESSION)},
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    if store.is_banned(token):
        ws_warnings.labels(code=WARNING_BANNED).inc()
        await websocket.accept()
        await manager.send(
            websocket,
            {"type": "warning", "code": WARNING_BANNED, "message": WARNING_MESSAGES.get(WARNING_BANNED)},
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    if claims.get("role") not in {Role.seeker.value, Role.volunteer.value}:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await manager.connect(session_uuid, websocket)
    # Send initial state/timer snapshot
    await manager.send(websocket, {"type": "session_state", "state": session.state.value})
    if session.expires_at:
        from datetime import datetime, timezone

        remaining = int((session.expires_at - datetime.now(timezone.utc)).total_seconds())
        await manager.send(websocket, {"type": "timer_update", "remaining_seconds": max(0, remaining)})

    window_start = time.time()
    msg_count = 0

    try:
        while True:
            data = await asyncio.wait_for(websocket.receive_text(), timeout=settings.idle_timeout_seconds)
            now = time.time()
            if now - window_start >= 60:
                window_start = now
                msg_count = 0
            if msg_count >= settings.max_messages_per_min:
                ws_warnings.labels(code=WARNING_RATE_LIMITED).inc()
                await manager.send(
                    websocket,
                    {
                        "type": "warning",
                        "code": WARNING_RATE_LIMITED,
                        "message": WARNING_MESSAGES.get(WARNING_RATE_LIMITED),
                    },
                )
                continue
            if len(data.encode()) > settings.max_message_bytes:
                ws_errors.labels(code=ERROR_MESSAGE_TOO_LARGE).inc()
                await manager.send(
                    websocket,
                    {
                        "type": "error",
                        "code": ERROR_MESSAGE_TOO_LARGE,
                        "message": ERROR_MESSAGES.get(ERROR_MESSAGE_TOO_LARGE),
                    },
                )
                continue
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                ws_errors.labels(code=ERROR_INVALID_JSON).inc()
                await manager.send(
                    websocket,
                    {"type": "error", "code": ERROR_INVALID_JSON, "message": ERROR_MESSAGES.get(ERROR_INVALID_JSON)},
                )
                continue
            if payload.get("type") == "leave":
                await handle_session_exit(session_uuid, role, token, store)
                await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
                break
            if payload.get("type") == "decline" and role == Role.volunteer.value:
                session = store.get_session(session_uuid)
                if session and session.state == SessionState.PENDING_ACCEPT and session.pending_volunteer_token == token:
                    session = store.end_session(session_uuid, SessionState.FAILED_NO_VOLUNTEER) or session
                    sessions_failed_no_volunteer.inc()
                    log_event("volunteer.declined", session_id=str(session_uuid), token=token)
                    await manager.broadcast(
                        session_uuid,
                        {
                            "type": "system",
                            "code": SYSTEM_NO_VOLUNTEER_AVAILABLE,
                            "content": "No volunteer accepted.",
                        },
                    )
                    await manager.broadcast(session_uuid, {"type": "session_state", "state": session.state.value})
                continue
            if payload.get("type") == "message":
                start_ts = time.monotonic()
                msg_count += 1
                content = payload.get("content", "")
                decision = moderate_message(token=token, role=role, content=content, store=store, settings=settings)
                if decision.banned:
                    ws_warnings.labels(code=WARNING_BANNED).inc()
                    await manager.send(
                        websocket,
                        {
                            "type": "warning",
                            "code": WARNING_BANNED,
                            "message": WARNING_MESSAGES.get(WARNING_BANNED),
                        },
                    )
                    session = store.end_session(session_uuid, SessionState.FAILED_ERROR) or session
                    sessions_failed_error.inc()
                    log_event("session.banned", session_id=str(session_uuid), token=token)
                    await manager.broadcast(
                        session_uuid, {"type": "session_state", "state": session.state.value}, exclude=None
                    )
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    break
                if decision.end_session:
                    ws_warnings.labels(code=decision.block_code or "SESSION_ENDED").inc()
                    block_code = decision.block_code or "SESSION_ENDED"
                    await manager.send(
                        websocket,
                        {"type": "warning", "code": block_code, "message": WARNING_MESSAGES.get(block_code)},
                    )
                    session = store.end_session(session_uuid, SessionState.FAILED_ERROR) or session
                    sessions_failed_error.inc()
                    log_event("session.failed_error", session_id=str(session_uuid), token=token, code=block_code)
                    await manager.broadcast(
                        session_uuid, {"type": "session_state", "state": session.state.value}, exclude=None
                    )
                    continue
                if not decision.allow:
                    ws_warnings.labels(code=decision.block_code or "BLOCKED").inc()
                    await manager.send(
                        websocket,
                        {
                            "type": "warning",
                            "code": decision.block_code,
                            "message": WARNING_MESSAGES.get(decision.block_code),
                        },
                    )
                    continue
                # crisis flag: send informational event to both parties
                if decision.crisis:
                    ws_warnings.labels(code=WARNING_CRISIS_LANGUAGE_DETECTED).inc()
                    await manager.broadcast(
                        session_uuid,
                        {
                            "type": "warning",
                            "code": WARNING_CRISIS_LANGUAGE_DETECTED,
                            "message": WARNING_MESSAGES.get(WARNING_CRISIS_LANGUAGE_DETECTED),
                        },
                        exclude=None,
                    )
                    await manager.broadcast(
                        session_uuid,
                        {
                            "type": "system",
                            "code": SYSTEM_CRISIS_RESOURCES,
                            "content": settings.crisis_message(locale),
                        },
                        exclude=None,
                    )
                await manager.broadcast(
                    session_uuid,
                    {"type": "message", "from": role, "content": content},
                    exclude=websocket,
                )
                ws_message_handle_seconds.observe(max(0.0, time.monotonic() - start_ts))
            else:
                ws_errors.labels(code=ERROR_UNKNOWN_TYPE).inc()
                await manager.send(
                    websocket,
                    {"type": "error", "code": ERROR_UNKNOWN_TYPE, "message": ERROR_MESSAGES.get(ERROR_UNKNOWN_TYPE)},
                )
    except asyncio.TimeoutError:
        await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
    except WebSocketDisconnect:
        pass
    finally:
        manager.remove(session_uuid, websocket)
        await handle_session_exit(session_uuid, role, token, store)
