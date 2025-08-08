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
      if (token != null && token.isNotEmpty) 
        'Authorization': 'Bearer $token',
    };
  }

  // Méthode générique pour gérer les réponses
  Map<String, dynamic> _handleResponse(http.Response response) {
    if (kDebugMode) {
      print('↪️ Réponse ${response.statusCode} | ${response.request?.url}');
      print('📦 Body: ${response.body}');
    }

    switch (response.statusCode) {
      case 200:
      case 201:
        try {
          return jsonDecode(response.body);
        } catch (e) {
          throw ApiException('Format de réponse invalide', 500);
        }
      case 400:
        throw ApiException('Requête incorrecte', 400);
      case 401:
        throw ApiException('Authentification requise', 401);
      case 403:
        throw ApiException('Accès refusé', 403);
      case 404:
        throw ApiException('Ressource non trouvée', 404);
      case 500:
        throw ApiException('Erreur serveur', 500);
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
        print('📤 Body: $body');
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
      throw ApiException('Erreur inattendue: ${e.toString()}');
    }
  }

  /// Envoi d'une question au chat
  Future<Map<String, dynamic>> askQuestion(
    String question,
    String token,
  ) async {
    return post(
      '/ask', // Note: pas de double /api
      {'question': question.trim()},
      token: token,
      timeout: const Duration(seconds: 30),
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
    try {
      return await post(
        '/login',
        {
          'login_identifier': loginIdentifier,
          'password': password,
        },
        timeout: const Duration(seconds: 15),
      );
    } on ApiException {
      rethrow;
    } catch (e) {
      throw ApiException('Erreur lors de la connexion: ${e.toString()}');
    }
  }
}