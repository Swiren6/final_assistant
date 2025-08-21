import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:provider/provider.dart';
import '../services/auth_service.dart';
import '../utils/constants.dart';

class HistorySidebar extends StatefulWidget {
  final Function(List<Map<String, dynamic>>) onConversationSelected;
  final Function() onNewConversation;

  const HistorySidebar({
    super.key,
    required this.onConversationSelected,
    required this.onNewConversation,
  });

  @override
  State<HistorySidebar> createState() => _HistorySidebarState();
}

class _HistorySidebarState extends State<HistorySidebar> {
  List<Map<String, dynamic>> _conversations = [];
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadConversations();
  }

  Future<void> _loadConversations() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final authService = Provider.of<AuthService>(context, listen: false);
      
      if (authService.token == null) {
        throw Exception('Token d\'authentification manquant');
      }

      debugPrint('🌐 GET ${AppConstants.apiBaseUrl}/conversations');
      
      final response = await http.get(
        Uri.parse('${AppConstants.apiBaseUrl}/conversations'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ${authService.token}',
        },
      );

      debugPrint('↪️ Réponse ${response.statusCode} | ${response.request?.url}');
      debugPrint('📦 Taille réponse: ${response.body.length} chars');

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        debugPrint('✅ Réponse décodée avec succès');
        debugPrint('🔍 Clés disponibles: ${data.keys.toList()}');
        
        if (data['success'] == true && data['conversations'] is List) {
          final conversations = List<Map<String, dynamic>>.from(
            data['conversations'].map((conv) => Map<String, dynamic>.from(conv))
          );
          
          setState(() {
            _conversations = conversations;
            _isLoading = false;
          });
          
          debugPrint('✅ ${conversations.length} conversations chargées');
        } else {
          throw Exception('Format de réponse invalide');
        }
      } else {
        final errorBody = response.body;
        debugPrint('❌ Erreur ${response.statusCode}: $errorBody');
        throw Exception('Erreur serveur: ${response.statusCode}');
      }
    } catch (e) {
      debugPrint('❌ Erreur chargement conversations: $e');
      setState(() {
        _error = 'Erreur lors de la récupération des conversations (Code: ${e.toString().contains('500') ? '500' : 'NETWORK'})';
        _isLoading = false;
      });
    }
  }

  Future<void> _loadConversationMessages(int conversationId) async {
    try {
      debugPrint('🔄 Chargement messages conversation $conversationId');
      
      final authService = Provider.of<AuthService>(context, listen: false);
      
      final response = await http.get(
        Uri.parse('${AppConstants.apiBaseUrl}/conversations/$conversationId/messages'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ${authService.token}',
        },
      );

      debugPrint('↪️ Messages ${response.statusCode} | conversation $conversationId');

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        
        if (data['success'] == true && data['messages'] is List) {
          final messages = List<Map<String, dynamic>>.from(
            data['messages'].map((msg) => Map<String, dynamic>.from(msg))
          );
          
          debugPrint('✅ ${messages.length} messages chargés');
          widget.onConversationSelected(messages);
        } else {
          throw Exception('Format de messages invalide');
        }
      } else {
        throw Exception('Erreur chargement messages: ${response.statusCode}');
      }
    } catch (e) {
      debugPrint('❌ Erreur chargement messages: $e');
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Erreur chargement messages: ${e.toString()}'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  Future<void> _deleteConversation(int conversationId) async {
    try {
      final authService = Provider.of<AuthService>(context, listen: false);
      
      final response = await http.post(
        Uri.parse('${AppConstants.apiBaseUrl}/conversations/$conversationId/delete'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ${authService.token}',
        },
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          setState(() {
            _conversations.removeWhere((conv) => conv['id'] == conversationId);
          });
          
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Conversation supprimée'),
              backgroundColor: Colors.green,
            ),
          );
        }
      } else {
        throw Exception('Erreur suppression: ${response.statusCode}');
      }
    } catch (e) {
      debugPrint('❌ Erreur suppression: $e');
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Erreur suppression: ${e.toString()}'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 300,
      decoration: BoxDecoration(
        color: Colors.grey[50],
        border: Border(
          right: BorderSide(
            color: Colors.grey[300]!,
            width: 1,
          ),
        ),
      ),
      child: Column(
        children: [
          // En-tête
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppConstants.primaryColor,
              border: Border(
                bottom: BorderSide(color: Colors.grey[300]!),
              ),
            ),
            child: Row(
              children: [
                const Icon(Icons.history, color: Colors.white),
                const SizedBox(width: 8),
                const Expanded(
                  child: Text(
                    'Historique',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.refresh, color: Colors.white),
                  onPressed: _loadConversations,
                  tooltip: 'Actualiser',
                ),
              ],
            ),
          ),
          
          // Bouton nouvelle conversation
          Container(
            padding: const EdgeInsets.all(16),
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: widget.onNewConversation,
              icon: const Icon(Icons.add),
              label: const Text('Nouvelle conversation'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppConstants.primaryColor,
                foregroundColor: Colors.white,
              ),
            ),
          ),
          
          // Liste des conversations
          Expanded(
            child: _buildConversationsList(),
          ),
        ],
      ),
    );
  }

  Widget _buildConversationsList() {
    if (_isLoading) {
      return const Center(
        child: CircularProgressIndicator(),
      );
    }

    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.error_outline,
                size: 48,
                color: Colors.grey[400],
              ),
              const SizedBox(height: 16),
              Text(
                _error!,
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: Colors.grey[600],
                  fontSize: 14,
                ),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _loadConversations,
                child: const Text('Réessayer'),
              ),
            ],
          ),
        ),
      );
    }

    if (_conversations.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.chat_bubble_outline,
                size: 48,
                color: Colors.grey[400],
              ),
              const SizedBox(height: 16),
              Text(
                'Aucune conversation',
                style: TextStyle(
                  color: Colors.grey[600],
                  fontSize: 16,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Commencez une nouvelle conversation',
                style: TextStyle(
                  color: Colors.grey[500],
                  fontSize: 14,
                ),
              ),
            ],
          ),
        ),
      );
    }

    return ListView.builder(
      itemCount: _conversations.length,
      itemBuilder: (context, index) {
        final conversation = _conversations[index];
        final title = conversation['title'] as String? ?? 'Sans titre';
        final createdAt = conversation['created_at'] as String? ?? '';
        final messageCount = conversation['message_count'] as int? ?? 0;
        final conversationId = conversation['id'] as int;
        
        // Format de la date
        String formattedDate = '';
        if (createdAt.isNotEmpty) {
          try {
            final date = DateTime.parse(createdAt);
            formattedDate = '${date.day}/${date.month}/${date.year}';
          } catch (e) {
            formattedDate = createdAt;
          }
        }

        return Card(
          margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          child: ListTile(
            title: Text(
              title,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w500,
              ),
            ),
            subtitle: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (formattedDate.isNotEmpty)
                  Text(
                    formattedDate,
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.grey[600],
                    ),
                  ),
                Text(
                  '$messageCount messages',
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.grey[500],
                  ),
                ),
              ],
            ),
            leading: CircleAvatar(
              backgroundColor: AppConstants.primaryColor,
              child: Text(
                title.isNotEmpty ? title[0].toUpperCase() : '?',
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            trailing: PopupMenuButton<String>(
              onSelected: (value) {
                if (value == 'delete') {
                  _showDeleteConfirmation(conversationId);
                }
              },
              itemBuilder: (context) => [
                const PopupMenuItem<String>(
                  value: 'delete',
                  child: Row(
                    children: [
                      Icon(Icons.delete, color: Colors.red),
                      SizedBox(width: 8),
                      Text('Supprimer'),
                    ],
                  ),
                ),
              ],
            ),
            onTap: () => _loadConversationMessages(conversationId),
            dense: true,
          ),
        );
      },
    );
  }

  void _showDeleteConfirmation(int conversationId) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Supprimer la conversation'),
        content: const Text(
          'Êtes-vous sûr de vouloir supprimer cette conversation ? '
          'Cette action ne peut pas être annulée.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Annuler'),
          ),
          TextButton(
            onPressed: () {
              Navigator.of(context).pop();
              _deleteConversation(conversationId);
            },
            style: TextButton.styleFrom(
              foregroundColor: Colors.red,
            ),
            child: const Text('Supprimer'),
          ),
        ],
      ),
    );
  }
}