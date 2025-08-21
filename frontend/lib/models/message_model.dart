import 'package:flutter/foundation.dart';

enum MessageType { user, assistant, error, system, notification }

class Message {
  final String text;
  final MessageType type;
  final bool isMe;
  final String? sqlQuery;
  final String? graphBase64;
  final DateTime timestamp;
  final Map<String, dynamic>? metadata;
  final String? pdfUrl; 
  final String? pdfType;
  final String? imageUrl;


  Message({
    required this.text,
    required this.type,
    this.isMe = false,
    this.sqlQuery,
    this.graphBase64,
    this.metadata,
    this.pdfUrl,    
    this.pdfType,
    this.imageUrl,
    DateTime? timestamp,
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

  // Dans message_model.dart
  factory Message.system({required String text}) {
    return Message(
      text: text,
      type: MessageType.system,
      isMe: false,
      timestamp: DateTime.now(),
    );
  }
  factory Message.assistant({
    required String text,
    String? sqlQuery,
    String? graphBase64,
    Map<String, dynamic>? metadata,
  }) {
    // Nettoyer le texte si nécessaire
    String cleanText = text;
    String? finalGraphBase64 = graphBase64;

    // Si le graphique n'est pas fourni séparément, essayer de l'extraire du texte
    if (finalGraphBase64 == null || finalGraphBase64.isEmpty) {
      final graphRegex = RegExp(r'data:image\/[a-zA-Z]+;base64,[A-Za-z0-9+/=]+');
      final match = graphRegex.firstMatch(cleanText);
      if (match != null) {
        finalGraphBase64 = match.group(0);
        debugPrint('📊 Graphique extrait du texte: ${finalGraphBase64?.substring(0, 50)}...');
      }
    }

    return Message(
      text: cleanText,
      type: MessageType.assistant,
      isMe: false,
      sqlQuery: sqlQuery?.isNotEmpty == true ? sqlQuery : null,
      graphBase64: finalGraphBase64?.isNotEmpty == true ? finalGraphBase64 : null,
      metadata: metadata,
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
  Message.assistantWithPdf({
    required String text,
    String? sqlQuery,
    String? graphBase64,
    String? pdfUrl,
    String? pdfType,
  }) : this(
          text: text,
          isMe: false,
          type: MessageType.assistant,
          sqlQuery: sqlQuery,
          graphBase64: graphBase64,
          pdfUrl: pdfUrl,
          pdfType: pdfType,
          
        );
  // Méthode pour créer une copie avec des modifications
  Message copyWith({
    String? text,
    MessageType? type,
    bool? isMe,
    String? sqlQuery,
    String? graphBase64,
    Map<String, dynamic>? metadata,
    DateTime? timestamp,
  }) {
    return Message(
      text: text ?? this.text,
      type: type ?? this.type,
      isMe: isMe ?? this.isMe,
      sqlQuery: sqlQuery ?? this.sqlQuery,
      graphBase64: graphBase64 ?? this.graphBase64,
      metadata: metadata ?? this.metadata,
      timestamp: timestamp ?? this.timestamp,
    );
  }

  // Vérifier si le message contient un graphique
  bool get hasGraph {
    return graphBase64 != null && 
           graphBase64!.isNotEmpty && 
           (graphBase64!.startsWith('data:image/') || 
            _isValidBase64(graphBase64!));
  }

  // Vérifier si le message contient du SQL
  bool get hasSqlQuery {
    return sqlQuery != null && sqlQuery!.isNotEmpty;
  }

  // Vérifier si c'est un message système de chargement
  bool get isTyping {
    return type == MessageType.system && text == 'typing...';
  }

  // Vérifier si c'est un message d'erreur
  bool get isError {
    return type == MessageType.error;
  }

  // Vérifier si c'est un message de notification
  bool get isNotification {
    return type == MessageType.notification;
  }

  // Méthode utilitaire pour vérifier si une chaîne est du Base64 valide
  bool _isValidBase64(String str) {
    if (str.isEmpty) return false;
    
    // Nettoyer la chaîne (retirer le préfixe data:image si présent)
    String cleaned = str;
    if (str.contains(',')) {
      cleaned = str.split(',').last;
    }
    
    // Vérifier le format Base64
    final base64Regex = RegExp(r'^[A-Za-z0-9+/]*={0,2}$');
    return base64Regex.hasMatch(cleaned) && cleaned.length % 4 == 0;
  }

  @override
  String toString() {
    return 'Message(type: $type, text: ${text.length > 50 ? "${text.substring(0, 50)}..." : text}, hasGraph: $hasGraph, hasSql: $hasSqlQuery)';
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is Message &&
        other.text == text &&
        other.type == type &&
        other.isMe == isMe &&
        other.sqlQuery == sqlQuery &&
        other.graphBase64 == graphBase64 &&
        other.timestamp == timestamp;
  }

  @override
  int get hashCode {
    return Object.hash(text, type, isMe, sqlQuery, graphBase64, timestamp);
  }
}