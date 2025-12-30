from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import uuid4

import jwt
from fastapi import Depends, HTTPException, Header, status

from .config import settings
from .models import Role


def create_anonymous_token(role: Role) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(uuid4()),
        "role": role.value,
        "exp": now + timedelta(days=settings.jwt_exp_days),
        "iat": now,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


def create_admin_token() -> str:
    if not settings.admin_jwt_secret:
        raise RuntimeError("ADMIN_JWT_SECRET is not configured")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(uuid4()),
        "role": "admin",
        "exp": now + timedelta(days=7),
        "iat": now,
    }
    return jwt.encode(payload, settings.admin_jwt_secret, algorithm="HS256")


def decode_admin_token(token: str) -> dict:
    if not settings.admin_jwt_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin auth not configured")
    try:
        claims = jwt.decode(token, settings.admin_jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    if claims.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return claims


def get_current_token(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    decode_token(token)  # validates
    return token
