import 'package:flutter/foundation.dart';

enum MessageType { user, assistant, error, system }

class Message {
  final String id;
  final String text;
  final MessageType type;
  final DateTime timestamp;
  final bool isTyping;
  final String? sqlQuery;
  final int? tokensUsed;
  final double? cost;

  Message({
    String? id,
    required this.text,
    required this.type,
    DateTime? timestamp,
    this.isTyping = false,
    this.sqlQuery,
    this.tokensUsed,
    this.cost,
  }) : id = id ?? DateTime.now().millisecondsSinceEpoch.toString(),
       timestamp = timestamp ?? DateTime.now();

  // Constructeurs de convenance
  Message.user({
    required String text,
    String? id,
    DateTime? timestamp,
  }) : this(
         id: id,
         text: text,
         type: MessageType.user,
         timestamp: timestamp,
       );

  Message.assistant({
    required String text,
    String? id,
    DateTime? timestamp,
    String? sqlQuery,
    int? tokensUsed,
    double? cost,
  }) : this(
         id: id,
         text: text,
         type: MessageType.assistant,
         timestamp: timestamp,
         sqlQuery: sqlQuery,
         tokensUsed: tokensUsed,
         cost: cost,
       );

  Message.typing() : this(
         text: '',
         type: MessageType.assistant,
         isTyping: true,
       );

  Message.error({
    required String text,
    String? id,
    DateTime? timestamp,
  }) : this(
         id: id,
         text: text,
         type: MessageType.error,
         timestamp: timestamp,
       );

  factory Message.fromJson(Map<String, dynamic> json) {
    return Message(
      id: json['id']?.toString() ?? DateTime.now().millisecondsSinceEpoch.toString(),
      text: json['text'] ?? '',
      type: MessageType.values.firstWhere(
        (e) => e.toString() == 'MessageType.${json['type']}',
        orElse: () => MessageType.system,
      ),
      timestamp: DateTime.parse(json['timestamp'] ?? DateTime.now().toIso8601String()),
      isTyping: json['isTyping'] ?? false,
      sqlQuery: json['sqlQuery'],
      tokensUsed: json['tokensUsed'],
      cost: json['cost']?.toDouble(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'text': text,
      'type': type.toString().split('.').last,
      'timestamp': timestamp.toIso8601String(),
      'isTyping': isTyping,
      'sqlQuery': sqlQuery,
      'tokensUsed': tokensUsed,
      'cost': cost,
    };
  }

  Message copyWith({
    String? id,
    String? text,
    MessageType? type,
    DateTime? timestamp,
    bool? isTyping,
    String? sqlQuery,
    int? tokensUsed,
    double? cost,
  }) {
    return Message(
      id: id ?? this.id,
      text: text ?? this.text,
      type: type ?? this.type,
      timestamp: timestamp ?? this.timestamp,
      isTyping: isTyping ?? this.isTyping,
      sqlQuery: sqlQuery ?? this.sqlQuery,
      tokensUsed: tokensUsed ?? this.tokensUsed,
      cost: cost ?? this.cost,
    );
  }

  bool get isMe => type == MessageType.user;
  bool get isAssistant => type == MessageType.assistant;
  bool get isError => type == MessageType.error;

  @override
  String toString() {
    return 'Message{id: $id, text: $text, type: $type, timestamp: $timestamp}';
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is Message && other.id == id;
  }

  @override
  int get hashCode => id.hashCode;
}