# Lifeline Portfolio Notes

## Problem Statement

Lifeline explores a low-friction support pattern for people who need a short anonymous conversation in a difficult moment. The product intentionally avoids profiles, usernames, avatars, and permanent chat history.

## Architecture Summary

- Flutter mobile app with seeker and volunteer demo flows.
- FastAPI backend with REST endpoints for auth, matching, volunteer status, and session lifecycle.
- WebSocket channel for real-time chat, system events, warnings, and timer updates.
- Redis for ephemeral matching/session state.
- Postgres for bans, strikes, and moderation incident metadata.
- Prometheus metrics endpoint for operational visibility.

## Backend Highlights

- Anonymous JWT auth for seekers and volunteers.
- Oldest-seeker to available-volunteer matching.
- Server-side five minute session timer and terminal state enforcement.
- WebSocket event protocol for messages, state changes, timers, warnings, and system notices.
- Basic moderation for personal information, abuse, self-harm signals, strikes, bans, and crisis resource notices.
- Admin endpoints for viewing incidents and lifting bans.
- Docker Compose stack with Redis, Postgres, migrations, and backend.

## Mobile Highlights

- Calm dark UI designed around a clear timer and minimal identity cues.
- Seeker flow: request help, wait for matching, chat, leave/end state.
- Volunteer flow: availability toggle, request prompt, accept/decline, chat helper prompts.
- Demo mode supports role switching and polling instead of push notifications.
- Warning and system messages are shown without storing chat content locally beyond the active session.

## Safety And Privacy Tradeoffs

- Message content is relayed in memory and not stored in Postgres.
- Moderation incidents store metadata, not message bodies.
- Anonymous tokens reduce account friction but are not a full trust-and-safety model.
- Crisis resources are informational; the app is not therapy, emergency response, or medical care.

## Demo Limitations

- Firebase Cloud Messaging is deferred.
- UGC reporting and blocking are not yet implemented.
- Legal copy, privacy policy, terms acceptance, and Play Store health declarations are not complete.
- Moderation is deterministic and intentionally limited for MVP scope.

## Future Work

- Add in-app report/block flows.
- Add FCM for volunteer notifications.
- Add stronger volunteer onboarding and abuse review workflows.
- Lock down production CORS and metrics exposure.
- Prepare Play Store privacy policy, content rating, health declaration, and closed testing track.

## Portfolio Angles

- Real-time systems: WebSockets, session timers, state machines.
- Privacy-aware design: ephemeral chat and metadata-only safety logging.
- Product judgment: narrowed public-release scope into a responsible portfolio MVP.
- Full-stack delivery: Flutter client, FastAPI backend, Redis/Postgres infrastructure, Docker deployment.
