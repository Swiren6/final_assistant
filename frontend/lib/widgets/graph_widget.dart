import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';

class GraphDisplay extends StatelessWidget {
  final String base64String;

  const GraphDisplay({super.key, required this.base64String});

  @override
  Widget build(BuildContext context) {
    String cleanedBase64 = base64String;
    
    // Nettoyage de la chaîne Base64
    if (base64String.contains(',')) {
      cleanedBase64 = base64String.split(',').last;
    }

    return FutureBuilder<Uint8List>(
      future: _decodeImage(cleanedBase64),
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return _buildErrorWidget('Erreur de décodage: ${snapshot.error}');
        }

        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }

        return Container(
          margin: const EdgeInsets.symmetric(vertical: 8),
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            border: Border.all(color: Colors.grey.shade300),
            borderRadius: BorderRadius.circular(8),
          ),
          child: InteractiveViewer(
            panEnabled: true,
            scaleEnabled: true,
            child: Image.memory(
              snapshot.data!,
              fit: BoxFit.contain,
            ),
          ),
        );
      },
    );
  }

  Future<Uint8List> _decodeImage(String base64) async {
    try {
      return base64Decode(base64);
    } catch (e) {
      debugPrint('Erreur de décodage Base64: $e');
      rethrow;
    }
  }

  Widget _buildErrorWidget(String message) {
    return Container(
      padding: const EdgeInsets.all(8),
      color: Colors.red[50],
      child: Row(
        children: [
          const Icon(Icons.error_outline, color: Colors.red),
          const SizedBox(width: 8),
          Expanded(child: Text(message)),
        ],
      ),
    );
  }
}