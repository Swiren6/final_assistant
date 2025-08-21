import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/auth_service.dart';
import '../utils/constants.dart';
import '../screens/login_screen.dart';

class SidebarMenu extends StatelessWidget {
  const SidebarMenu({super.key});

  @override
  Widget build(BuildContext context) {
    return Drawer(
      child: Column(
        children: [
          _buildHeader(context),
          Expanded(
            child: ListView(
              padding: EdgeInsets.zero,
              children: [
                ListTile(
                  leading: const Icon(Icons.chat),
                  title: const Text('Chat'),
                  onTap: () {
                    Navigator.pop(context);
                    Navigator.pushReplacementNamed(context, '/chat');
                  },
                ),
                const Divider(),
                ListTile(
                  leading: const Icon(Icons.logout, color: Colors.red),
                  title: const Text('Déconnexion', style: TextStyle(color: Colors.red)),
                  onTap: () => _logout(context),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Consumer<AuthService>(
      builder: (context, authService, child) {
        return UserAccountsDrawerHeader(
          accountName: Text('ID: ${authService.user?.idpersonne ?? ""}'),
          accountEmail: Text(authService.user?.email ?? ''),
          currentAccountPicture: CircleAvatar(
            backgroundColor: Colors.white,
            child: Icon(
              Icons.person,
              color: AppConstants.primaryColor,
              size: 40,
            ),
          ),
          decoration: BoxDecoration(
            color: AppConstants.primaryColor,
          ),
        );
      },
    );
  }

  
  void _logout(BuildContext context) {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: const Text('Déconnexion'),
          content: const Text('Êtes-vous sûr de vouloir vous déconnecter ?'),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Annuler'),
            ),
            TextButton(
              onPressed: () async {
                Navigator.of(context).pop();
                try {
                  final authService = Provider.of<AuthService>(context, listen: false);
                  await authService.logout();
                  
                  Navigator.of(context).pushAndRemoveUntil(
                    MaterialPageRoute(builder: (context) => const LoginScreen()),
                    (Route<dynamic> route) => false,
                  );
                } catch (e) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text('Erreur lors de la déconnexion: $e'),
                      backgroundColor: Colors.red,
                    ),
                  );
                }
              },
              child: const Text('Déconnexion'),
            ),
          ],
        );
      },
    );
  }
}