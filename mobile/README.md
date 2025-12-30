# Lifeline Mobile (Flutter)

This is a minimal Flutter scaffold that speaks to the Lifeline backend.

## Prereqs

- Install Flutter SDK (3.3+).
- Android Studio + emulator or a physical device.

## Configure API base URL

Default base URL is `http://10.0.2.2:8000` (Android emulator -> localhost).

Override at build/run:

```bash
flutter run --dart-define=LIFELINE_API_BASE=http://10.0.2.2:8000
```

## Run

```bash
cd mobile
flutter pub get
flutter run
```

## Notes

- UI is a minimal seeker-only flow (start/leave) and shows system/warning messages.
- Volunteer flow + chat UI will be added next.
