# Lifeline Backend (FastAPI)

Early scaffold for Phase 1 MVP per `Details.md`.

## Quickstart

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export JWT_SECRET=change-me
export ADMIN_JWT_SECRET=admin-secret
uvicorn app.main:app --reload --port 8000
```

Health check: `GET http://localhost:8000/health`

## Useful endpoints (v1)

- `POST /v1/auth/anonymous` — returns anonymous JWT (`role` defaults to `seeker`).
- `POST /v1/session/request` — create a session, returns `session_id` + status.
- `POST /v1/session/cancel`
- `POST /v1/session/leave` — explicit leave for seeker/volunteer (ends session).
- `GET /v1/session/{id}/status`
- `POST /v1/volunteer/status`
- `POST /v1/volunteer/accept`
- `POST /v1/volunteer/decline`
- `WS /v1/ws?token=...&session_id=...&role=seeker|volunteer[&locale=en]`
- `GET /v1/config/public` — public runtime constants for mobile.
- `GET /v1/admin/bans` / `DELETE /v1/admin/bans/{token_hash}`
- `GET /v1/admin/incidents`
  - Use `Authorization: Bearer <admin_jwt>` when `ADMIN_JWT_SECRET` is set.

## Notes

- Storage now uses Redis if `REDIS_URL` is set (default `redis://localhost:6379/0` via docker-compose). Falls back to in-memory if Redis is unavailable.
- Matching queue + volunteer availability are handled in Redis.
- Background enforcer ticks once per second to expire matching window (→ `FAILED_NO_VOLUNTEER`) and session duration (→ `ENDED_TIMEOUT`), and emits `session_state`/`timer_update` over WebSocket.
- WebSocket now sends initial state/timer snapshot, enforces message size + per-connection rate limiting, and runs basic moderation: blocks PII, blocks abusive language with strikes/ban thresholds, flags self-harm for crisis message, bans tokens on repeated abuse.
- WebSocket disconnects (or `{"type":"leave"}`) end sessions with `ENDED_*` states and system messages for seeker/volunteer departures.
- REST `POST /v1/session/leave` mirrors the same behavior as WebSocket `leave`.
- HTTP endpoints `/v1/session/request` and `/v1/volunteer/accept` enforce rate limits with `X-RateLimit-*` headers.
- Prometheus metrics exposed at `/metrics` (sessions, moderation, rate limits).
- Optional Postgres persistence via `DB_URL` for bans/strikes/incidents with retention cleanup (hourly maintenance worker).
- To run migrations: `DB_URL=postgresql://... alembic -c alembic.ini upgrade head`.
- Admin endpoints require `Authorization: Bearer <admin_jwt>` signed with `ADMIN_JWT_SECRET`.
- Generate a token locally:

```bash
python - <<'PY'
import os
os.environ["ADMIN_JWT_SECRET"] = "admin-secret"
from app.auth import create_admin_token
print(create_admin_token())
PY
```
- Security/CORS is permissive for local dev; tighten before staging.
