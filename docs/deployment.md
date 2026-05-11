# Deployment Notes

This project is ready for a portfolio demo deployment, not a public Play Store production launch.

## Recommended Demo Stack

- A small VPS or managed Docker host.
- FastAPI backend container.
- Redis container or managed Redis.
- Postgres container or managed Postgres.
- HTTPS reverse proxy such as Traefik, Caddy, or Nginx.
- Environment variables managed outside Git.

## Required Environment

- `JWT_SECRET`
- `ADMIN_JWT_SECRET`
- `REDIS_URL`
- `DB_URL`
- `APP_ENV=prod`

Use `postgres` and `redis` hostnames only inside Docker Compose networks. Use `localhost` when running the backend directly on your machine.

## Deployment Steps

1. Provision host and install Docker.
2. Copy the repo or deploy from GitHub.
3. Create production environment variables on the host.
4. Start Postgres and Redis.
5. Run `alembic -c alembic.ini upgrade head` inside the backend image.
6. Start backend behind HTTPS reverse proxy.
7. Verify `GET /health`.
8. Build the Android demo with `--dart-define=LIFELINE_API_BASE=https://your-api-domain`.

## Production Caveats

- Restrict CORS before real users.
- Protect or disable `/metrics` publicly.
- Replace demo volunteer polling with Firebase Cloud Messaging.
- Add UGC reporting/blocking and terms acceptance before Play Store release.
- Add hosted privacy policy and app content declarations for health-related functionality.
