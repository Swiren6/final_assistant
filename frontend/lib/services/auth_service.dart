import 'package:flutter/foundation.dart';
import '../models/user_model.dart';
import 'api_service.dart';
import 'storage_service.dart';

class AuthService with ChangeNotifier {
  UserModel? _user;
  String? _token;
  bool _isAuthenticated = false;
  bool _isLoading = false;
  String? _errorMessage;

  // Getters
  UserModel? get user => _user;
  String? get token => _token; // Getter public pour le token
  bool get isAuthenticated => _isAuthenticated;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  final ApiService _apiService = ApiService();
  final StorageService _storageService = StorageService();

  AuthService() {
    checkAuthStatus();
  }

  Future<void> checkAuthStatus() async {
    _setLoading(true);
    try {
      final token = await _storageService.getToken();
      final userData = await _storageService.getUserData();

      if (token != null && userData != null) {
        _token = token;
        _user = UserModel.fromJson(userData);
        _isAuthenticated = true;
        debugPrint('✅ Session restaurée depuis le storage');
      }
    } catch (e) {
      debugPrint('Erreur vérification statut auth: $e');
      await logout();
    } finally {
      _setLoading(false);
    }
  }

  Future<bool> login(String loginIdentifier, String password) async {
    debugPrint('🔐 AuthService.login() démarré');
    _setLoading(true);
    _clearError();

    try {
      final response = await _apiService.login(loginIdentifier, password);
      final receivedToken = response['token'];

      if (receivedToken != null && receivedToken.toString().isNotEmpty) {
        _token = receivedToken.toString();
        // Créer l'utilisateur depuis la réponse
        try {
          _user = UserModel.fromJson(response);
          debugPrint('✅ UserModel créé: ${_user?.idpersonne}');
        } catch (e) {
          debugPrint('⚠️ Erreur création UserModel: $e');
          // Créer un utilisateur par défaut si échec
          _user = UserModel(
            idpersonne: response['idpersonne'] ?? 0,
            roles: List<String>.from(response['roles'] ?? ['USER']),
            changepassword: response['changepassword'] ?? 0,
          );
        }

        _isAuthenticated = true;
        debugPrint('✅ isAuthenticated défini à true');

        // Sauvegarder dans le storage
        await _storageService.saveToken(_token!);
        await _storageService.saveUserData(response);
        debugPrint('✅ Données sauvegardées dans le storage');

        debugPrint('🎉 Connexion RÉUSSIE');
        return true;
      } else {
        debugPrint('❌ Token NULL ou vide dans la réponse');
        _setError('Aucun token reçu du serveur');
        return false;
      }
    } catch (e) {
      debugPrint('❌ Erreur login: $e');
      _setError(e.toString());
      return false;
    } finally {
      _setLoading(false);
      debugPrint('🔚 AuthService.login() terminé');
    }
  }

  Future<void> logout() async {
    _setLoading(true);
    try {
      await _storageService.clearAll();
      _user = null;
      _token = null;
      _isAuthenticated = false;
      _clearError();
      debugPrint('✅ Déconnexion réussie');
    } catch (e) {
      debugPrint('Erreur lors de la déconnexion: $e');
    } finally {
      _setLoading(false);
    }
  }

  Future<void> updateUser(UserModel updatedUser) async {
    _user = updatedUser;
    await _storageService.saveUserData(updatedUser.toJson());
    notifyListeners();
  }

  bool hasRole(String role) => _user?.hasRole(role) ?? false;
  bool get mustChangePassword => _user?.changepassword ?? false;

  // Méthodes privées
  void _setLoading(bool loading) {
    _isLoading = loading;
    notifyListeners();
    debugPrint('⏳ Loading: $loading');
  }

  void _setError(String error) {
    _errorMessage = error;
    notifyListeners();
    debugPrint('❌ Erreur: $error');
  }

  void _clearError() {
    _errorMessage = null;
    notifyListeners();
  }
}
