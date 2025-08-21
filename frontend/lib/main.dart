import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'screens/login_screen.dart';
import 'screens/chat_screen.dart';
import 'services/auth_service.dart';
import 'services/storage_service.dart';
import 'utils/theme.dart';
import 'utils/constants.dart';
import 'screens/notification_checker.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialisation du service de stockage
  await StorageService.init();

  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthService()),
      ],
      child: MaterialApp(
        title: 'Assistant Scolaire',
        theme: AppTheme.lightTheme,
        darkTheme: AppTheme.darkTheme,
        themeMode: ThemeMode.system,
        home: const AuthWrapper(),
        routes: {
          '/login': (context) => const LoginScreen(),
          '/chat': (context) => const ChatScreen(),
          '/notifications': (context) => const NotificationChecker(),
        },
      ),
    );
  }
}

class AuthWrapper extends StatefulWidget {
  const AuthWrapper({super.key});

  @override
  State<AuthWrapper> createState() => _AuthWrapperState();
}

class _AuthWrapperState extends State<AuthWrapper> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _checkAuthStatus();
    });
  }

  void _checkAuthStatus() async {
    final authService = Provider.of<AuthService>(context, listen: false);
    await authService.checkAuthStatus();
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<AuthService>(
      builder: (context, authService, child) {
        if (authService.isLoading) {
          return const Scaffold(
            body: Center(
              child: CircularProgressIndicator(),
            ),
          );
        }

        return authService.isAuthenticated
            ? const ChatScreen()
            : const LoginScreen();
      },
    );
  }
}

class GraphPage extends StatelessWidget {
  final String base64Image;

  const GraphPage(this.base64Image, {super.key});

  @override
  Widget build(BuildContext context) {
    try {
      Uint8List imageBytes = base64Decode(base64Image);
      return Scaffold(
        appBar: AppBar(title: const Text("Graphique généré")),
        body: Center(child: Image.memory(imageBytes)),
      );
    } catch (e) {
      return Scaffold(
        appBar: AppBar(title: const Text("Erreur")),
        body: Center(child: Text("Impossible d'afficher l'image.")),
      );
    }
  }
}
