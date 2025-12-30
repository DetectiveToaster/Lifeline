from __future__ import annotations

import enum
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from uuid import UUID, uuid4


class Role(str, enum.Enum):
    seeker = "seeker"
    volunteer = "volunteer"


class SessionState(str, enum.Enum):
    REQUESTED = "REQUESTED"
    MATCHING = "MATCHING"
    PENDING_ACCEPT = "PENDING_ACCEPT"
    ACTIVE = "ACTIVE"
    ENDED_TIMEOUT = "ENDED_TIMEOUT"
    ENDED_SEEKER_LEFT = "ENDED_SEEKER_LEFT"
    ENDED_VOLUNTEER_LEFT = "ENDED_VOLUNTEER_LEFT"
    FAILED_NO_VOLUNTEER = "FAILED_NO_VOLUNTEER"
    CANCELLED_BY_SEEKER = "CANCELLED_BY_SEEKER"
    FAILED_ERROR = "FAILED_ERROR"


@dataclass
class Session:
    session_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    state: SessionState = SessionState.MATCHING
    seeker_token: str | None = None
    volunteer_token: str | None = None
    pending_volunteer_token: str | None = None
    estimated_wait_seconds: int = 15
    expires_at: datetime | None = None

    def activate(self, duration_seconds: int) -> None:
        self.state = SessionState.ACTIVE
        self.expires_at = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)

    def to_dict(self) -> Dict:
        data = asdict(self)
        data["session_id"] = str(self.session_id)
        data["created_at"] = self.created_at.isoformat()
        data["state"] = self.state.value
        data["expires_at"] = self.expires_at.isoformat() if self.expires_at else None
        return data

    @staticmethod
    def from_dict(data: Dict) -> "Session":
        return Session(
            session_id=UUID(data["session_id"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            state=SessionState(data["state"]),
            seeker_token=data.get("seeker_token"),
            volunteer_token=data.get("volunteer_token"),
            pending_volunteer_token=data.get("pending_volunteer_token"),
            estimated_wait_seconds=int(data.get("estimated_wait_seconds", 15)),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
        )
