# Lifeline Mobile

Flutter demo app for the Lifeline portfolio MVP.

## Run

Default API URL is `http://10.0.2.2:8000`, which points Android emulators to the host machine.

```bash
flutter pub get
flutter run --dart-define=LIFELINE_API_BASE=http://10.0.2.2:8000
```

For a deployed backend:

```bash
flutter run --dart-define=LIFELINE_API_BASE=https://your-api-domain.example
```

## Demo Flow

- Seeker mode starts a request and opens the chat once matched.
- Volunteer mode toggles availability, polls for assigned requests, and supports accept/decline.
- Active sessions show timer updates, messages, system notices, warnings, and a leave action.

## Deferred Production Work

- Firebase Cloud Messaging.
- Store-ready privacy policy and terms acceptance.
- In-app UGC report/block flows.
- Release signing and Play Store listing assets.
