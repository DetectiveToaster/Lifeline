# Lifeline Prototype

Early development scaffold based on `Details.md` and `High level Prototype.md`.

## Structure

- `backend/` — FastAPI MVP scaffold with anonymous auth, session endpoints, volunteer endpoints, matching service, timers, and WebSocket relay.
- `docker-compose.yml` — Local stack with backend + Redis (session/matching use Redis if available).
- `mobile/` — Flutter scaffold (seeker flow + API client + WS handling).

## Backend quickstart

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export JWT_SECRET=change-me
uvicorn app.main:app --reload --port 8000
```

Then hit `GET http://localhost:8000/health`.

Docker: `JWT_SECRET=change-me docker-compose up --build`

## Next steps

- Finish server-enforced timers and matching (done in background enforcer; refine).
- Implement moderation filters and HTTP/WS rate limiting + error codes.
- Flesh out WebSocket events (warnings, more error codes) to match the contract.
- Add tests for state machine, matching, WS relay, and lint/test CI.
- Optional persistence via `DB_URL` for bans/strikes/incidents.
- Admin endpoints require bearer token signed with `ADMIN_JWT_SECRET`.
- Alembic migrations live in `backend/alembic/`.
