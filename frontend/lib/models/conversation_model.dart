class ConversationModel {
  final int id;
  String title;
  final DateTime createdAt;
  final DateTime updatedAt;
  final int messageCount;
  final bool isArchived;

  ConversationModel({
    required this.id,
    required this.title,
    required this.createdAt,
    required this.updatedAt,
    required this.messageCount,
    this.isArchived = false,
  });

  factory ConversationModel.fromJson(Map<String, dynamic> json) {
    return ConversationModel(
      id: json['id'] as int,
      title: json['title'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
      messageCount: json['message_count'] as int? ?? 0,
      isArchived: json['is_archived'] as bool? ?? false,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
      'message_count': messageCount,
      'is_archived': isArchived,
    };
  }
}

class MessageHistoryModel {
  final String type; // 'user', 'assistant', 'system'
  final String content;
  final DateTime timestamp;
  final String? sqlQuery;
  final String? graphData;

  MessageHistoryModel({
    required this.type,
    required this.content,
    required this.timestamp,
    this.sqlQuery,
    this.graphData,
  });

  factory MessageHistoryModel.fromJson(Map<String, dynamic> json) {
    return MessageHistoryModel(
      type: json['type'] as String,
      content: json['content'] as String,
      timestamp: DateTime.parse(json['timestamp'] as String),
      sqlQuery: json['sql_query'] as String?,
      graphData: json['graph_data'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'type': type,
      'content': content,
      'timestamp': timestamp.toIso8601String(),
      if (sqlQuery != null) 'sql_query': sqlQuery,
      if (graphData != null) 'graph_data': graphData,
    };
  }
}