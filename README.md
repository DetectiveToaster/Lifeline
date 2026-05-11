# Lifeline

Lifeline is a portfolio MVP for anonymous, time-boxed, one-to-one support chat. The demo focuses on a five minute seeker/volunteer conversation, ephemeral messaging, moderation warnings, and a calm mobile experience.

This is not positioned as a production mental health service or a public Google Play release yet. Play Store publication is deferred until reporting/blocking, legal copy, privacy policy, health declarations, and stronger trust-and-safety workflows are complete.

## Current Status

- Backend: functional FastAPI demo backend with JWT auth, Redis matching, WebSockets, timers, moderation, metrics, admin endpoints, Postgres persistence, Docker, and Alembic.
- Mobile: Flutter portfolio demo with seeker and volunteer modes, matching, accept/decline, chat UI, timer UI, system messages, and warning handling.
- Deployment: local Docker stack is prepared. Production deployment still needs HTTPS reverse proxy configuration and real hosted secrets.

## Structure

- `backend/`: FastAPI API and WebSocket backend.
- `mobile/`: Flutter Android/demo app.
- `docs/`: specs, wireframes, portfolio notes, and deployment notes.
- `scripts/`: local smoke-test helpers.
- `docker-compose.yml`: local backend, Redis, Postgres, and migration stack.

## Local Backend

Copy `.env.example` to `.env`, then replace secrets with local random values:

```bash
cp .env.example .env
docker compose up --build
```

The compose stack starts Postgres, Redis, runs Alembic migrations, then starts the backend.

Useful endpoints:

- `GET http://localhost:8000/health`
- `GET http://localhost:8000/metrics`
- `POST http://localhost:8000/v1/auth/anonymous`

Run a local smoke test after the stack is up:

```bash
python scripts/smoke_backend.py http://localhost:8000
```

## Local Mobile Demo

Run the Flutter app against the Docker backend:

```bash
cd mobile
flutter pub get
flutter run --dart-define=LIFELINE_API_BASE=http://10.0.2.2:8000
```

Use two emulators/devices, or switch roles in the app:

- Seeker: tap `I need someone`.
- Volunteer: toggle `Available for requests`, accept the pending request, then chat.

## Portfolio Notes

See [docs/portfolio-notes.md](docs/portfolio-notes.md) for case-study copy, architecture points, demo limitations, and future work.

## Demo Limitations

- Push notifications are intentionally deferred; volunteer assignment uses polling for portfolio demo mode.
- Chat content is relayed over WebSockets and not persisted, but this has not been externally audited.
- Open CORS and admin JWT are acceptable for local/portfolio demo only.
- A public Play Store release requires UGC reporting/blocking, terms acceptance, health policy work, and privacy/legal review.
