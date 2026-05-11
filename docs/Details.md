## 1. Product goals, personas, success criteria

### Product goals (MVP)

- Provide **instant 1-on-1 anonymous chat** within ~20 seconds median.
    
- Enforce **5-minute, ephemeral sessions** with hard cutoff.
    
- Make it **safe enough** for distressed users and **lightweight enough** for volunteers.
    

### Personas

**Seeker “L”**

- 18–40, lonely, high anxiety about burdening friends.
    
- Uses phone at night, scrolling, intrusive suicidal thoughts.
    
- Needs: _someone now_, low friction, no identity, no judgment.
    

**Volunteer “V”**

- 20–45, has some emotional resilience, not a professional.
    
- Wants to help without long-term commitment.
    
- Needs: clear boundaries (5 minutes), simple guidance, emotional safety.
    

### Success criteria (MVP)

- Median time from “I need someone” → session start: **≤ 20 s**.
    
- % of seeker requests that get matched: **≥ 80%** (during active hours).
    
- % of sessions that reach natural 5 minute completion (not drops): **≥ 70%**.
    
- Queue timeout max: **30 s** before fallback message.
    
- App crash rate: **< 1%** of sessions.
    

> “MVP complete” = end-to-end: seeker button → matched → 5-min chat → teardown, with safety, logs, and monitoring in place.

---

## 2. Flows, edge cases & state definitions

### Matching rules

- Seeker requests help → enqueue in `seekers` queue with timestamp.
    
- Volunteers set `status = available`.
    
- Matching engine:
    
    - Always match **oldest seeker** to **longest-waiting available volunteer**.
        
    - Retry window: if no volunteer accepts within **20s**, show fallback.
        
    - Max queue length: configurable (e.g. 100); beyond that, show “high load” message.
        

### Session state machine

States (per session):

- `REQUESTED` → seeker pressed button
    
- `MATCHING` → looking for volunteer
    
- `PENDING_ACCEPT` → volunteer notified, waiting accept
    
- `ACTIVE` → 5-minute chat running
    
- `ENDED_TIMEOUT` → 5 minutes reached
    
- `ENDED_SEEKER_LEFT`
    
- `ENDED_VOLUNTEER_LEFT`
    
- `FAILED_NO_VOLUNTEER`
    
- `FAILED_ERROR`
    

### Edge cases

- **Volunteer drops mid-session**
    
    - Server detects WS close from volunteer.
        
    - Session → `ENDED_VOLUNTEER_LEFT`.
        
    - Seeker sees: “The connection was interrupted. You can start another session.”
        
    - No auto-rematch in the same session (keeps logic simple).
        
- **Seeker drops mid-session**
    
    - Same logic reversed.
        
- **Network/push failure**
    
    - If volunteer never sees notification or can’t accept, session remains `PENDING_ACCEPT` until 20s timeout → `FAILED_NO_VOLUNTEER`.
        
- **Reconnect behavior**
    
    - No reconnect to same session (statelessness & ephemerality).
        
    - If connection dies, user must start a new session.
        
- **Cancellation**
    
    - Seeker cancels in `MATCHING` or `PENDING_ACCEPT` → session → `CANCELLED_BY_SEEKER`.
        

---

## 3. API contracts

### Auth / identity

- No accounts for seekers.
    
- Each app instance gets a **device-bound anonymous token**:
    
    - `POST /auth/anonymous` → `{ token: <jwt> }`
        
    - JWT contains:
        
        - `sub`: random UUID
            
        - `role`: `seeker` or `volunteer`
            
        - `exp`: e.g. 30 days
            
- Volunteers: same, but with `role=volunteer + hasCompletedOnboarding=true`.
    

---

### REST API (HTTP)

**POST /session/request**

Seeker asks for help.

Request:

`{   "client_capabilities": {     "platform": "android",     "version": "1.0.0"   } }`

Response:

`{   "session_id": "uuid",   "status": "MATCHING",   "estimated_wait_seconds": 15 }`

**POST /session/cancel**

`{   "session_id": "uuid" }`

**POST /volunteer/status**

`{   "available": true }`

Response:

`{ "status": "ok" }`

**POST /volunteer/accept**

`{   "session_id": "uuid" }`

Response:

`{   "status": "ACCEPTED" }`

Error codes: `400` invalid state, `404` session not found, `409` already taken.

---

### WebSocket protocol

Endpoint: `/ws`

Client connects with JWT via query:  
`/ws?token=<jwt>&session_id=<uuid>&role=seeker|volunteer`

Message format (JSON):

**Client → Server**

`{   "type": "message",   "session_id": "uuid",   "content": "text here" }`

**Server → Client events**

`// text message from peer {   "type": "message",   "from": "seeker" | "volunteer",   "content": "..." }`

`// timer sync {   "type": "timer_update",   "remaining_seconds": 287 }`

`// session state changes {   "type": "session_state",   "state": "ACTIVE" | "ENDED_TIMEOUT" | "ENDED_VOLUNTEER_LEFT" | "ENDED_SEEKER_LEFT" | "FAILED_NO_VOLUNTEER" }`

`// moderation warning {   "type": "warning",   "code": "PERSONAL_INFO_BLOCKED",   "message": "For your safety, we blocked part of that message." }`

`// error {   "type": "error",   "code": "INVALID_SESSION",   "message": "Session is no longer active." }`

Timer source of truth = server. Client shows local countdown but is corrected by `timer_update` messages.

---

## 4. Safety & moderation policy

### Filters

- Regex + keyword-based detection for:
    
    - Phone numbers, emails, URLs, addresses, GPS-like strings.
        
    - Explicit self-harm instructions.
        
    - Hate/abuse terms.
        

Behavior:

- For personal info: **block message**, send `warning` event, do not deliver.
    
- For abuse:
    
    - First offense: block + warning.
        
    - Repeated / severe: auto-end session + increment `strikes` for offender; if volunteer, ban UID after threshold.
        

### Escalation

- MVP: no human-in-the-loop live moderation (keeps infra lean).
    
- Instead:
    
    - System may show pre-configured crisis resource message if high-risk language appears multiple times.
        

### “Everything has been erased” vs logging

- No **content** logs, ever.
    
- Allowed to keep **aggregated metrics**:
    
    - Session counts, durations, states, timestamps.
        
    - All keyed by **non-linkable, rotated token IDs**.
        
- No IP stored long-term; IP can be in short-term infra logs with automatic rotation/retention (e.g. 7 days).
    

### Data retention

- Conversations: in-memory only, destroyed at end of session.
    
- Metrics: stored without any PII or stable identifiers, used for monitoring.
    

---

## 5. Security & privacy model

- Auth:
    
    - Anonymous JWT per device, rotated on renewal.
        
    - Volunteers flagged by role only.
        
- Rate limiting:
    
    - Per token & per IP:
        
        - Seeker sessions: e.g. max 5/hour.
            
        - Volunteer accepts: rate-limited to avoid abuse.
            
- Transport:
    
    - TLS everywhere (HTTPS + WSS).
        
- Storage:
    
    - Redis for ephemeral session state only.
        
    - Postgres (optional) for metrics & bans, no PII columns.
        
- Secrets:
    
    - Managed via env vars / KMS depending on cloud.
        
- Compliance stance:
    
    - GDPR: no PII, clear privacy policy, data minimization.
        

---

## 6. Notifications

Provider: **Firebase Cloud Messaging** (FCM) for both Android and iOS.

### Payload (volunteer)

`{   "to": "<fcm_token>",   "data": {     "type": "NEW_SESSION_REQUEST",     "session_id": "uuid"   },   "notification": {     "title": "Someone needs to talk",     "body": "A 5-minute session is available."   } }`

Mobile behavior:

- Background: tap notification → volunteer app opens → checks `/session/:id` state → if `PENDING_ACCEPT`, show accept dialog.
    
- Foreground: in-app modal.
    

Failure fallback:

- If no volunteers accept within timeout, seeker receives graceful failure message via API + WS.
    

---

## 7. UX spec baseline

### Typography

- Heading: 24–28 px, semi-bold.
    
- Body: 14–16 px.
    
- Monospace nowhere; keep soft.
    

### Color tokens (not exact hex, just intentions)

- Background: near-black, slightly warm.
    
- Primary: soft desaturated blue/teal.
    
- Accent (error): desaturated red.
    
- Text: off-white.
    

### Layout

- Spacing scale: 4/8/12/16/24/32 px.
    
- Min tap size: 44x44 px.
    
- No avatars, no profile pics.
    

### Accessibility

- Contrast ≥ WCAG AA where possible.
    
- Dynamic type support (respect OS font size).
    
- Haptics:
    
    - Light haptic on button press.
        
    - Slight vibration on connection/disconnection.
        

### Platforms

- Min Android SDK 23 (7.0+).
    
- Min iOS 14+.
    

Localization:

- MVP: English only.
    
- Prepare text via string keys so adding ES/other languages later is trivial.
    

---

## 8. Infra / ops

### Environments

- `dev`: local docker-compose.
    
- `staging`: single VPS (backend + Redis).
    
- `prod`: VPS or simple managed container cluster.
    

### Monitoring / metrics

- Prometheus or simpler hosted metrics:
    
    - `sessions_created_total`
        
    - `sessions_completed_total`
        
    - `sessions_failed_no_volunteer_total`
        
    - `session_duration_seconds`
        
    - `matching_wait_seconds`
        
- Alerts:
    
    - Error rate > X/min.
        
    - No sessions completed in Y minutes.
        
    - Redis/CPU at 90% for Z minutes.
        

Logs:

- Structured JSON logs, no message content, no PII.
    

Domain/SSL:

- Domain like `fiveminutes.app` (or whatever).
    
- Use Let’s Encrypt via Traefik.
    

Backups:

- Only for metrics DB. No chat content to backup.
    

---

## 9. Testing / quality

### Backend

- Unit tests:
    
    - Matching logic.
        
    - Session state machine.
        
    - Timer enforcement.
        
- Integration:
    
    - WS handshake + message relay between two fake clients.
        
- Load:
    
    - Target: e.g. 500 concurrent sessions.
        
    - Simulate bursts: 100 seekers in 10 seconds.
        

### Mobile

- Widget tests:
    
    - Timer UI.
        
    - State transitions (landing → connecting → chat → end).
        
- E2E:
    
    - Manual first: two devices connect via staging backend.
        

### Chaos

- Kill volunteer connection mid-session: ensure seeker gets useful state.
    
- Delay timer updates: ensure server still ends session at 5 min.
    

---

## 10. Project logistics & milestones

Assume: 1–2 devs, part-time.

### Milestones

1. **M1 – Core loop (E2E, no push yet)**
    
    - Anonymous auth
        
    - Matching
        
    - WebSocket chat
        
    - Timer & teardown
        
2. **M2 – Volunteer mode + notifications**
    
    - Volunteer onboarding & toggle
        
    - FCM wired
        
    - Basic safety filters
        
3. **M3 – Safety hardening & monitoring**
    
    - Abuse filters
        
    - Metrics + alerts
        
    - Legal copy (ToS, disclaimer, privacy)
        
4. **M4 – Alpha release (small closed group)**
    
    - Deploy stable backend
        
    - Publish test builds
        
    - Collect feedback manually
        

Risks (top 3):

- Legal / liability concerns around suicide-related content.
    
- Psychological safety of volunteers (burnout).
    
- Abuse/trolling if the app is discovered as a “playground.”
    

Mitigation: tight scope, clear disclaimers, short sessions, aggressive banning.

---


1. API specifics
1.1 HTTP status codes & error payload

Success:

200 OK – standard success

201 Created – if you ever create a persistent resource (probably not needed for MVP)

204 No Content – for actions with no response body (optional)

Client errors:

400 Bad Request – invalid payload, missing fields

401 Unauthorized – invalid/expired JWT

403 Forbidden – banned user, role mismatch

404 Not Found – session or resource not found

409 Conflict – invalid state transition (e.g. session already taken/ended)

429 Too Many Requests – rate limiting

Server errors:

500 Internal Server Error

503 Service Unavailable – e.g. maintenance mode

Error payload schema (consistent):

{
  "error": {
    "code": "SESSION_CONFLICT",
    "message": "Session is no longer available.",
    "details": null
  }
}


Fields:

code: stable, machine-parseable string

message: user-readable, short

details: optional (debug info, usually null in prod)

1.2 Rate-limit headers

Use standard-ish headers:

X-RateLimit-Limit: integer (max requests / window)

X-RateLimit-Remaining: integer

X-RateLimit-Reset: unix timestamp when window resets

Per:

IP + token for seekers

token for volunteers

1.3 Versioning

Simple strategy:

Base path: /v1/...

WebSocket endpoint: /v1/ws

New major changes → /v2

Old versions deprecated after some grace period

1.4 /session/request ETA updates

Decision:

/session/request returns one-time ETA (best guess).

Live updates (e.g. state change MATCHING → FAILED_NO_VOLUNTEER) delivered via:

WebSocket if already connected, or

Polling GET /session/{id}/status every 3–5 seconds if WS isn’t connected yet.

For MVP:

App flow:

POST /session/request

Immediately open WS with session_id

If WS fails, fall back to polling GET /session/{id}/status

2. Session lifecycle & timeouts
2.1 Allowed transitions

States:

REQUESTED

MATCHING

PENDING_ACCEPT

ACTIVE

ENDED_TIMEOUT

ENDED_SEEKER_LEFT

ENDED_VOLUNTEER_LEFT

FAILED_NO_VOLUNTEER

CANCELLED_BY_SEEKER

FAILED_ERROR

Transitions (simplified):

REQUESTED → MATCHING

MATCHING → PENDING_ACCEPT (volunteer notified)

MATCHING → FAILED_NO_VOLUNTEER (wait timeout)

PENDING_ACCEPT → ACTIVE (volunteer accepts)

PENDING_ACCEPT → FAILED_NO_VOLUNTEER (accept timeout)

MATCHING → CANCELLED_BY_SEEKER

PENDING_ACCEPT → CANCELLED_BY_SEEKER
(yes, seeker can cancel while volunteer hasn’t accepted yet)

From ACTIVE:

ACTIVE → ENDED_TIMEOUT (5 minutes exact)

ACTIVE → ENDED_SEEKER_LEFT

ACTIVE → ENDED_VOLUNTEER_LEFT

ACTIVE → FAILED_ERROR (server catastrophe)

Terminal states: all except REQUESTED/MATCHING/PENDING_ACCEPT/ACTIVE.

2.2 Timeouts (constants)

Define in config:

MATCHING_MAX_WAIT_SECONDS = 30
(hard cap from seeker request to volunteer accept; beyond → FAILED_NO_VOLUNTEER)

PENDING_ACCEPT_TIMEOUT_SECONDS = 20
(time allowed for volunteer to tap “Accept” after notification)

SESSION_DURATION_SECONDS = 300
(5 minutes, server-enforced)

SESSION_GRACE_PERIOD_SECONDS = 5
(buffer for WS cleanup after timeout before force close)

3. Safety & legal specifics
3.1 User-facing disclaimer copy (MVP version)

Landing screen (small text):

This is not a medical or therapy service.
If you are in immediate danger or planning to harm yourself, please contact your local emergency services or a crisis hotline.

On first app launch, blocking modal:

Important

This app offers anonymous, short conversations with volunteers, not professionals.
Volunteers are not therapists and cannot provide medical, legal, or emergency help.
If your life is in danger, or someone else’s is, contact emergency services immediately.

[I understand and want to continue]

3.2 Strike thresholds

For volunteers:

1st severe violation → immediate ban.

3 minor violations (abusive language, ignoring guidelines) → ban.

For seekers:

3 severe abuse/trolling events → token banned.

Ban is on anonymous token; can optionally ban by IP range if repeated.

3.3 Keyword / regex examples

You’ll refine this later, but MVP set:

Personal info patterns:

Phone numbers:

/\+?\d{1,3}[\s\-]?\d{2,4}[\s\-]?\d{2,4}[\s\-]?\d{2,4}/

Emails:

/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/

URLs:

/https?:\/\/[^\s]+/

Addresses (very fuzzy):

(street|st\.|road|rd\.|avenue|ave\.|calle|carrer|via|boulevard|blvd)
combined with numbers.

On match:

Block message content and replace with “[blocked for your safety]”.

Send warning event.

Self-harm / suicide indicators:
List of keywords like "kill myself", "end it all", "suicide", "overdose", "no reason to live", etc.
For MVP:

These do not block messages.

They trigger:

internal “risk flag” counter.

optional automatic crisis resource message after N occurrences.

3.4 Incident logs & bans retention

Ban records: retain 1 year:

bans table: id, token_hash, reason, created_at, last_seen_at.

Incident logs (non-content, just type + timestamp + token hash):

Retain 90 days.

4. Privacy & telemetry
4.1 Metrics schema (Postgres example)

metrics_sessions

id (uuid, PK)

created_at (timestamp)

ended_at (timestamp)

end_state (enum: ENDED_TIMEOUT, ENDED_SEEKER_LEFT, etc.)

role_seeker_platform (text)

role_volunteer_platform (text, nullable)

matching_wait_ms (int)

duration_ms (int)

metrics_abuse

id (uuid)

created_at

type (e.g. PERSONAL_INFO_BLOCKED, ABUSE_FLAG)

role (seeker/volunteer)

bans

as above.

No user identifiers except token hash:

token_hash = HMAC(secret, raw_token) so it’s non-reversible.

4.2 Logs retention

Application logs:

Retain 30 days, then purge.

No content, no PII, no token values.

Infra logs:

If on cloud provider, keep default if reasonable, otherwise also 30 days.

4.3 Consent / opt-out UX

MVP:

On first launch: show privacy notice (short summary + link to full policy).

Implicit consent by continuing; no custom telemetry toggles since we don’t collect personal data or behavior tracking beyond basic metrics.

Telemetry limited strictly to:

session counts

durations

success/failure status.

You can add an “About & Privacy” screen later that explains this in plain language.

5. Notifications specifics
5.1 Token registration / refresh

Flow:

On app launch:

Get FCM token.

If changed or new, call:

POST /device/register:

{
  "fcm_token": "string",
  "platform": "android|ios",
  "role": "volunteer"
}


Backend stores it in devices table:

id, token_hash, platform, role, volunteer_id, last_seen_at.

When volunteer toggles “Available = true”:

Backend associates their current device token with that volunteer as active target.

5.2 iOS background handling

Use FCM with:

notification payload for user-visible banner.

Optionally content-available: 1 in aps for silent refresh if needed (not essential for MVP).

Volunteer flow:

Notification tapped → opens app → app reads data.session_id → calls /session/{id}/status → shows accept modal.

5.3 Retry / backoff policy for failed sends

On FCM failure:

For transient errors (rate, internal): retry with exponential backoff: 1s, 2s, 4s (max 3 attempts).

For permanent errors (invalid token, not registered): delete token from DB.

No repeated notification spam; one notification per seeker request per volunteer.

6. Mobile UX concrete tokens
6.1 Colors (hex suggestions)
BACKGROUND:       #05070A
SURFACE:          #12151C
SURFACE_ELEVATED: #1A1F29
PRIMARY:          #4BA3C7
PRIMARY_SOFT:     #3A7D9A
TEXT_PRIMARY:     #F5F7FA
TEXT_MUTED:       #A0A7B3
ACCENT_DANGER:    #D75C5C
BORDER_SUBTLE:    #2B3140


Expose as constants in Flutter app_theme.dart.

6.2 Type scale

Display: 28 / 32 px, semi-bold – for main phrases like “You’re not alone.”

Title: 20 / 22 px – screen titles.

Body: 16 px – main body text.

Caption: 12–13 px – disclaimers, secondary text.

6.3 Spacing system

Spacing units (kSpace1 = 4, etc.):

4, 8, 12, 16, 24, 32
Use:

24/32 for big top margins.

16 between major blocks.

8 between related items.

6.4 Empty / error states

Network loss (seeker):

We couldn’t connect right now.
Check your connection and try again.

Buttons:

[ Try again ]

No volunteers available:

No one is available right now.
This is not your fault. You can try again in a moment or contact a local hotline.

Push denied (volunteer):

Notifications are disabled.
You may miss people who need you.
Enable notifications in system settings to receive session requests.

6.5 Haptics

Android:

Button tap: HapticFeedback.lightImpact

Session start: HapticFeedback.mediumImpact

Session end: HapticFeedback.heavyImpact

iOS:

Map similarly via FeedbackType.light, medium, heavy.

Quiet but noticeable.

7. Infra decisions
7.1 Staging / prod stack

Provider: keep it simple, e.g. DigitalOcean or similar VPS provider.

Staging:

1 × droplet: 2 vCPU, 4 GB RAM

Runs backend + Redis + Traefik via docker-compose.

No autoscaling, just manual.

Prod (MVP):

1 × 4 vCPU, 8 GB RAM droplet.

Same docker-compose setup.

Off-box managed Postgres (small instance).

Redis: container is fine, or managed Redis if you want.

You can move to managed Kubernetes later if you enjoy suffering.

7.2 CI steps

Backend ci.yml:

black/ruff for lint.

pytest for tests.

Optional: build Docker image on main merges.

Flutter CI (later):

flutter analyze

flutter test

7.3 Secret management

MVP:

.env files on server with:

JWT_SECRET

REDIS_URL

DB_URL

FCM_SERVER_KEY

Later:

Move to KMS/Secret Manager if you move to bigger infra.

7.4 SSL / Traefik defaults

Basic Traefik dynamic config:

HTTP to HTTPS redirect

TLS via Let’s Encrypt:

certresolver = letsencrypt

HTTP challenge or TLS-ALPN challenge

Middlewares:

redirectscheme (http → https)

rateLimit basic (per IP)

Routes:

api.yourdomain → backend (port 8000)

ws.yourdomain → same backend (WS upgrade allowed)

8. Testing targets & acceptance criteria
8.1 Load / latency targets

Concurrent sessions target: 500 simultaneous ACTIVE sessions.

p95 HTTP latency (for simple endpoints): < 200 ms.

p95 WS message relay latency: < 200 ms.

p99 WS message relay: < 500 ms under target load.

WS lag measured as time from sending by one client to receiving by the other, server in the middle.

8.2 Per-milestone acceptance

M1 – Core loop

Seeker can:

Press button

Get matched to a volunteer (even if volunteer is a second device in dev)

Chat for 5 minutes

See timer end and auto-disconnect.

No message content stored after session in Redis or DB.

Session state transitions logged correctly (in metrics).

M2 – Volunteer + notifications

Volunteer receives push when available.

Volunteer can accept and get into chat from cold start (app closed).

At least basic safety filters:

Emails, phone numbers, URLs blocked.

Warnings delivered.

Rate limiting:

429 returned when seeker exceeds configured session rate.

M3 – Safety & monitoring

Abuse / bans functional:

3 abuse events → banned token.

Metrics visible in dashboard:

Number of sessions, end states, average duration.

Alerts configured for basic errors.

M4 – Alpha

No critical crashes in a small, real-world test.

P95 match time ≤ 20 seconds given enough test volunteers.

Clear disclaimer and privacy text shown on first launch.



1. Brief threat model & DDoS / abuse mitigations
1.1 Threat model (MVP-level)

Primary threats:

Trolling / harassment: people using the app to abuse seekers or volunteers.

Flooding / DDoS: bots spamming /session/request, WS connections, or message spam.

Enumeration / probing: trying to infer who is online, scraping usage patterns.

Account / role abuse: pretending to be a volunteer to harm seekers.

Infra exhaustion: Redis / backend overload, causing legit sessions to fail.

We accept:

This is not a banking app.

Adversaries are likely bored idiots, not nation-state actors.

1.2 Mitigations

WebSocket abuse limits:

Max concurrent WS connections per token: MAX_WS_PER_TOKEN = 2.

Max WS connections per IP: MAX_WS_PER_IP = 10 (configurable).

Idle timeout: if no messages in IDLE_TIMEOUT_SECONDS = 60, close WS.

Message limits:

Max message size: MAX_MESSAGE_BYTES = 2_000 (~2kB).

Max messages per minute per participant: MAX_MESSAGES_PER_MIN = 60 (1 msg/sec avg).

If exceeded:

Temporarily ignore messages and send warning event: RATE_LIMITED.

If clearly malicious (spam flood), end session and increment strikes.

IP blocking strategy:

Maintain in-memory + DB-backed ip_reputation:

Track:

failed_auth_count

banned_token_count

session_request_rate

If thresholds exceeded:

Soft block: respond 429 to /session/request for that IP for X minutes.

Hard block: blacklist IP for IP_BLOCK_DURATION_MINUTES (e.g. 60).

No fancy geo-blocking; just behavioral blocking.

Matching abuse:

Require valid volunteer status + onboarding flag to accept sessions.

Banned volunteers cannot change token or status.

2. Crash / error reporting for mobile

Pick one: Sentry or Firebase Crashlytics.
Since we’re already using FCM, easiest path: Crashlytics.

2.1 Tool: Firebase Crashlytics

Collected:

Stack traces

App version

Platform / OS version

Basic device model

Explicitly not collected:

Messages

Session IDs

Tokens

Any user-entered text

2.2 Data minimization

Implementation guidelines:

No logging of message contents in crash logs.

Use generic tags only:

session_state = ACTIVE/ENDED/FAILED

role = seeker/volunteer

Wrap WS errors / API errors with sanitized messages, not raw payloads.

Disable automatic breadcrumbs that might store URLs with tokens; scrub them before sending.

3. Seeker notification strategy

For MVP:

No push notifications to seekers.

Reason:

The app is built as an immediate interaction: seeker taps “I need someone,” stays in app until matched or failed.

No background scheduling, no pending “someone will answer later.”

Behavior:

If no volunteer: show in-app message:
“No one is available right now. Try again or contact a hotline.”

Later you could do seeker nudges, but that complicates expectations and infra. For now: no seeker-side push.

4. Volunteer token lifecycle

Problem: app uninstall/reinstall, or token changes.

4.1 FCM token lifecycle

On each app start:

Get FCM token.

Call POST /device/register with:

fcm_token

platform

role

Backend:

Hash token and either:

Insert new row if not exists.

Update last_seen_at for existing hash.

If backend receives FCM errors indicating “not registered”:

Mark token as inactive.

If app is uninstalled:

FCM will eventually return error for that token → backend marks it inactive.

If reinstalled:

New FCM token generated.

App registers new token → backend uses that.

4.2 Volunteer identity & availability

Volunteer is identified by:

Anonymous JWT sub (volunteer_id)

Linked to one or more device tokens

On status change:

POST /volunteer/status with { available: true }

Backend:

Marks volunteer as available only if:

At least one active device token is registered.

On app uninstall:

Their tokens go invalid.

They can’t actually receive sessions until app is run again and re-registers a token.

No long-term problem there.

5. Config defaults & sync between backend/mobile

You don’t want magic numbers scattered around. So:

5.1 Backend config (env vars)

Env var names (with defaults):

APP_ENV=dev
JWT_SECRET=<required>
JWT_EXP_DAYS=30

MATCHING_MAX_WAIT_SECONDS=30
PENDING_ACCEPT_TIMEOUT_SECONDS=20
SESSION_DURATION_SECONDS=300
SESSION_GRACE_PERIOD_SECONDS=5

MAX_WS_PER_TOKEN=2
MAX_WS_PER_IP=10
IDLE_TIMEOUT_SECONDS=60

MAX_MESSAGE_BYTES=2000
MAX_MESSAGES_PER_MIN=60

SEEKER_SESSION_RATE_PER_HOUR=5

IP_BLOCK_THRESHOLD_SCORE=10
IP_BLOCK_DURATION_MINUTES=60

LOG_RETENTION_DAYS=30
METRICS_RETENTION_DAYS=365


Expose them in a /v1/config/public endpoint for mobile, only for non-sensitive things:

GET /v1/config/public →

{
  "session_duration_seconds": 300,
  "matching_max_wait_seconds": 30,
  "timer_sync_interval_seconds": 5,
  "max_message_length": 2000
}


JWT secrets, rate limits, IP stuff stay server-only.

5.2 Mobile config

Mobile reads /config/public once at app startup and caches these, so backend and app stay in sync without releasing a new app every time you change a timeout.

Flutter side: define something like:

class AppConfig {
  final int sessionDurationSeconds;
  final int matchingMaxWaitSeconds;
  final int timerSyncIntervalSeconds;
  final int maxMessageLength;

  // from backend or defaults
}


Fallback defaults baked in if request fails.

That covers threat model, DDoS/abuse handling, crash reporting, seeker/volunteer token behavior, and config sync.