import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

class StorageService {
  static SharedPreferences? _prefs;
  
  // Clés de stockage
  static const String _tokenKey = 'auth_token';
  static const String _userDataKey = 'user_data';
  static const String _chatHistoryKey = 'chat_history';
  static const String _settingsKey = 'app_settings';

  /// Initialisation du service
  static Future<void> init() async {
    _prefs = await SharedPreferences.getInstance();
  }

  SharedPreferences get prefs {
    if (_prefs == null) {
      throw Exception('StorageService non initialisé. Appelez StorageService.init() d\'abord.');
    }
    return _prefs!;
  }

  /// Sauvegarde du token d'authentification
  Future<void> saveToken(String token) async {
    await prefs.setString(_tokenKey, token);
  }

  /// Récupération du token d'authentification
  Future<String?> getToken() async {
    return prefs.getString(_tokenKey);
  }

  /// Suppression du token
  Future<void> removeToken() async {
    await prefs.remove(_tokenKey);
  }

  /// Sauvegarde des données utilisateur
  Future<void> saveUserData(Map<String, dynamic> userData) async {
    final userDataJson = jsonEncode(userData);
    await prefs.setString(_userDataKey, userDataJson);
  }

  /// Récupération des données utilisateur
  Future<Map<String, dynamic>?> getUserData() async {
    final userDataJson = prefs.getString(_userDataKey);
    if (userDataJson != null) {
      return jsonDecode(userDataJson);
    }
    return null;
  }

  /// Suppression des données utilisateur
  Future<void> removeUserData() async {
    await prefs.remove(_userDataKey);
  }

  /// Sauvegarde de l'historique du chat
  Future<void> saveChatHistory(List<Map<String, dynamic>> messages) async {
    final chatHistoryJson = jsonEncode(messages);
    await prefs.setString(_chatHistoryKey, chatHistoryJson);
  }

  /// Récupération de l'historique du chat
  Future<List<Map<String, dynamic>>> getChatHistory() async {
    final chatHistoryJson = prefs.getString(_chatHistoryKey);
    if (chatHistoryJson != null) {
      final List<dynamic> decoded = jsonDecode(chatHistoryJson);
      return decoded.map((e) => Map<String, dynamic>.from(e)).toList();
    }
    return [];
  }

  /// Suppression de l'historique du chat
  Future<void> clearChatHistory() async {
    await prefs.remove(_chatHistoryKey);
  }

  /// Sauvegarde des paramètres de l'application
  Future<void> saveSettings(Map<String, dynamic> settings) async {
    final settingsJson = jsonEncode(settings);
    await prefs.setString(_settingsKey, settingsJson);
  }

  /// Récupération des paramètres de l'application
  Future<Map<String, dynamic>> getSettings() async {
    final settingsJson = prefs.getString(_settingsKey);
    if (settingsJson != null) {
      return jsonDecode(settingsJson);
    }
    return {
      'theme_mode': 'system',
      'language': 'fr',
      'notifications_enabled': true,
    };
  }

  /// Stockage d'une valeur string
  Future<void> setString(String key, String value) async {
    await prefs.setString(key, value);
  }

  /// Récupération d'une valeur string
  String? getString(String key) {
    return prefs.getString(key);
  }

  /// Stockage d'une valeur boolean
  Future<void> setBool(String key, bool value) async {
    await prefs.setBool(key, value);
  }

  /// Récupération d'une valeur boolean
  bool getBool(String key, {bool defaultValue = false}) {
    return prefs.getBool(key) ?? defaultValue;
  }

  /// Stockage d'une valeur int
  Future<void> setInt(String key, int value) async {
    await prefs.setInt(key, value);
  }

  /// Récupération d'une valeur int
  int getInt(String key, {int defaultValue = 0}) {
    return prefs.getInt(key) ?? defaultValue;
  }

  /// Vérification de l'existence d'une clé
  bool containsKey(String key) {
    return prefs.containsKey(key);
  }

  /// Suppression d'une clé spécifique
  Future<void> remove(String key) async {
    await prefs.remove(key);
  }

  /// Nettoyage complet du stockage
  Future<void> clearAll() async {
    await prefs.clear();
  }

  /// Récupération de toutes les clés
  Set<String> getAllKeys() {
    return prefs.getKeys();
  }
}