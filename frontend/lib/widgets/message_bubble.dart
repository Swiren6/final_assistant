import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:image/image.dart' as img;
import '../models/message_model.dart';
import 'dart:convert';
import 'dart:typed_data';

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
            maxWidth: MediaQuery.of(context).size.width * 0.85,
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
    if (message.type == MessageType.notification) {
      return const EdgeInsets.symmetric(vertical: 4, horizontal: 8);
    }
    return const EdgeInsets.symmetric(vertical: 8, horizontal: 12);
  }

  BoxDecoration _getBubbleDecoration(BuildContext context) {
    if (message.type == MessageType.notification) {
      return BoxDecoration(
        color: Colors.blue[50],
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.blue[100]!),
      );
    }

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

        // Traiter le texte pour extraire le graphique intégré
        _buildTextContent(context),

        // Afficher le graphique séparé s'il existe
        if (message.graphBase64 != null && message.graphBase64!.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: _buildGraphWidget(context, message.graphBase64!),
          ),

        // Afficher la requête SQL pour debug (seulement pour les admins)
        if (message.sqlQuery != null && 
            message.sqlQuery!.isNotEmpty && 
            message.type != MessageType.notification)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.grey[100],
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.grey[300]!),
              ),
              child: Row(
                children: [
                  Icon(Icons.code, size: 16, color: Colors.grey[600]),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'SQL: ${message.sqlQuery}',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        fontFamily: 'monospace',
                        color: Colors.grey[700],
                        fontSize: 11,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildTextContent(BuildContext context) {
    String textToDisplay = message.text;
    String? extractedGraphBase64;

    // Extraire le graphique du texte si présent
    final graphRegex = RegExp(r"<img src='(data:image/[^']+)");
    final match = graphRegex.firstMatch(textToDisplay);
    
    if (match != null) {
      extractedGraphBase64 = match.group(1);
      // Nettoyer le texte en supprimant la balise img
      textToDisplay = textToDisplay.replaceAll(
        RegExp(r"📊 Graphique généré: <img[^>]*>"), 
        "\n📊 **Graphique généré :**"
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Texte principal
        _isMarkdown(textToDisplay)
            ? MarkdownBody(
                data: textToDisplay,
                styleSheet: MarkdownStyleSheet(
                  p: Theme.of(context).textTheme.bodyMedium,
                  strong: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
              )
            : Text(textToDisplay, style: _getTextStyle(context)),

        // Graphique extrait du texte
        if (extractedGraphBase64 != null)
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: _buildGraphWidget(context, extractedGraphBase64),
          ),
      ],
    );
  }

  bool _isMarkdown(String text) {
    return text.contains('**') || 
           text.contains('```') || 
           text.contains('|') ||
           text.contains('###') ||
           text.contains('##') ||
           text.contains('#');
  }

  Widget _buildNotificationHeader() {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
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
      ),
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
      
      if (cleanedBase64.isEmpty) {
        return _buildErrorWidget('Données graphique vides');
      }

      return FutureBuilder<Uint8List>(
        future: _decodeBase64Image(cleanedBase64),
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            debugPrint('Erreur décodage graphique: ${snapshot.error}');
            return _buildErrorWidget('Erreur de décodage du graphique');
          }

          if (!snapshot.hasData) {
            return Container(
              height: 200,
              alignment: Alignment.center,
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  CircularProgressIndicator(
                    strokeWidth: 2,
                    valueColor: AlwaysStoppedAnimation<Color>(
                      Theme.of(context).primaryColor,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Chargement du graphique...',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            );
          }

          return Container(
            margin: const EdgeInsets.symmetric(vertical: 8),
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.white,
              border: Border.all(color: Colors.grey.shade300),
              borderRadius: BorderRadius.circular(12),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.1),
                  blurRadius: 4,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            constraints: BoxConstraints(
              maxHeight: 400,
              maxWidth: MediaQuery.of(context).size.width * 0.8,
            ),
            child: Column(
              children: [
                // En-tête du graphique
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.grey[50],
                    borderRadius: const BorderRadius.vertical(
                      top: Radius.circular(8),
                    ),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        Icons.bar_chart,
                        size: 16,
                        color: Theme.of(context).primaryColor,
                      ),
                      const SizedBox(width: 8),
                      Text(
                        'Graphique',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          fontWeight: FontWeight.bold,
                          color: Theme.of(context).primaryColor,
                        ),
                      ),
                    ],
                  ),
                ),
                
                // Graphique interactif
                Expanded(
                  child: InteractiveViewer(
                    panEnabled: true,
                    scaleEnabled: true,
                    boundaryMargin: const EdgeInsets.all(20),
                    minScale: 0.5,
                    maxScale: 3.0,
                    child: Center(
                      child: Image.memory(
                        snapshot.data!,
                        fit: BoxFit.contain,
                        filterQuality: FilterQuality.high,
                        errorBuilder: (ctx, error, stack) {
                          debugPrint('Erreur affichage image: $error');
                          return _buildErrorWidget('Impossible d\'afficher le graphique');
                        },
                      ),
                    ),
                  ),
                ),
              ],
            ),
          );
        },
      );
    } catch (e) {
      debugPrint('Erreur construction graphique: $e');
      return _buildErrorWidget('Format de graphique non supporté');
    }
  }

  Future<Uint8List> _decodeBase64Image(String base64String) async {
    try {
      final bytes = base64.decode(base64String);
      
      // Vérifier que c'est une image valide
      final image = img.decodeImage(bytes);
      if (image == null) {
        throw Exception('Format d\'image invalide');
      }
      
      return bytes;
    } catch (e) {
      debugPrint('Erreur décodage base64: $e');
      rethrow;
    }
  }

  String _cleanBase64String(String base64Image) {
    if (base64Image.isEmpty) return '';
    
    // Retirer le préfixe data:image si présent
    if (base64Image.contains(',')) {
      return base64Image.split(',').last;
    }
    
    return base64Image;
  }

  Widget _buildErrorWidget(String message) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.red[50],
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.red[200]!),
      ),
      child: Row(
        children: [
          Icon(Icons.error_outline, size: 20, color: Colors.red[700]),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              message,
              style: TextStyle(
                color: Colors.red[700],
                fontSize: 14,
              ),
            ),
          ),
        ],
      ),
    );
  }
}