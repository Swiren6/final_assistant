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

class ApiResponse {
  final String response;
  final String? sqlQuery;
  final String? graphBase64;
  final bool hasGraph;
  final Map<String, dynamic>? userData;
  final String status;
  final DateTime timestamp;
  // Ajout des champs pour PDF
  final String? pdfUrl;
  final String? pdfType;

  ApiResponse({
    required this.response,
    this.sqlQuery,
    this.graphBase64,
    this.hasGraph = false,
    this.userData,
    this.status = 'success',
    required this.timestamp,
    this.pdfUrl,
    this.pdfType,
  });

  factory ApiResponse.fromJson(Map<String, dynamic> json) {
    String? extractedGraph;
    bool graphFound = false;

    // EXTRACTION ROBUSTE DU GRAPHIQUE
    // Méthode 1: Chercher directement dans 'graph'
    if (json['graph'] != null && json['graph'].toString().isNotEmpty) {
      extractedGraph = json['graph'].toString();
      graphFound = true;
      if (kDebugMode) {
        print('🖼️ Graphique trouvé dans json["graph"]');
      }
    }

    // Méthode 2: Chercher dans 'response' (graphique inline)
    if (extractedGraph == null && json['response'] != null) {
      final responseText = json['response'].toString();
      final graphRegex = RegExp(r'data:image/[^;]+;base64,[A-Za-z0-9+/=]+');
      final match = graphRegex.firstMatch(responseText);

      if (match != null) {
        extractedGraph = match.group(0);
        graphFound = true;
        if (kDebugMode) {
          print('🖼️ Graphique extrait du texte de réponse');
        }
      }
    }

    // Méthode 3: Vérifier has_graph comme indicateur
    if (json['has_graph'] == true) {
      graphFound = true;
      if (kDebugMode) {
        print('📊 has_graph=true détecté');
      }
    }

    return ApiResponse(
      response: json['response']?.toString() ?? '',
      sqlQuery: json['sql_query']?.toString(),
      graphBase64: extractedGraph,
      hasGraph: graphFound,
      pdfUrl: json['pdf_url'] as String?,
      pdfType: json['pdf_type'] as String?,
      userData: json['user'] as Map<String, dynamic>?,
      status: json['status']?.toString() ?? 'success',
      timestamp: json['timestamp'] != null
          ? DateTime.tryParse(json['timestamp'].toString()) ?? DateTime.now()
          : DateTime.now(),
    );
  }
}

class ApiService {
  static const String baseUrl = AppConstants.apiBaseUrl;
  static const Duration defaultTimeout = Duration(seconds: 50);
  static const Duration longTimeout = Duration(seconds: 120);
  static const Duration loginTimeout = Duration(seconds: 15);

  Map<String, String> _getHeaders(String? token) {
    return {
      'Content-Type': 'application/json; charset=utf-8',
      'Accept': 'application/json',
      if (token != null && token.isNotEmpty) 'Authorization': 'Bearer $token',
    };
  }

  // Méthode générique pour gérer les réponses
  Map<String, dynamic> _handleResponse(http.Response response) {
    if (kDebugMode) {
      print('↪️ Réponse ${response.statusCode} | ${response.request?.url}');
      print('📦 Taille réponse: ${response.body.length} chars');
    }

    switch (response.statusCode) {
      case 200:
      case 201:
        try {
          final decoded = jsonDecode(response.body);
          if (kDebugMode) {
            print('✅ Réponse décodée avec succès');
            if (decoded is Map<String, dynamic>) {
              final keys = decoded.keys.toList();
              print('🔍 Clés disponibles: $keys');

              // Debug spécial pour les graphiques
              _debugGraphData(decoded);
            }
          }
          return decoded;
        } catch (e) {
          if (kDebugMode) {
            print('❌ Erreur décodage JSON: $e');
            print('📝 Extrait: ${response.body.substring(0, 200)}...');
          }
          throw ApiException('Format de réponse invalide', 500,
              {'raw_response': response.body.substring(0, 500)});
        }
      case 400:
        throw ApiException(
            _extractErrorMessage(response, 'Requête incorrecte'), 400);
      case 401:
        throw ApiException('Session expirée - Veuillez vous reconnecter', 401);
      case 403:
        throw ApiException(_extractErrorMessage(response, 'Accès refusé'), 403);
      case 404:
        throw ApiException('Service non trouvé', 404);
      case 422:
        throw ApiException(
            _extractErrorMessage(response, 'Données invalides'), 422);
      case 500:
        throw ApiException(
            _extractErrorMessage(response, 'Erreur serveur interne'), 500);
      case 503:
        throw ApiException('Service temporairement indisponible', 503);
      default:
        throw ApiException(
          'Erreur inattendue: ${response.statusCode}',
          response.statusCode,
        );
    }
  }

  void _debugGraphData(Map<String, dynamic> data) {
    // Debug pour 'graph' direct
    if (data['graph'] != null) {
      final graph = data['graph'].toString();
      if (graph.startsWith('data:image')) {
        print('🖼️ Graphique direct trouvé, taille: ${graph.length}');
      }
    }

    // Debug pour has_graph
    if (data['has_graph'] == true) {
      print('📊 has_graph=true confirmé');
    }

    // Debug pour graphique dans response
    if (data['response'] != null) {
      final response = data['response'].toString();
      if (response.contains('data:image')) {
        print('🖼️ Graphique inline détecté dans response');
      }
    }
  }

  String _extractErrorMessage(http.Response response, String defaultMessage) {
    try {
      final errorBody = jsonDecode(response.body);
      if (errorBody['error'] != null) {
        return errorBody['error'].toString();
      }
      if (errorBody['message'] != null) {
        return errorBody['message'].toString();
      }
      if (errorBody['details'] != null) {
        return errorBody['details'].toString();
      }
    } catch (_) {
      // Ignore JSON parsing errors for error messages
    }
    return defaultMessage;
  }

  // Méthode générique GET
  Future<Map<String, dynamic>> get(
    String endpoint, {
    String? token,
    Duration? timeout,
    Map<String, String>? queryParams,
  }) async {
    try {
      var uri = Uri.parse('$baseUrl$endpoint');
      if (queryParams != null && queryParams.isNotEmpty) {
        uri = uri.replace(queryParameters: queryParams);
      }

      if (kDebugMode) {
        print('🌐 GET $uri');
      }

      final response = await http
          .get(
            uri,
            headers: _getHeaders(token),
          )
          .timeout(timeout ?? defaultTimeout);

      return _handleResponse(response);
    } on SocketException {
      throw ApiException('Aucune connexion internet disponible');
    } on TimeoutException {
      throw ApiException('Délai d\'attente dépassé - Serveur trop lent');
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
        print(
            '📤 Payload: ${body.length > 300 ? "${body.substring(0, 300)}..." : body}');
      }

      final response = await http
          .post(
            uri,
            headers: _getHeaders(token),
            body: body,
          )
          .timeout(timeout ?? defaultTimeout);

      return _handleResponse(response);
    } on SocketException {
      throw ApiException('Aucune connexion internet disponible');
    } on TimeoutException {
      throw ApiException('Délai d\'attente dépassé - Serveur trop lent');
    } on http.ClientException catch (e) {
      throw ApiException('Erreur réseau: ${e.message}');
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('Erreur inattendue: ${e.toString()}');
    }
  }

  /// 🤖 Envoi d'une question au chat avec gestion optimisée des graphiques
  Future<ApiResponse> askQuestion(
    String question,
    String token,
  ) async {
    if (kDebugMode) {
      print(
          '🤖 Question envoyée: "${question.length > 100 ? "${question.substring(0, 100)}..." : question}"');
    }

    try {
      final response = await post(
        '/ask',
        {
          'question': question.trim(),
          'include_graph': true,
          'response_format': 'enhanced',
          'max_tokens': null,
        },
        token: token,
        timeout:
            longTimeout, // Plus de temps pour les questions complexes avec graphiques
      );

      if (kDebugMode) {
        print('✅ Réponse chat reçue');

        // Debug détaillé pour graphiques
        if (response['has_graph'] == true || response['graph'] != null) {
          print('📊 Réponse contient un graphique');
          if (response['graph'] != null) {
            final graphSize = response['graph'].toString().length;
            print('📏 Taille graphique: $graphSize caractères');
          }
        }
      }

      return ApiResponse.fromJson(response);
    } catch (e) {
      if (kDebugMode) {
        print('❌ Erreur question chat: $e');
      }
      rethrow;
    }
  }

  /// 🔐 Connexion utilisateur avec gestion d'erreurs améliorée
  Future<Map<String, dynamic>> login(
    String loginIdentifier,
    String password,
  ) async {
    if (kDebugMode) {
      print('🔐 Tentative connexion: $loginIdentifier');
    }

    try {
      // Validation côté client
      if (loginIdentifier.trim().isEmpty) {
        throw ApiException('Identifiant requis', 400);
      }
      if (password.trim().isEmpty) {
        throw ApiException('Mot de passe requis', 400);
      }

      final response = await post(
        '/login',
        {
          'login_identifier': loginIdentifier.trim(),
          'password': password,
        },
        timeout: loginTimeout,
      );

      if (kDebugMode) {
        print('✅ Connexion réussie');
        if (response['user'] != null) {
          final user = response['user'] as Map<String, dynamic>;
          print(
              '👤 Utilisateur: ${user['username']} (ID: ${user['idpersonne']})');
          if (user['roles'] != null) {
            print('🔑 Rôles: ${user['roles']}');
          }
        }
      }

      return response;
    } on ApiException catch (e) {
      // Améliorer les messages d'erreur de connexion
      if (e.statusCode == 401) {
        throw ApiException('Identifiants incorrects', 401);
      } else if (e.statusCode == 403) {
        throw ApiException('Compte désactivé ou accès refusé', 403);
      }
      rethrow;
    } catch (e) {
      if (kDebugMode) {
        print('❌ Erreur connexion: $e');
      }
      throw ApiException('Erreur lors de la connexion: ${e.toString()}');
    }
  }

  /// 📊 Génération de graphique à partir de données personnalisées
  Future<String?> generateCustomGraph(
    List<Map<String, dynamic>> data,
    String token, {
    String? graphType, // 'bar', 'line', 'pie'
    String? title,
  }) async {
    try {
      if (kDebugMode) {
        print('📊 Génération graphique personnalisé: ${data.length} points');
      }

      final response = await post(
        '/graph',
        {
          'data': data,
          'graph_type': graphType,
          'title': title ?? 'Graphique personnalisé',
        },
        token: token,
        timeout: longTimeout,
      );

      if (response['success'] == true && response['graph'] != null) {
        if (kDebugMode) {
          print('✅ Graphique personnalisé généré');
        }
        return response['graph'].toString();
      }

      return null;
    } catch (e) {
      if (kDebugMode) {
        print('❌ Erreur génération graphique: $e');
      }
      return null;
    }
  }

  /// 🔔 Récupération des notifications
  Future<List<Map<String, dynamic>>> getNotifications(String token) async {
    try {
      final response = await get(
        '/notifications',
        token: token,
        timeout: const Duration(seconds: 10),
      );

      if (response['notifications'] is List) {
        final notifications =
            List<Map<String, dynamic>>.from(response['notifications']);
        if (kDebugMode) {
          print('🔔 ${notifications.length} notifications récupérées');
        }
        return notifications;
      }

      // Support pour format direct (liste à la racine)
      if (response is List) {
        return List<Map<String, dynamic>>.from(response as List);
      }

      return [];
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ Erreur notifications: $e');
      }
      return [];
    }
  }

  /// 🏥 Test de connectivité avec diagnostic détaillé
  Future<Map<String, dynamic>> testConnection() async {
    final startTime = DateTime.now();

    try {
      final response =
          await get('/health', timeout: const Duration(seconds: 5));

      final endTime = DateTime.now();
      final responseTime = endTime.difference(startTime).inMilliseconds;

      final isHealthy =
          response['status'] == 'healthy' || response['status'] == 'OK';

      final result = {
        'connected': isHealthy,
        'status': response['status'] ?? 'unknown',
        'response_time': responseTime,
        'timestamp': DateTime.now().toIso8601String(),
        'services': response['services'] ?? {},
      };

      if (kDebugMode) {
        print(isHealthy
            ? '✅ Connexion OK (${responseTime}ms)'
            : '⚠️ Service dégradé');
      }

      return result;
    } catch (e) {
      if (kDebugMode) {
        print('❌ Test connexion échoué: $e');
      }

      return {
        'connected': false,
        'error': e.toString(),
        'response_time': -1,
        'timestamp': DateTime.now().toIso8601String(),
      };
    }
  }

  /// 🔧 Statut de l'assistant IA
  Future<Map<String, dynamic>?> getAssistantStatus(String token) async {
    try {
      final response = await get('/status', token: token);

      if (kDebugMode) {
        print('🤖 Statut assistant récupéré');
        if (response['status'] != null) {
          print('📊 Assistant: ${response['status']}');
        }
      }

      return response;
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ Erreur statut assistant: $e');
      }
      return null;
    }
  }

  /// 🔄 Réinitialiser l'assistant
  Future<bool> resetAssistant(String token) async {
    try {
      if (kDebugMode) {
        print('🔄 Réinitialisation assistant...');
      }

      final response = await post(
        '/reinit',
        {},
        token: token,
        timeout: const Duration(seconds: 30),
      );

      final success = response['success'] == true;

      if (kDebugMode) {
        print(success ? '✅ Réinitialisation OK' : '❌ Réinitialisation échouée');
      }

      return success;
    } catch (e) {
      if (kDebugMode) {
        print('❌ Erreur réinitialisation: $e');
      }
      return false;
    }
  }

  /// 🧹 Effacer l'historique des conversations
  Future<bool> clearHistory(String token) async {
    try {
      if (kDebugMode) {
        print('🧹 Effacement historique...');
      }

      final response = await post(
        '/clear-history',
        {},
        token: token,
        timeout: const Duration(seconds: 15),
      );

      final success = response['success'] == true;

      if (kDebugMode) {
        print(success ? '✅ Historique effacé' : '❌ Effacement échoué');
      }

      return success;
    } catch (e) {
      if (kDebugMode) {
        print('❌ Erreur effacement historique: $e');
      }
      return false;
    }
  }

  /// 📄 Demande de génération de documents (attestation)
  Future<Map<String, dynamic>?> requestDocument(
    String documentType,
    String studentName,
    String token, {
    Map<String, dynamic>? additionalParams,
  }) async {
    try {
      if (kDebugMode) {
        print('📄 Demande document $documentType pour: $studentName');
      }

      final payload = {
        'question': '$documentType de $studentName',
        'document_type': documentType,
        'student_name': studentName,
        ...?additionalParams,
      };

      final response = await post(
        '/ask',
        payload,
        token: token,
        timeout: longTimeout,
      );

      if (kDebugMode) {
        if (response['pdf_url'] != null) {
          print('📄 Document généré: ${response['pdf_url']}');
        }
      }

      return response;
    } catch (e) {
      if (kDebugMode) {
        print('❌ Erreur génération document: $e');
      }
      return null;
    }
  }
}
