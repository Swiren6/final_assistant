import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:image/image.dart' as img;
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:flutter/foundation.dart';
import '../models/message_model.dart';
import '../utils/constants.dart'; // 🔧 Ajouté pour AppConstants
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
        color: isMe ? Theme.of(context).primaryColor : Colors.grey[300]!,
      ),
    );
  }

  Widget _buildMessageContent(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (message.type == MessageType.notification)
          _buildNotificationHeader(),
        _buildTextContent(context),
        if (message.graphBase64 != null && message.graphBase64!.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: _buildGraphWidget(context, message.graphBase64!),
          ),
        // 🆕 Affichage PDF amélioré
        if (_shouldShowPdfWidget()) ...[
          const SizedBox(height: 12),
          _buildPdfWidget(context),
        ],
      ],
    );
  }

  // 🆕 Vérification intelligente pour afficher le widget PDF
  bool _shouldShowPdfWidget() {
    // Cas 1: PDF URL directement fournie
    if (message.pdfUrl != null && message.pdfUrl!.isNotEmpty) {
      return true;
    }

    // Cas 2: Lien PDF détecté dans le texte
    if (_extractPdfLinkFromText() != null) {
      return true;
    }

    return false;
  }

  // 🆕 Extraction du lien PDF depuis le texte
  String? _extractPdfLinkFromText() {
    if (message.text.isEmpty) return null;

    // Pattern pour détecter les liens d'attestation/PDF
    final patterns = [
      RegExp(r"<a href='([^']*\.pdf[^']*)'[^>]*>.*?</a>", caseSensitive: false),
      RegExp(r"href='([^']*attestation[^']*\.pdf[^']*)'", caseSensitive: false),
    ];

    for (var pattern in patterns) {
      final match = pattern.firstMatch(message.text);
      if (match != null) {
        String url = match.group(1) ?? match.group(0)!;
        // Nettoyer l'URL
        url = url.replaceAll(RegExp(r'''[<>"'\\s]'''), '');
        return url;
      }
    }

    return null;
  }

  Widget _buildTextContent(BuildContext context) {
    String textToDisplay = message.text;
    String? extractedGraphBase64;

    final graphRegexPatterns = [
      RegExp(r"<img src='(data:image/[^']+)"),
      RegExp(r"📊 Graphique généré: <img[^>]*>"),
      RegExp(r"data:image/[^,\s]+,[A-Za-z0-9+/=]+"),
      RegExp(r"<img[^>]*data:image[^>]*>"),
    ];

    for (var pattern in graphRegexPatterns) {
      final match = pattern.firstMatch(textToDisplay);
      if (match != null && extractedGraphBase64 == null) {
        extractedGraphBase64 = match.group(1) ?? match.group(0);
      }
      textToDisplay = textToDisplay.replaceAll(pattern, '');
    }

    // 🆕 Nettoyer les liens PDF du texte d'affichage
    textToDisplay = _cleanPdfLinksFromText(textToDisplay);

    textToDisplay = textToDisplay.replaceAll(
        RegExp(r"📊\s*\*\*Graphique généré\s*:\*\*"), "");
    textToDisplay =
        textToDisplay.replaceAll(RegExp(r"📊\s*Graphique généré\s*:"), "");

    textToDisplay = textToDisplay.replaceAll(RegExp(r'\n\s*\n\s*\n+'), '\n\n');
    textToDisplay = textToDisplay.trim();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (textToDisplay.isNotEmpty)
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
      ],
    );
  }

  // 🆕 Nettoyer les liens PDF du texte pour éviter la duplication
  String _cleanPdfLinksFromText(String text) {
    final patterns = [
      RegExp(r"<a href='[^']*\.pdf[^']*'[^>]*>.*?</a>", caseSensitive: false),
      RegExp(r"📄 Télécharger l'attestation</a>", caseSensitive: false),
      RegExp(r"✅\s*Attestation générée pour [^<\n]*", caseSensitive: false),
    ];

    for (var pattern in patterns) {
      text = text.replaceAll(pattern, '');
    }

    return text;
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
                Container(
                  width: double.infinity,
                  padding:
                      const EdgeInsets.symmetric(vertical: 8, horizontal: 12),
                  decoration: BoxDecoration(
                    color: Colors.grey[50],
                    borderRadius: const BorderRadius.vertical(
                      top: Radius.circular(8),
                    ),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.bar_chart,
                          size: 18, color: Theme.of(context).primaryColor),
                      const SizedBox(width: 8),
                      Text(
                        '📊 Graphique généré',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              fontWeight: FontWeight.bold,
                              color: Theme.of(context).primaryColor,
                            ),
                      ),
                      const Spacer(),
                      IconButton(
                        icon: Icon(Icons.fullscreen,
                            size: 16, color: Colors.grey[600]),
                        onPressed: () =>
                            _showFullscreenGraph(context, snapshot.data!),
                        tooltip: 'Voir en plein écran',
                        constraints: const BoxConstraints(
                          minWidth: 32,
                          minHeight: 32,
                        ),
                        padding: EdgeInsets.zero,
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: ClipRRect(
                    borderRadius: const BorderRadius.vertical(
                      bottom: Radius.circular(8),
                    ),
                    child: InteractiveViewer(
                      panEnabled: true,
                      scaleEnabled: true,
                      boundaryMargin: const EdgeInsets.all(20),
                      minScale: 0.5,
                      maxScale: 4.0,
                      child: Center(
                        child: Image.memory(
                          snapshot.data!,
                          fit: BoxFit.contain,
                          filterQuality: FilterQuality.high,
                          errorBuilder: (ctx, error, stack) {
                            debugPrint('Erreur affichage image: $error');
                            return _buildErrorWidget(
                                'Impossible d\'afficher le graphique');
                          },
                        ),
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

  void _showFullscreenGraph(BuildContext context, Uint8List imageData) {
    showDialog(
      context: context,
      barrierDismissible: true,
      builder: (BuildContext context) {
        return Dialog(
          backgroundColor: Colors.black,
          insetPadding: const EdgeInsets.all(10),
          child: Stack(
            children: [
              Center(
                child: InteractiveViewer(
                  panEnabled: true,
                  scaleEnabled: true,
                  minScale: 0.3,
                  maxScale: 5.0,
                  child: Image.memory(
                    imageData,
                    fit: BoxFit.contain,
                    filterQuality: FilterQuality.high,
                  ),
                ),
              ),
              Positioned(
                top: 10,
                right: 10,
                child: IconButton(
                  icon: const Icon(Icons.close, color: Colors.white, size: 28),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ),
              Positioned(
                bottom: 20,
                left: 20,
                right: 20,
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
                  decoration: BoxDecoration(
                    color: Colors.black54,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    'Pincer pour zoomer • Faire glisser pour naviguer • Toucher pour fermer',
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.9),
                      fontSize: 12,
                    ),
                    textAlign: TextAlign.center,
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  // 🔧 Widget PDF corrigé
  Widget _buildPdfWidget(BuildContext context) {
    // Déterminer l'URL du PDF
    String? pdfUrl = message.pdfUrl ?? _extractPdfLinkFromText();
    String pdfType = message.pdfType ?? 'PDF';

    if (pdfUrl == null) {
      return _buildErrorWidget('URL PDF introuvable');
    }

    // Nettoyer l'URL si nécessaire
    pdfUrl = _cleanPdfUrl(pdfUrl);

    // 🔧 Correction : Convertir correctement l'URL PDF en URL d'image
    String imageUrl = _convertPdfUrlToImageUrl(pdfUrl);

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.red[50],
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.red[200]!),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // En-tête du PDF
          Row(
            children: [
              Icon(Icons.picture_as_pdf, color: Colors.red[700], size: 20),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  '📄 Document $pdfType généré',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: Colors.red[700],
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),

          // Aperçu de l'image du document avec gestion du tap pour agrandir
          GestureDetector(
            onTap: () => _showFullscreenDocument(context, imageUrl),
            child: Container(
              width: double.infinity,
              constraints: const BoxConstraints(
                maxHeight: 300,
                minHeight: 150,
              ),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.grey[300]!),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.1),
                    blurRadius: 4,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Stack(
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: Image.network(
                      imageUrl,
                      width: double.infinity,
                      fit: BoxFit.contain,
                      loadingBuilder: (context, child, loadingProgress) {
                        if (loadingProgress == null) return child;
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
                                'Chargement du document...',
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            ],
                          ),
                        );
                      },
                      errorBuilder: (context, error, stackTrace) {
                        debugPrint('⚠️ Erreur chargement image PDF: $error');
                        debugPrint('🔗 URL tentée: $imageUrl');

                        return Container(
                          height: 200,
                          alignment: Alignment.center,
                          decoration: BoxDecoration(
                            color: Colors.grey[100],
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(
                                Icons.picture_as_pdf,
                                size: 48,
                                color: Colors.red[300],
                              ),
                              const SizedBox(height: 8),
                              Text(
                                'Aperçu non disponible',
                                style: TextStyle(
                                  color: Colors.grey[600],
                                  fontSize: 14,
                                ),
                              ),
                              Text(
                                'Utilisez le bouton télécharger',
                                style: TextStyle(
                                  color: Colors.grey[500],
                                  fontSize: 12,
                                ),
                              ),
                              if (kDebugMode) ...[
                                const SizedBox(height: 8),
                                Container(
                                  padding: const EdgeInsets.all(8),
                                  decoration: BoxDecoration(
                                    color: Colors.orange[100],
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                  child: SelectableText(
                                    'Debug: Erreur $error\nURL: $imageUrl',
                                    style: const TextStyle(fontSize: 10),
                                  ),
                                ),
                              ],
                            ],
                          ),
                        );
                      },
                    ),
                  ),
                  // Indicateur de zoom
                  Positioned(
                    top: 8,
                    right: 8,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.black54,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.zoom_in, color: Colors.white, size: 14),
                          const SizedBox(width: 4),
                          Text(
                            'Toucher pour agrandir',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 10,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 12),

          // Bouton de téléchargement uniquement
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: () => _downloadPdf(context, pdfUrl!),
              icon: const Icon(Icons.download, size: 18),
              label: const Text('Télécharger le document'),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.red[600],
                foregroundColor: Colors.white,
                padding:
                    const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
            ),
          ),

          // URL de débogage (en mode debug seulement)
          if (kDebugMode) ...[
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.grey[100],
                borderRadius: BorderRadius.circular(4),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SelectableText(
                    'Debug PDF URL: $pdfUrl',
                    style:
                        const TextStyle(fontSize: 10, fontFamily: 'monospace'),
                  ),
                  SelectableText(
                    'Debug Image URL: $imageUrl',
                    style:
                        const TextStyle(fontSize: 10, fontFamily: 'monospace'),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  // 🔧 Conversion corrigée de l'URL PDF vers URL image
  String _convertPdfUrlToImageUrl(String pdfUrl) {
    debugPrint('🔄 Conversion PDF -> Image: $pdfUrl');

    // Si l'URL pointe vers /static/attestations/file.pdf
    if (pdfUrl.contains('/static/attestations/')) {
      // Remplacer par /static/images/ et changer l'extension
      String imageUrl = pdfUrl
          .replaceAll('/static/attestations/', '/static/images/')
          .replaceAll('.pdf', '.png');

      debugPrint('🖼️ URL image générée: $imageUrl');
      return imageUrl;
    }

    // Si c'est déjà un chemin image, le retourner tel quel
    if (pdfUrl.contains('/static/images/')) {
      return pdfUrl;
    }

    // Fallback: essayer de construire l'URL image
    if (pdfUrl.endsWith('.pdf')) {
      String filename = pdfUrl.split('/').last;
      String imageFilename = filename.replaceAll('.pdf', '.png');
      String baseUrl = AppConstants.apiBaseUrl;
      String imageUrl = '$baseUrl/static/images/$imageFilename';

      debugPrint('🔧 Fallback URL image: $imageUrl');
      return imageUrl;
    }

    // Dernier recours
    return pdfUrl;
  }

  // 🆕 Nettoyage de l'URL PDF
  String _cleanPdfUrl(String url) {
    // Supprimer les caractères indésirables
    url = url.replaceAll(RegExp(r'''[<>"'\s]'''), '');

    // Si l'URL est relative, construire l'URL complète
    if (url.startsWith('/')) {
      // Utiliser la constante de base URL de votre app
      url = '${AppConstants.apiBaseUrl}$url';
    }

    return url;
  }

  // 🆕 Téléchargement PDF amélioré
  Future<void> _downloadPdf(BuildContext context, String pdfUrl) async {
    try {
      debugPrint('🔗 Tentative téléchargement PDF: $pdfUrl');

      final Uri url = Uri.parse(pdfUrl);

      // Vérifier si l'URL est valide
      if (!url.hasScheme || (!url.scheme.startsWith('http'))) {
        throw Exception('URL invalide: $pdfUrl');
      }

      if (await canLaunchUrl(url)) {
        final launched = await launchUrl(
          url,
          mode: LaunchMode.externalApplication,
        );

        if (launched) {
          _showSnackBar(context, '📱 Ouverture du téléchargement...');
        } else {
          throw Exception('Impossible de lancer l\'URL');
        }
      } else {
        throw Exception('URL non supportée');
      }
    } catch (e) {
      debugPrint('⚠️ Erreur téléchargement PDF: $e');
      _showSnackBar(context, 'Erreur téléchargement: ${e.toString()}');
    }
  }

  // 🆕 Affichage plein écran de l'image du document
  void _showFullscreenDocument(BuildContext context, String imageUrl) {
    showDialog(
      context: context,
      barrierDismissible: true,
      builder: (BuildContext context) {
        return Dialog(
          backgroundColor: Colors.black,
          insetPadding: const EdgeInsets.all(10),
          child: Stack(
            children: [
              Center(
                child: InteractiveViewer(
                  panEnabled: true,
                  scaleEnabled: true,
                  minScale: 0.3,
                  maxScale: 5.0,
                  child: Image.network(
                    imageUrl,
                    fit: BoxFit.contain,
                    filterQuality: FilterQuality.high,
                    loadingBuilder: (context, child, loadingProgress) {
                      if (loadingProgress == null) return child;
                      return Container(
                        width: 200,
                        height: 200,
                        alignment: Alignment.center,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor:
                              AlwaysStoppedAnimation<Color>(Colors.white),
                        ),
                      );
                    },
                    errorBuilder: (context, error, stackTrace) {
                      return Container(
                        width: 200,
                        height: 200,
                        alignment: Alignment.center,
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(
                              Icons.error_outline,
                              size: 48,
                              color: Colors.white70,
                            ),
                            const SizedBox(height: 8),
                            Text(
                              'Impossible de charger\nl\'aperçu du document',
                              style: TextStyle(
                                color: Colors.white70,
                                fontSize: 14,
                              ),
                              textAlign: TextAlign.center,
                            ),
                          ],
                        ),
                      );
                    },
                  ),
                ),
              ),
              Positioned(
                top: 10,
                right: 10,
                child: IconButton(
                  icon: const Icon(Icons.close, color: Colors.white, size: 28),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ),
              Positioned(
                bottom: 20,
                left: 20,
                right: 20,
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
                  decoration: BoxDecoration(
                    color: Colors.black54,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    'Pincer pour zoomer • Faire glisser pour naviguer • Toucher pour fermer',
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.9),
                      fontSize: 12,
                    ),
                    textAlign: TextAlign.center,
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  // Méthode _showSnackBar
  void _showSnackBar(BuildContext context, String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        duration: const Duration(seconds: 3),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }
}