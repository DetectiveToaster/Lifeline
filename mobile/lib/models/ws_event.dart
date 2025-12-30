class WsEvent {
  WsEvent({required this.type, this.data});

  final String type;
  final Map<String, dynamic>? data;

  factory WsEvent.fromJson(Map<String, dynamic> json) {
    return WsEvent(
      type: json["type"] as String? ?? "unknown",
      data: json,
    );
  }
}
