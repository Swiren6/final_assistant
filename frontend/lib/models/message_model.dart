import 'package:flutter/foundation.dart';

enum MessageType { user, assistant, error, system, notification }

class Message {
  final String text;
  final MessageType type;
  final bool isMe;
  final String? sqlQuery;
  final String? graphBase64;
  final DateTime timestamp;
  final bool isTyping;

  // Retirer `const` ici
  Message({
    required this.text,
    required this.type,
    
    this.isMe = false,
    this.sqlQuery,
    this.graphBase64,
    DateTime? timestamp,
    this.isTyping = false,
  }) : timestamp = timestamp ?? DateTime.now();

  factory Message.notification({required String text}) {
    return Message(
      text: text,
      type: MessageType.notification,
      isMe: false,
    );
  }

  factory Message.user({required String text}) {
    return Message(
      text: text,
      type: MessageType.user,
      isMe: true,
    );
  }

  factory Message.assistant({
    required String text,
    String? sqlQuery,
    String? graphBase64,
  }) {
    return Message(
      text: text,
      type: MessageType.assistant,
      isMe: false,
      sqlQuery: sqlQuery,
      graphBase64: graphBase64,
    );
  }

  factory Message.typing() {
    return Message(
      text: 'typing...',
      type: MessageType.system,
      isMe: false,
    );
  }

  factory Message.error({required String text}) {
    return Message(
      text: text,
      type: MessageType.error,
      isMe: false,
    );
  }
}