import 'dart:convert';
import 'dart:io';
import 'dart:async';
import 'package:http/http.dart' as http;
import '../utils/constants.dart';
import 'package:flutter/foundation.dart';

class ApiException implements Exception {
  final String message;
  final int? statusCode;

  ApiException(this.message, [this.statusCode]);

  @override
  String toString() =>
      '$message${statusCode != null ? ' (Code: $statusCode)' : ''}';
}

class ApiService {
  static const String baseUrl = AppConstants.apiBaseUrl;
  static const Duration defaultTimeout = Duration(seconds: 30);

  Map<String, String> _getHeaders(String? token) {
    return {
      'Content-Type': 'application/json; charset=utf-8',
      'Accept': 'application/json',
      if (token != null && token.isNotEmpty) 'Authorization': 'Bearer $token',
    };
  }

  // Méthode générique pour gérer les réponses
  Map<String, dynamic> _handleResponse(http.Response response) {
    final statusCode = response.statusCode;
    if (kDebugMode) {
      print('↪️ Réponse ${response.statusCode} | ${response.request?.url}');
      print('📦 Body: ${response.body}');
    }

    try {
      final data = jsonDecode(utf8.decode(response.bodyBytes));
      
      if (statusCode >= 200 && statusCode < 300) {
        // Formatage spécial pour les réponses de chat
        if (data.containsKey('response') && data.containsKey('sql_query')) {
          return {
            'response': data['response'] ?? data['msg'] ?? 'Réponse reçue',
            'sql_query': data['sql_query'],
            'status': 'success',
          };
        }
        return data;
      } else {
        final message = data['error'] ?? 
                       data['message'] ?? 
                       data['msg'] ?? 
                       'Erreur serveur (code $statusCode)';
        throw ApiException(message, statusCode);
      }
    } on FormatException catch (e) {
      if (kDebugMode) {
        print('❌ Erreur de format JSON: $e');
      }
      throw ApiException('Format de réponse invalide du serveur', statusCode);
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
      final headers = _getHeaders(token);

      if (kDebugMode) {
        print('🌐 GET $uri');
      }

      final response = await http.get(
        uri,
        headers: headers,
      ).timeout(timeout ?? defaultTimeout);

      return _handleResponse(response);
    } on SocketException {
      throw ApiException('Pas de connexion internet. Vérifiez votre réseau.');
    } on TimeoutException {
      throw ApiException('Temps d\'attente dépassé. Le serveur ne répond pas.');
    } on http.ClientException catch (e) {
      throw ApiException('Erreur réseau: ${e.message}');
    } catch (e) {
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
      final headers = _getHeaders(token);
      final body = jsonEncode(data);

      if (kDebugMode) {
        print('🌐 POST $uri');
        print('📤 Body: $body');
      }

      final response = await http.post(
        uri,
        headers: headers,
        body: body,
      ).timeout(timeout ?? defaultTimeout);

      return _handleResponse(response);
    } on SocketException {
      throw ApiException('Pas de connexion internet. Vérifiez votre réseau.');
    } on TimeoutException {
      throw ApiException('Temps d\'attente dépassé. Le serveur ne répond pas.');
    } on http.ClientException catch (e) {
      throw ApiException('Erreur réseau: ${e.message}');
    } catch (e) {
      throw ApiException('Erreur inattendue: ${e.toString()}');
    }
  }

  /// Envoi d'une question au chat
  Future<Map<String, dynamic>> askQuestion(
    String question,
    String token,
  ) async {
    final trimmedQuestion = question.trim();
    if (trimmedQuestion.isEmpty) {
      throw ApiException('Veuillez entrer une question', 422);
    }

    if (kDebugMode) {
      print('💬 Envoi de question: $trimmedQuestion');
      print('🔑 Token: ${token.isNotEmpty ? "présent" : "absent"}');
    }

    return post(
      '/ask',
      {'question': trimmedQuestion},
      token: token,
      timeout: const Duration(seconds: 40), // Augmenté à 40s
    );
  }

  /// Test de connectivité
  Future<bool> testConnection() async {
    try {
      final response = await get('/health', 
        timeout: const Duration(seconds: 5));
      return response['status'] == 'OK';
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
    if (kDebugMode) {
      print('🔐 Tentative de connexion pour: $loginIdentifier');
    }

    try {
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
}
