import re
from dataclasses import dataclass

from .config import Settings
from .constants import WARNING_ABUSIVE_LANGUAGE_BLOCKED, WARNING_PERSONAL_INFO_BLOCKED
from .metrics import moderation_events
from .storage import SessionStore

PHONE_RE = re.compile(r"\+?\d{1,3}[\s\-]?\d{2,4}[\s\-]?\d{2,4}[\s\-]?\d{2,4}")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"https?://[^\s]+")
ADDRESS_RE = re.compile(r"(street|st\\.|road|rd\\.|avenue|ave\\.|calle|carrer|via|boulevard|blvd)", re.IGNORECASE)

ABUSE_KEYWORDS = {
    "kill you",
    "hate you",
    "stupid",
    "idiot",
    "die",
    "dox",
    "go die",
    "trash",
    "worthless",
}
SELF_HARM_KEYWORDS = {
    "kill myself",
    "end it all",
    "suicide",
    "overdose",
    "no reason to live",
    "self harm",
    "cut myself",
    "i want to die",
}


@dataclass
class ModerationDecision:
    allow: bool
    block_code: str | None = None
    crisis: bool = False
    end_session: bool = False
    banned: bool = False
    strikes: int = 0


def check_pii(text: str) -> bool:
    return any(pattern.search(text) for pattern in (PHONE_RE, EMAIL_RE, URL_RE, ADDRESS_RE))


def check_abuse(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in ABUSE_KEYWORDS)


def check_self_harm(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in SELF_HARM_KEYWORDS)


def moderate_message(token: str, role: str, content: str, store: SessionStore, settings: Settings) -> ModerationDecision:
    # PII first: block and warn, do not deliver.
    if check_pii(content):
        strikes = store.increment_strike(token, amount=0)  # read current
        store.log_incident(
            {"type": "PERSONAL_INFO_BLOCKED", "code": WARNING_PERSONAL_INFO_BLOCKED, "token": token, "role": role},
            retention_days=settings.incident_retention_days,
        )
        moderation_events.labels(type="PERSONAL_INFO_BLOCKED").inc()
        return ModerationDecision(allow=False, block_code=WARNING_PERSONAL_INFO_BLOCKED, strikes=strikes)

    # Abuse: block, warn, increment strike; maybe ban/end.
    if check_abuse(content):
        strikes = store.increment_strike(token, amount=1)
        store.log_incident(
            {"type": "ABUSE_FLAG", "code": WARNING_ABUSIVE_LANGUAGE_BLOCKED, "token": token, "role": role},
            retention_days=settings.incident_retention_days,
        )
        moderation_events.labels(type="ABUSE_FLAG").inc()
        decision = ModerationDecision(allow=False, block_code=WARNING_ABUSIVE_LANGUAGE_BLOCKED, strikes=strikes)
        if strikes >= settings.abuse_ban_threshold:
            store.ban_token(token)
            store.log_incident(
                {"type": "BAN", "code": WARNING_BANNED, "token": token, "role": role, "reason": "ABUSE_THRESHOLD"},
                retention_days=settings.incident_retention_days,
            )
            moderation_events.labels(type="BAN").inc()
            decision.banned = True
            decision.end_session = True
        elif strikes >= settings.abuse_end_session_threshold:
            decision.end_session = True
        return decision

    # Self-harm indicators: allow but flag crisis message if repeats.
    crisis = False
    if check_self_harm(content):
        strikes = store.increment_self_harm(token)
        store.log_incident(
            {"type": "SELF_HARM_FLAG", "code": WARNING_CRISIS_LANGUAGE_DETECTED, "token": token, "role": role},
            retention_days=settings.incident_retention_days,
        )
        moderation_events.labels(type="SELF_HARM_FLAG").inc()
        crisis = strikes >= settings.self_harm_crisis_threshold
    return ModerationDecision(allow=True, crisis=crisis)
