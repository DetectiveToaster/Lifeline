import "dart:async";

import "package:flutter/foundation.dart";

import "../models/session_state.dart";
import "../models/ws_event.dart";
import "../services/api_client.dart";
import "../services/ws_client.dart";
import "../storage/token_store.dart";

enum SessionPhase { idle, matching, active, ended, error }

class SessionController extends ChangeNotifier {
  SessionController({
    required ApiClient api,
    required TokenStore tokenStore,
  })  : _api = api,
        _tokenStore = tokenStore;

  final ApiClient _api;
  final TokenStore _tokenStore;
  final WsClient _ws = WsClient();

  SessionPhase phase = SessionPhase.idle;
  SessionState? state;
  String? sessionId;
  int? remainingSeconds;
  String? lastSystemMessage;
  String? lastWarningMessage;

  StreamSubscription<WsEvent>? _subscription;

  Future<void> startSeekerSession() async {
    phase = SessionPhase.matching;
    lastSystemMessage = null;
    lastWarningMessage = null;
    notifyListeners();

    final token = await _tokenStore.getOrCreateToken(api: _api, role: "seeker");
    final response = await _api.requestSession(token: token);
    sessionId = response["session_id"] as String;
    state = sessionStateFromString(response["status"] as String);

    _subscription?.cancel();
    _subscription = _ws
        .connect(token: token, sessionId: sessionId!, role: "seeker")
        .listen(_handleEvent, onError: _handleError);
    notifyListeners();
  }

  Future<void> leaveSession() async {
    if (sessionId == null) {
      return;
    }
    final token = await _tokenStore.getOrCreateToken(api: _api, role: "seeker");
    await _api.leaveSession(token: token, sessionId: sessionId!);
    _ws.sendLeave();
    _ws.close();
    phase = SessionPhase.ended;
    notifyListeners();
  }

  void _handleEvent(WsEvent event) {
    final data = event.data ?? {};
    switch (event.type) {
      case "session_state":
        final raw = data["state"] as String? ?? "FAILED_ERROR";
        state = sessionStateFromString(raw);
        if (state == SessionState.active) {
          phase = SessionPhase.active;
        } else if (state == SessionState.matching || state == SessionState.pendingAccept) {
          phase = SessionPhase.matching;
        } else {
          phase = SessionPhase.ended;
        }
        break;
      case "timer_update":
        remainingSeconds = data["remaining_seconds"] as int?;
        break;
      case "system":
        lastSystemMessage = data["content"] as String?;
        break;
      case "warning":
        lastWarningMessage = data["message"] as String? ?? data["code"] as String?;
        break;
      case "error":
        phase = SessionPhase.error;
        lastWarningMessage = data["message"] as String? ?? data["code"] as String?;
        break;
      default:
        break;
    }
    notifyListeners();
  }

  void _handleError(Object error) {
    phase = SessionPhase.error;
    lastWarningMessage = "Connection error";
    notifyListeners();
  }

  @override
  void dispose() {
    _subscription?.cancel();
    _ws.close();
    super.dispose();
  }
}
