import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from .config import settings

logger = logging.getLogger("lifeline")


def _hash_value(value: str) -> str:
    if not settings.jwt_secret:
        return "redacted"
    return hashlib.sha256((settings.jwt_secret + value).encode()).hexdigest()


def _sanitize_fields(fields: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in fields.items():
        if value is None:
            sanitized[key] = None
            continue
        if "token" in key:
            sanitized[key] = _hash_value(str(value))
        else:
            sanitized[key] = value
    return sanitized


def log_event(event_type: str, **fields: Any) -> None:
    payload = {"event": event_type, "ts": datetime.now(timezone.utc).isoformat()}
    payload.update(_sanitize_fields(fields))
    logger.info(json.dumps(payload))
