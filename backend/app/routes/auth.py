from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..auth import create_anonymous_token
from ..models import Role

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class AnonymousAuthRequest(BaseModel):
    role: Role = Field(default=Role.seeker, description="Role for this token.")


class AnonymousAuthResponse(BaseModel):
    token: str


@router.post("/anonymous", response_model=AnonymousAuthResponse)
def anonymous_auth(payload: AnonymousAuthRequest) -> AnonymousAuthResponse:
    token = create_anonymous_token(payload.role)
    return AnonymousAuthResponse(token=token)
