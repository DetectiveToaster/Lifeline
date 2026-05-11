enum ChatMessageKind { local, peer, system, warning }

class ChatMessage {
  const ChatMessage({
    required this.kind,
    required this.text,
    required this.createdAt,
    this.sender,
  });

  final ChatMessageKind kind;
  final String text;
  final DateTime createdAt;
  final String? sender;
}
