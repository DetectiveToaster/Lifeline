import "dart:async";

import "package:flutter/foundation.dart";

import "../models/chat_message.dart";
import "../models/session_state.dart";
import "../models/ws_event.dart";
import "../services/api_client.dart";
import "../services/ws_client.dart";
import "../storage/token_store.dart";

enum SessionPhase { idle, matching, pendingAccept, active, ended, error }

enum DemoRole { seeker, volunteer }

class SessionController extends ChangeNotifier {
  SessionController({
    required ApiClient api,
    required TokenStore tokenStore,
  })  : _api = api,
        _tokenStore = tokenStore;

  final ApiClient _api;
  final TokenStore _tokenStore;
  final WsClient _ws = WsClient();

  DemoRole role = DemoRole.seeker;
  SessionPhase phase = SessionPhase.idle;
  SessionState? state;
  String? sessionId;
  int? remainingSeconds;
  String? lastSystemMessage;
  String? lastWarningMessage;
  bool volunteerAvailable = false;
  String? pendingSessionId;
  final List<ChatMessage> messages = [];

  StreamSubscription<WsEvent>? _subscription;
  Timer? _pendingPollTimer;

  void switchRole(DemoRole nextRole) {
    if (phase == SessionPhase.active || phase == SessionPhase.matching || phase == SessionPhase.pendingAccept) {
      return;
    }
    role = nextRole;
    _resetSessionUi();
    notifyListeners();
  }

  Future<void> startSeekerSession() async {
    role = DemoRole.seeker;
    phase = SessionPhase.matching;
    _resetMessages();
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

  Future<void> setVolunteerAvailable(bool available) async {
    role = DemoRole.volunteer;
    volunteerAvailable = available;
    _resetSessionUi(keepAvailability: true);
    notifyListeners();

    final token = await _tokenStore.getOrCreateToken(api: _api, role: "volunteer");
    await _api.volunteerStatus(token: token, available: available);

    _pendingPollTimer?.cancel();
    if (available) {
      phase = SessionPhase.matching;
      _pendingPollTimer = Timer.periodic(const Duration(seconds: 2), (_) => pollPendingVolunteerSession());
      await pollPendingVolunteerSession();
    } else {
      phase = SessionPhase.idle;
    }
    notifyListeners();
  }

  Future<void> pollPendingVolunteerSession() async {
    if (!volunteerAvailable || phase == SessionPhase.active) {
      return;
    }
    final token = await _tokenStore.getOrCreateToken(api: _api, role: "volunteer");
    final pending = await _api.volunteerPending(token: token);
    if (pending.isNotEmpty) {
      pendingSessionId = pending.first["session_id"] as String;
      sessionId = pendingSessionId;
      state = sessionStateFromString(pending.first["status"] as String);
      phase = SessionPhase.pendingAccept;
      _pendingPollTimer?.cancel();
      _addSystem("Someone needs to talk right now.");
      notifyListeners();
    }
  }

  Future<void> acceptVolunteerSession() async {
    if (pendingSessionId == null) {
      return;
    }
    final token = await _tokenStore.getOrCreateToken(api: _api, role: "volunteer");
    await _api.volunteerAccept(token: token, sessionId: pendingSessionId!);
    sessionId = pendingSessionId;
    phase = SessionPhase.active;
    state = SessionState.active;
    _subscription?.cancel();
    _subscription = _ws
        .connect(token: token, sessionId: sessionId!, role: "volunteer")
        .listen(_handleEvent, onError: _handleError);
    notifyListeners();
  }

  Future<void> declineVolunteerSession() async {
    if (pendingSessionId == null) {
      return;
    }
    final token = await _tokenStore.getOrCreateToken(api: _api, role: "volunteer");
    await _api.volunteerDecline(token: token, sessionId: pendingSessionId!);
    pendingSessionId = null;
    phase = volunteerAvailable ? SessionPhase.matching : SessionPhase.idle;
    _addSystem("Request declined.");
    if (volunteerAvailable) {
      _pendingPollTimer = Timer.periodic(const Duration(seconds: 2), (_) => pollPendingVolunteerSession());
    }
    notifyListeners();
  }

  void sendMessage(String content) {
    final trimmed = content.trim();
    if (trimmed.isEmpty || phase != SessionPhase.active) {
      return;
    }
    messages.add(ChatMessage(kind: ChatMessageKind.local, text: trimmed, createdAt: DateTime.now(), sender: "You"));
    _ws.sendMessage(trimmed);
    notifyListeners();
  }

  Future<void> leaveSession() async {
    if (sessionId == null) {
      return;
    }
    final tokenRole = role == DemoRole.seeker ? "seeker" : "volunteer";
    final token = await _tokenStore.getOrCreateToken(api: _api, role: tokenRole);
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
          _addSystem("Session connected.");
        } else if (state == SessionState.matching || state == SessionState.pendingAccept) {
          phase = state == SessionState.pendingAccept ? SessionPhase.pendingAccept : SessionPhase.matching;
        } else {
          phase = SessionPhase.ended;
        }
        break;
      case "timer_update":
        remainingSeconds = data["remaining_seconds"] as int?;
        break;
      case "system":
        lastSystemMessage = data["content"] as String?;
        if (lastSystemMessage != null) {
          _addSystem(lastSystemMessage!);
        }
        break;
      case "warning":
        lastWarningMessage = data["message"] as String? ?? data["code"] as String?;
        if (lastWarningMessage != null) {
          messages.add(
            ChatMessage(kind: ChatMessageKind.warning, text: lastWarningMessage!, createdAt: DateTime.now()),
          );
        }
        break;
      case "message":
        messages.add(
          ChatMessage(
            kind: ChatMessageKind.peer,
            text: data["content"] as String? ?? "",
            createdAt: DateTime.now(),
            sender: data["from"] as String?,
          ),
        );
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

  void _addSystem(String text) {
    messages.add(ChatMessage(kind: ChatMessageKind.system, text: text, createdAt: DateTime.now()));
  }

  void _resetMessages() {
    messages.clear();
    lastSystemMessage = null;
    lastWarningMessage = null;
    remainingSeconds = null;
  }

  void _resetSessionUi({bool keepAvailability = false}) {
    _subscription?.cancel();
    _pendingPollTimer?.cancel();
    _ws.close();
    phase = SessionPhase.idle;
    state = null;
    sessionId = null;
    pendingSessionId = null;
    if (!keepAvailability) {
      volunteerAvailable = false;
    }
    _resetMessages();
  }

  @override
  void dispose() {
    _subscription?.cancel();
    _pendingPollTimer?.cancel();
    _ws.close();
    super.dispose();
  }
}
