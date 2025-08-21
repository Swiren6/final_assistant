import 'package:flutter/material.dart';

class AppConstants {
  // Configuration API
  static const String apiBaseUrl = 'http://localhost:5001/api';
  // Alternative pour les tests réseau
  // static const String apiBaseUrl = 'http://192.168.56.1:5001/api';

  // Couleurs principales
  static const Color primaryColor = Color(0xFF2196F3);
  static const Color primaryColorDark = Color(0xFF1976D2);
  static const Color primaryColorLight = Color(0xFF64B5F6);
  static const Color accentColor = Color(0xFF03DAC6);
  static const Color errorColor = Color(0xFFB00020);
  static const Color successColor = Color(0xFF4CAF50);
  static const Color warningColor = Color(0xFFFF9800);

  // Couleurs du texte
  static const Color textPrimary = Color(0xFF212121);
  static const Color textSecondary = Color(0xFF757575);
  static const Color textHint = Color(0xFF9E9E9E);

  // Couleurs de fond
  static const Color backgroundLight = Color(0xFFF5F5F5);
  static const Color backgroundDark = Color(0xFF303030);
  static const Color surfaceLight = Color(0xFFFFFFFF);
  static const Color surfaceDark = Color(0xFF424242);

  // Espacement
  static const double paddingSmall = 8.0;
  static const double paddingMedium = 16.0;
  static const double paddingLarge = 24.0;
  static const double paddingExtraLarge = 32.0;

  // Border radius
  static const double radiusSmall = 4.0;
  static const double radiusMedium = 8.0;
  static const double radiusLarge = 16.0;
  static const double radiusRound = 24.0;

  // Tailles de police
  static const double fontSizeSmall = 12.0;
  static const double fontSizeMedium = 14.0;
  static const double fontSizeLarge = 16.0;
  static const double fontSizeExtraLarge = 18.0;
  static const double fontSizeTitle = 20.0;
  static const double fontSizeHeading = 24.0;

  // Animation
  static const Duration animationDurationShort = Duration(milliseconds: 200);
  static const Duration animationDurationMedium = Duration(milliseconds: 400);
  static const Duration animationDurationLong = Duration(milliseconds: 600);

  // Timeouts
  static const Duration httpTimeoutDuration = Duration(seconds: 30);
  static const Duration httpTimeoutDurationShort = Duration(seconds: 10);

  // Messages
  static const String noInternetMessage = 'Pas de connexion internet';
  static const String serverErrorMessage = 'Erreur serveur, veuillez réessayer';
  static const String genericErrorMessage = 'Une erreur s\'est produite';
  static const String loadingMessage = 'Chargement...';
  static const String successMessage = 'Opération réussie';

  // Validation
  static const int minPasswordLength = 6;
  static const int maxPasswordLength = 50;
  static const int maxUsernameLength = 50;

  // Chat
  static const int? maxMessageLength = null;
  static const int maxChatHistory = 100;
  static const String defaultWelcomeMessage =
      'Bonjour! Comment puis-je vous aider aujourd\'hui?';

  // App Info
  static const String appName = 'Assistant Scolaire';
  static const String appVersion = '1.0.0';



  // Regex patterns
  static const String emailPattern =
      r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$';
  static const String phonePattern = r'^[+]?[0-9]{8,15}$';

  // Messages d'erreur spécifiques
  static const String invalidCredentialsMessage = 'Identifiants incorrects';
  static const String networkErrorMessage = 'Erreur de connexion réseau';
  static const String timeoutErrorMessage = 'Délai d\'attente dépassé';
  static const String unauthorizedMessage = 'Accès non autorisé';

  // Configuration UI
  static const double maxDialogWidth = 400.0;
  static const double minButtonHeight = 48.0;
  static const double maxInputWidth = 350.0;

  // Breakpoints responsive
  static const double mobileBreakpoint = 600.0;
  static const double tabletBreakpoint = 1024.0;
  static const double desktopBreakpoint = 1440.0;

  // Icônes par défaut
  static const IconData defaultUserIcon = Icons.person;
  static const IconData defaultAssistantIcon = Icons.smart_toy;
  static const IconData defaultErrorIcon = Icons.error_outline;
  static const IconData defaultSuccessIcon = Icons.check_circle;
  static const IconData defaultWarningIcon = Icons.warning;

  // URLs et liens (à modifier selon vos besoins)
  static const String supportEmail = 'support@assistant-scolaire.com';
  static const String privacyPolicyUrl = 'https://example.com/privacy';
  static const String termsOfServiceUrl = 'https://example.com/terms';
}

// Extensions utiles
extension StringExtension on String {
  /// Valide si la chaîne est un email valide
  bool get isValidEmail {
    return RegExp(AppConstants.emailPattern).hasMatch(this);
  }

  /// Valide si la chaîne est un numéro de téléphone valide
  bool get isValidPhone {
    return RegExp(AppConstants.phonePattern).hasMatch(this);
  }

  /// Met en forme la première lettre en majuscule
  String get capitalize {
    if (isEmpty) return this;
    return '${this[0].toUpperCase()}${substring(1).toLowerCase()}';
  }

  /// Met en forme chaque mot avec la première lettre en majuscule
  String get titleCase {
    if (isEmpty) return this;
    return split(' ').map((word) => word.capitalize).join(' ');
  }

  /// Tronque le texte avec des points de suspension
  String truncate(int maxLength) {
    if (length <= maxLength) return this;
    return '${substring(0, maxLength)}...';
  }
}

extension ColorExtension on Color {
  /// Crée un MaterialColor à partir d'une Color
  MaterialColor get materialColor {
    final Map<int, Color> swatch = {
      50: withOpacity(0.1),
      100: withOpacity(0.2),
      200: withOpacity(0.3),
      300: withOpacity(0.4),
      400: withOpacity(0.5),
      500: this,
      600: withOpacity(0.7),
      700: withOpacity(0.8),
      800: withOpacity(0.9),
      900: withOpacity(1.0),
    };
    return MaterialColor(value, swatch);
  }
}

extension BuildContextExtension on BuildContext {
  /// Raccourci pour MediaQuery
  MediaQueryData get mediaQuery => MediaQuery.of(this);

  /// Largeur de l'écran
  double get screenWidth => mediaQuery.size.width;

  /// Hauteur de l'écran
  double get screenHeight => mediaQuery.size.height;

  /// Vérifie si c'est un écran mobile
  bool get isMobile => screenWidth < AppConstants.mobileBreakpoint;

  /// Vérifie si c'est un écran tablette
  bool get isTablet =>
      screenWidth >= AppConstants.mobileBreakpoint &&
      screenWidth < AppConstants.tabletBreakpoint;

  /// Vérifie si c'est un écran desktop
  bool get isDesktop => screenWidth >= AppConstants.tabletBreakpoint;

  /// Theme actuel
  ThemeData get theme => Theme.of(this);

  /// TextTheme actuel
  TextTheme get textTheme => theme.textTheme;

  /// ColorScheme actuel
  ColorScheme get colorScheme => theme.colorScheme;
}
