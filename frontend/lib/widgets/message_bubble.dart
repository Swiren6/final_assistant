import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:image/image.dart' as img;
import '../models/message_model.dart';
import 'dart:convert';

class MessageBubble extends StatelessWidget {
  final Message message;
  final bool isMe;

  const MessageBubble({
    super.key,
    required this.message,
    required this.isMe,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: _getBubblePadding(),
      child: Align(
        alignment: isMe ? Alignment.centerRight : Alignment.centerLeft,
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.8,
          ),
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: _getBubbleDecoration(context),
            child: _buildMessageContent(context),
          ),
        ),
      ),
    );
  }

  EdgeInsets _getBubblePadding() {
    // Moins d'espace pour les notifications
    if (message.type == MessageType.notification) {
      return const EdgeInsets.symmetric(vertical: 4, horizontal: 8);
    }
    return const EdgeInsets.symmetric(vertical: 8, horizontal: 12);
  }

  BoxDecoration _getBubbleDecoration(BuildContext context) {
    // Style différent pour les notifications
    if (message.type == MessageType.notification) {
      return BoxDecoration(
        color: Colors.blue[50],
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.blue[100]!),
      );
    }

    // Style normal pour les autres messages
    return BoxDecoration(
      color: isMe 
          ? Theme.of(context).primaryColor.withOpacity(0.1)
          : Colors.grey[100],
      borderRadius: BorderRadius.circular(16),
      border: Border.all(
        color: isMe 
            ? Theme.of(context).primaryColor
            : Colors.grey[300]!,
      ),
    );
  }

  Widget _buildMessageContent(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (message.type == MessageType.notification)
          _buildNotificationHeader(),

        // Affiche markdown ou texte simple selon contenu
        _isMarkdownOrImage(message.text)
            ? MarkdownBody(data: message.text)
            : Text(message.text, style: _getTextStyle(context)),

        if (message.graphBase64 != null && message.graphBase64!.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: _buildGraphWidget(context, message.graphBase64!),
          ),

        if (message.sqlQuery != null && message.type != MessageType.notification)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(
              'Requête SQL: ${message.sqlQuery}',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    fontStyle: FontStyle.italic,
                    color: Colors.grey,
                  ),
            ),
          ),
      ],
    );
  }

  bool _isMarkdownOrImage(String text) {
    final lower = text.toLowerCase();
    return lower.contains('data:image') || text.contains('```') || text.contains('|');
  }

  Widget _buildNotificationHeader() {
    return Row(
      children: [
        const Icon(Icons.notifications_active, size: 16, color: Colors.blue),
        const SizedBox(width: 8),
        Text(
          'Notification',
          style: TextStyle(
            fontWeight: FontWeight.bold,
            color: Colors.blue[700],
          ),
        ),
      ],
    );
  }

  TextStyle? _getTextStyle(BuildContext context) {
    if (message.type == MessageType.notification) {
      return Theme.of(context).textTheme.bodyMedium?.copyWith(
            color: Colors.blue[900],
          );
    }
    return Theme.of(context).textTheme.bodyMedium;
  }

  Widget _buildGraphWidget(BuildContext context, String base64Image) {
    try {
      final cleanedBase64 = _cleanBase64String(base64Image);
      final imageBytes = base64.decode(cleanedBase64);
      final image = img.decodeImage(imageBytes);
      
      if (image == null) return _buildErrorWidget('Image invalide');

      return Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          border: Border.all(color: Colors.grey.shade300),
          borderRadius: BorderRadius.circular(8),
          color: Colors.white,
        ),
        constraints: BoxConstraints(
          maxHeight: 300,
          maxWidth: MediaQuery.of(context).size.width * 0.7,
        ),
        child: InteractiveViewer(
          panEnabled: true,
          boundaryMargin: const EdgeInsets.all(20),
          minScale: 0.1,
          maxScale: 4.0,
          child: Image.memory(
            imageBytes,
            fit: BoxFit.contain,
            filterQuality: FilterQuality.high,
            errorBuilder: (ctx, error, stack) => _buildErrorWidget('Erreur d\'affichage'),
          ),
        ),
      );
    } catch (e) {
      debugPrint('Erreur d\'affichage du graphique: $e');
      return _buildErrorWidget('Format d\'image non supporté');
    }
  }

  String _cleanBase64String(String base64Image) {
    return base64Image.contains(',') ? base64Image.split(',').last : base64Image;
  }

  Widget _buildErrorWidget(String message) {
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: Colors.red[50],
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          const Icon(Icons.error_outline, size: 16, color: Colors.red),
          const SizedBox(width: 8),
          Text(message, style: const TextStyle(color: Colors.red)),
        ],
      ),
    );
  }
}