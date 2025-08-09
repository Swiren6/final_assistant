import 'dart:convert';
import 'dart:io';
import 'dart:async';
import 'package:http/http.dart' as http;
import '../utils/constants.dart';
import 'package:flutter/foundation.dart';

class ApiException implements Exception {
  final String message;
  final int? statusCode;
  final Map<String, dynamic>? details;

  ApiException(this.message, [this.statusCode, this.details]);

  @override
  String toString() =>
      '$message${statusCode != null ? ' (Code: $statusCode)' : ''}';
}

class ApiService {
  static const String baseUrl = AppConstants.apiBaseUrl;
  static const Duration defaultTimeout = Duration(seconds: 30);
  static const Duration longTimeout = Duration(seconds: 60);

  Map<String, String> _getHeaders(String? token) {
    return {
      'Content-Type': 'application/json; charset=utf-8',
      'Accept': 'application/json',
      if (token != null && token.isNotEmpty) 
        'Authorization': 'Bearer $token',
    };
  }

  // Méthode générique pour gérer les réponses
  Map<String, dynamic> _handleResponse(http.Response response) {
    if (kDebugMode) {
      print('↪️ Réponse ${response.statusCode} | ${response.request?.url}');
      print('📦 Body: ${response.body.length > 500 ? "${response.body.substring(0, 500)}..." : response.body}');
    }

    switch (response.statusCode) {
      case 200:
      case 201:
        try {
          final decoded = jsonDecode(response.body);
          if (kDebugMode) {
            print('✅ Réponse décodée avec succès');
            if (decoded is Map<String, dynamic>) {
              print('🔍 Clés de la réponse: ${decoded.keys.toList()}');
              
              // Log spécial pour les graphiques
              if (decoded.containsKey('response') && 
                  decoded['response'].toString().contains('data:image')) {
                print('🖼️ Graphique détecté dans la réponse');
              }
            }
          }
          return decoded;
        } catch (e) {
          if (kDebugMode) {
            print('❌ Erreur de décodage JSON: $e');
            print('📝 Contenu brut: ${response.body}');
          }
          throw ApiException('Format de réponse invalide', 500, {'raw_response': response.body});
        }
      case 400:
        String errorMsg = 'Requête incorrecte';
        try {
          final errorBody = jsonDecode(response.body);
          if (errorBody['error'] != null) {
            errorMsg = errorBody['error'].toString();
          }
        } catch (_) {}
        throw ApiException(errorMsg, 400);
      case 401:
        throw ApiException('Authentification requise', 401);
      case 403:
        throw ApiException('Accès refusé', 403);
      case 404:
        throw ApiException('Ressource non trouvée', 404);
      case 422:
        String errorMsg = 'Données invalides';
        try {
          final errorBody = jsonDecode(response.body);
          if (errorBody['error'] != null) {
            errorMsg = errorBody['error'].toString();
          }
        } catch (_) {}
        throw ApiException(errorMsg, 422);
      case 500:
        String errorMsg = 'Erreur serveur';
        try {
          final errorBody = jsonDecode(response.body);
          if (errorBody['error'] != null) {
            errorMsg = errorBody['error'].toString();
          }
        } catch (_) {}
        throw ApiException(errorMsg, 500);
      case 503:
        throw ApiException('Service temporairement indisponible', 503);
      default:
        throw ApiException(
          'Erreur inattendue: ${response.statusCode}',
          response.statusCode,
        );
    }
  }

  // Méthode générique GET
  Future<Map<String, dynamic>> get(
    String endpoint, {
    String? token,
    Duration? timeout,
  }) async {
    try {
      final uri = Uri.parse('$baseUrl$endpoint');
      if (kDebugMode) {
        print('🌐 GET $uri');
      }

      final response = await http.get(
        uri,
        headers: _getHeaders(token),
      ).timeout(timeout ?? defaultTimeout);

      return _handleResponse(response);
    } on SocketException {
      throw ApiException('Pas de connexion internet');
    } on TimeoutException {
      throw ApiException('Temps d\'attente dépassé');
    } on http.ClientException catch (e) {
      throw ApiException('Erreur réseau: ${e.message}');
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('Erreur inattendue: ${e.toString()}');
    }
  }

  // Méthode générique POST
  Future<Map<String, dynamic>> post(
    String endpoint,
    Map<String, dynamic> data, {
    String? token,
    Duration? timeout,
  }) async {
    try {
      final uri = Uri.parse('$baseUrl$endpoint');
      final body = jsonEncode(data);
      
      if (kDebugMode) {
        print('🌐 POST $uri');
        print('📤 Body: ${body.length > 200 ? "${body.substring(0, 200)}..." : body}');
      }

      final response = await http.post(
        uri,
        headers: _getHeaders(token),
        body: body,
      ).timeout(timeout ?? defaultTimeout);

      return _handleResponse(response);
    } on SocketException {
      throw ApiException('Pas de connexion internet');
    } on TimeoutException {
      throw ApiException('Temps d\'attente dépassé');
    } on http.ClientException catch (e) {
      throw ApiException('Erreur réseau: ${e.message}');
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('Erreur inattendue: ${e.toString()}');
    }
  }

  /// Envoi d'une question au chat
  Future<Map<String, dynamic>> askQuestion(
    String question,
    String token,
  ) async {
    if (kDebugMode) {
      print('🤖 Envoi de la question: "$question"');
    }

    final response = await post(
      '/ask',
      {'question': question.trim()},
      token: token,
      timeout: longTimeout, // Plus de temps pour les questions complexes
    );

    if (kDebugMode) {
      print('✅ Réponse reçue pour la question');
      
      // Debug spécial pour les graphiques
      if (response['response'] != null) {
        final responseText = response['response'].toString();
        if (responseText.contains('data:image')) {
          print('🖼️ Graphique trouvé dans response["response"]');
          
          // Extraire les informations du graphique
          final graphRegex = RegExp(r"data:image/([^;]+);base64,([A-Za-z0-9+/=]+)");
          final match = graphRegex.firstMatch(responseText);
          if (match != null) {
            print('📊 Type d\'image: ${match.group(1)}');
            print('📏 Taille du base64: ${match.group(2)?.length} caractères');
          }
        }
      }
    }

    return response;
  }

  /// Test de connectivité
  Future<bool> testConnection() async {
    try {
      final response = await get('/health', 
        timeout: const Duration(seconds: 5));
      
      final isHealthy = response['status'] == 'healthy' || response['status'] == 'OK';
      
      if (kDebugMode) {
        print(isHealthy ? '✅ Connexion OK' : '⚠️ Service dégradé');
      }
      
      return isHealthy;
    } catch (e) {
      if (kDebugMode) {
        print('❌ Test de connexion échoué: $e');
      }
      return false;
    }
  }

  /// Connexion utilisateur
  Future<Map<String, dynamic>> login(
    String loginIdentifier,
    String password,
  ) async {
    try {
      if (kDebugMode) {
        print('🔐 Tentative de connexion pour: $loginIdentifier');
      }

      final response = await post(
        '/login',
        {
          'login_identifier': loginIdentifier,
          'password': password,
        },
        timeout: const Duration(seconds: 15),
      );

      if (kDebugMode) {
        print('✅ Connexion réussie');
      }

      return response;
    } on ApiException {
      rethrow;
    } catch (e) {
      throw ApiException('Erreur lors de la connexion: ${e.toString()}');
    }
  }

  /// Récupération des notifications
  Future<List<Map<String, dynamic>>> getNotifications(String token) async {
    try {
      final response = await get('/notifications', token: token);
      
      if (response['notifications'] is List) {
        return List<Map<String, dynamic>>.from(response['notifications']);
      }
      
      return [];
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ Erreur récupération notifications: $e');
      }
      return [];
    }
  }

  /// Statut de l'assistant IA
  Future<Map<String, dynamic>?> getAssistantStatus(String token) async {
    try {
      return await get('/status', token: token);
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ Erreur récupération statut assistant: $e');
      }
      return null;
    }
  }

  /// Réinitialiser l'assistant
  Future<bool> resetAssistant(String token) async {
    try {
      final response = await post('/reinit', {}, token: token);
      return response['success'] == true;
    } catch (e) {
      if (kDebugMode) {
        print('❌ Erreur réinitialisation assistant: $e');
      }
      return false;
    }
  }

  /// Effacer l'historique des conversations
  Future<bool> clearHistory(String token) async {
    try {
      final response = await post('/clear-history', {}, token: token);
      return response['success'] == true;
    } catch (e) {
      if (kDebugMode) {
        print('❌ Erreur effacement historique: $e');
      }
      return false;
    }
  }
}