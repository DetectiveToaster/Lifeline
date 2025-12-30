import "dart:convert";

import "package:web_socket_channel/web_socket_channel.dart";

import "../config/app_config.dart";
import "../models/ws_event.dart";

class WsClient {
  WebSocketChannel? _channel;

  Stream<WsEvent> connect({
    required String token,
    required String sessionId,
    required String role,
    String? locale,
  }) {
    final uri = Uri.parse(
      "${AppConfig.baseWsUrl}/v1/ws?token=$token&session_id=$sessionId&role=$role${locale != null ? "&locale=$locale" : ""}",
    );
    _channel = WebSocketChannel.connect(uri);
    return _channel!.stream.map((event) {
      final data = jsonDecode(event as String) as Map<String, dynamic>;
      return WsEvent.fromJson(data);
    });
  }

  void sendMessage(String content) {
    _channel?.sink.add(jsonEncode({"type": "message", "content": content}));
  }

  void sendLeave() {
    _channel?.sink.add(jsonEncode({"type": "leave"}));
  }

  void close() {
    _channel?.sink.close();
  }
}
