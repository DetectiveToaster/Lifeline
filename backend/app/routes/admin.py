from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel

from ..auth import decode_admin_token
from ..deps import get_session_store
from ..storage import SessionStore
from ..utils import log_event

router = APIRouter(prefix="/v1/admin", tags=["admin"])


def require_admin(
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin token required")
    token = authorization.split(" ", 1)[1]
    decode_admin_token(token)


class BanEntry(BaseModel):
    token_hash: str
    expires_at: datetime | None = None


@router.get("/bans", response_model=List[BanEntry], dependencies=[Depends(require_admin)])
def list_bans(store: SessionStore = Depends(get_session_store)):
    log_event("admin.bans.list")
    return store.list_bans()


@router.delete("/bans/{token_hash}", dependencies=[Depends(require_admin)])
def lift_ban(token_hash: str, store: SessionStore = Depends(get_session_store)):
    store.lift_ban(token_hash)
    log_event("admin.bans.lift", token_hash=token_hash)
    return {"status": "ok"}


class IncidentEntry(BaseModel):
    type: str
    token_hash: str
    role: str | None = None
    timestamp: datetime
    metadata: str | None = None


@router.get("/incidents", response_model=List[IncidentEntry], dependencies=[Depends(require_admin)])
def list_incidents(limit: int = 100, store: SessionStore = Depends(get_session_store)):
    log_event("admin.incidents.list", limit=limit)
    return store.list_incidents(limit=limit)
