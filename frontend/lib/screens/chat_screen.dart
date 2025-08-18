  import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:http/http.dart' as http;
import '../widgets/custom_appbar.dart';
import '../widgets/message_bubble.dart';
import '../widgets/sidebar_menu.dart';
import '../widgets/history_sidebar.dart';
import '../models/message_model.dart';
import '../models/conversation_model.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';
import '../utils/constants.dart';
import '../screens/login_screen.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _messageController = TextEditingController();
  final List<Message> _messages = [];
  final ScrollController _scrollController = ScrollController();
  final ApiService _apiService = ApiService();
  final Set<int> _seenNotificationIds = {};
  
  bool _isLoading = false;
  bool _showHistory = false;
  Timer? _notificationTimer;
  int? _currentConversationId;

  @override
  void initState() {
    super.initState();
    _addWelcomeMessage();
    _startNotificationPolling();
  }

  @override
  void dispose() {
    _notificationTimer?.cancel();
    _messageController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _startNotificationPolling() {
    _notificationTimer = Timer.periodic(
      const Duration(seconds: 50),
      (_) => _checkNotifications(),
    );
  }

  Future<void> _checkNotifications() async {
    try {
      final authService = Provider.of<AuthService>(context, listen: false);
      final response = await http.get(
        Uri.parse('${AppConstants.apiBaseUrl}/notifications'),
        headers: {'Authorization': 'Bearer ${authService.token}'},
      );

      if (response.statusCode == 200) {
        final List<dynamic> data = jsonDecode(response.body);
        bool hasNew = false;

        for (var notif in data) {
          final int id = notif['id'];
          if (!_seenNotificationIds.contains(id)) {
            setState(() {
              _messages.add(Message.notification(
                text: notif['message'],
              ));
              _seenNotificationIds.add(id);
              hasNew = true;
            });
          }
        }

        if (hasNew) _scrollToBottom();
      }
    } catch (e) {
      debugPrint('Erreur notifications: $e');
    }
  }

  void _addWelcomeMessage() {
    setState(() {
      _messages.add(Message.assistant(text: AppConstants.defaultWelcomeMessage));
    });
  }

  void _startNewConversation() {
    setState(() {
      _messages.clear();
      _seenNotificationIds.clear();
      _currentConversationId = null;
    });
    _addWelcomeMessage();
    
    if (_showHistory) {
      setState(() => _showHistory = false);
    }
  }

  Future<void> _loadConversation(List<Map<String, dynamic>> messages) async {
    setState(() {
      _messages.clear();
      _isLoading = true;
    });

    try {
      debugPrint('🔄 Chargement de ${messages.length} messages...');
      
      for (var messageData in messages) {
        try {
          final messageType = messageData['type'] as String? ?? 'system';
          final content = messageData['content'] as String? ?? '';
          
          if (content.isEmpty) {
            debugPrint('⚠️ Message avec contenu vide ignoré');
            continue;
          }
          
          switch (messageType) {
            case 'user':
              _messages.add(Message.user(text: content));
              break;
            case 'assistant':
              _messages.add(Message.assistant(
                text: content,
                sqlQuery: messageData['sql_query'] as String?,
                graphBase64: messageData['graph_data'] as String?,
              ));
              break;
            case 'system':
              _messages.add(Message.system(text: content));
              break;
            default:
              debugPrint('⚠️ Type de message non reconnu: $messageType');
              _messages.add(Message.system(text: content));
          }
        } catch (e) {
          debugPrint('❌ Erreur traitement message: $e');
          debugPrint('📄 Data: $messageData');
        }
      }
      
      setState(() => _showHistory = false);
      _scrollToBottom();
      debugPrint('✅ Conversation chargée avec ${_messages.length} messages');
      
    } catch (e) {
      debugPrint('❌ Erreur chargement conversation: $e');
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Erreur chargement: ${e.toString()}'),
          backgroundColor: Colors.red,
        ),
      );
    } finally {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _saveMessageToHistory(String messageType, String content, {
    String? sqlQuery,
    String? graphData,
  }) async {
    try {
      final authService = Provider.of<AuthService>(context, listen: false);
      
      // Validation de base
      if (authService.token == null || authService.token!.isEmpty) {
        debugPrint('⚠️ Token manquant pour sauvegarde historique');
        return;
      }
      
      // Si pas de conversation courante, en créer une
      if (_currentConversationId == null) {
        debugPrint('🔄 Création nouvelle conversation...');
        
        try {
          final createResponse = await http.post(
            Uri.parse('${AppConstants.apiBaseUrl}/conversations/create'),
            headers: {
              'Content-Type': 'application/json',
              'Authorization': 'Bearer ${authService.token}',
            },
            body: jsonEncode({'first_message': content}),
          );
          
          debugPrint('🌐 POST ${AppConstants.apiBaseUrl}/conversations/create');
          debugPrint('📤 Payload: ${jsonEncode({'first_message': content})}');
          debugPrint('↪️ Réponse ${createResponse.statusCode} | ${createResponse.request?.url}');
          debugPrint('📦 Taille réponse: ${createResponse.body.length} chars');
          
          if (createResponse.statusCode == 201) {
            final responseData = jsonDecode(createResponse.body);
            debugPrint('✅ Réponse décodée avec succès');
            debugPrint('🔍 Clés disponibles: ${responseData.keys.toList()}');
            
            if (responseData['success'] == true && responseData['conversation_id'] != null) {
              _currentConversationId = responseData['conversation_id'] as int;
              debugPrint('✅ Conversation créée avec ID: $_currentConversationId');
            } else {
              debugPrint('❌ Réponse de création invalide: $responseData');
              return;
            }
          } else {
            debugPrint('❌ Erreur création conversation: ${createResponse.statusCode}');
            debugPrint('📄 Body: ${createResponse.body}');
            return;
          }
        } catch (e) {
          debugPrint('❌ Exception création conversation: $e');
          return;
        }
      }
      
      // Sauvegarder le message
      if (_currentConversationId != null) {
        final messageData = {
          'message_type': messageType,
          'content': content,
          'sql_query': sqlQuery,
          'graph_data': graphData,
        };
        
        debugPrint('🌐 POST ${AppConstants.apiBaseUrl}/conversations/$_currentConversationId/messages');
        debugPrint('📤 Payload: ${jsonEncode(messageData)}');
        
        try {
          final messageResponse = await http.post(
            Uri.parse('${AppConstants.apiBaseUrl}/conversations/$_currentConversationId/messages'),
            headers: {
              'Content-Type': 'application/json',
              'Authorization': 'Bearer ${authService.token}',
            },
            body: jsonEncode(messageData),
          );
          
          debugPrint('↪️ Réponse ${messageResponse.statusCode} | ${messageResponse.request?.url}');
          debugPrint('📦 Taille réponse: ${messageResponse.body.length} chars');
          
          if (messageResponse.statusCode == 201) {
            debugPrint('✅ Message sauvegardé avec succès');
          } else {
            debugPrint('❌ Erreur sauvegarde message: ${messageResponse.statusCode}');
            debugPrint('📄 Body: ${messageResponse.body}');
          }
        } catch (e) {
          debugPrint('❌ Exception sauvegarde message: $e');
        }
      }
    } catch (e) {
      debugPrint('❌ Erreur générale sauvegarde: $e');
    }
  }

  Future<void> _sendMessage() async {
    final userMessage = _messageController.text.trim();
    if (userMessage.isEmpty || _isLoading) return;

    _messageController.clear();
    _addUserMessage(userMessage);
    await _processBotResponse(userMessage);
  }

  void _addUserMessage(String message) {
    setState(() {
      _messages.add(Message.user(text: message));
      _messages.add(Message.typing());
      _isLoading = true;
    });
    _scrollToBottom();
    
    _saveMessageToHistory('user', message).catchError((error) {
      debugPrint('Erreur sauvegarde message utilisateur: $error');
    });
  }

  Future<void> _processBotResponse(String userMessage) async {
    try {
      final authService = Provider.of<AuthService>(context, listen: false);
      final response = await _apiService.askQuestion(userMessage, authService.token ?? '');

      _handleSuccessfulResponse(response);
    } catch (e) {
      _handleErrorResponse(e);
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _handleSuccessfulResponse(ApiResponse response) {
    debugPrint('🔥 Réponse complète du backend: ${response.response}');
    
    String responseText = response.response;
    String? graphBase64 = response.graphBase64;
    String? sqlQuery = response.sqlQuery;

    responseText = _cleanResponseText(responseText);

    setState(() {
      _messages.removeLast(); // Retirer le message "typing..."
      _messages.add(
        Message.assistant(
          text: responseText,
          sqlQuery: sqlQuery,
          graphBase64: graphBase64,
        ),
      );
    });

    _saveMessageToHistory(
      'assistant', 
      responseText, 
      sqlQuery: sqlQuery,
      graphData: graphBase64,
    ).catchError((error) {
      debugPrint('Erreur sauvegarde message assistant: $error');
    });
    
    debugPrint('✅ Message ajouté avec graphique: ${graphBase64 != null}');
    _scrollToBottom();
  }

  void _logout() async {
    try {
      final authService = Provider.of<AuthService>(context, listen: false);
      authService.logout();
      
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
  }

  String _cleanResponseText(String text) {
    text = text.replaceAll(RegExp(r'SQL\s*:\s*[^\\n]*', caseSensitive: false), '');
    text = text.replaceAll(RegExp(r'Requête\s*:\s*[^\\n]*', caseSensitive: false), '');
    text = text.replaceAll(RegExp(r'Query\s*:\s*[^\\n]*', caseSensitive: false), '');
    text = text.replaceAll(RegExp(r'\n\s*\n\s*\n+'), '\n\n');
    text = text.trim();
    
    return text;
  }

  void _handleErrorResponse(dynamic error) {
    debugPrint('❌ Erreur de traitement: $error');
    setState(() {
      _messages.removeLast(); // Retirer le message "typing..."
      _messages.add(Message.error(text: _getErrorMessage(error)));
    });
  }

  String _getErrorMessage(dynamic error) {
    if (error is ApiException) {
      switch (error.statusCode) {
        case 401:
          return 'Votre session a expiré. Veuillez vous reconnecter.';
        case 403:
          return 'Vous n\'avez pas l\'autorisation pour cette action.';
        case 404:
          return 'Service non trouvé. Veuillez réessayer plus tard.';
        case 500:
          return 'Erreur du serveur. Veuillez réessayer dans quelques instants.';
        default:
          return 'Erreur: ${error.message}';
      }
    }
    
    if (error is http.ClientException) {
      return 'Problème de connexion réseau. Vérifiez votre connexion internet.';
    }
    
    if (error is TimeoutException) {
      return 'Temps d\'attente dépassé. Le serveur met trop de temps à répondre.';
    }
    
    return 'Une erreur inattendue s\'est produite. Veuillez réessayer.';
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: AppConstants.animationDurationShort,
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _clearChat() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Effacer la conversation'),
        content: const Text('Êtes-vous sûr de vouloir effacer toute la conversation ?'),
        actions: [
          TextButton(
            onPressed: Navigator.of(context).pop,
            child: const Text('Annuler'),
          ),
          TextButton(
            onPressed: () {
              Navigator.of(context).pop();
              _startNewConversation();
            },
            child: const Text('Effacer'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: CustomAppBar(
        title: 'Assistant Scolaire',
        actions: [
          IconButton(
            icon: Icon(
              _showHistory ? Icons.history : Icons.history_outlined,
              color: _showHistory ? AppConstants.primaryColor : null,
            ),
            onPressed: () => setState(() => _showHistory = !_showHistory),
            tooltip: 'Historique des conversations',
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: _logout,
            tooltip: 'Déconnexion',
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _clearChat,
            tooltip: 'Nouvelle conversation',
          ),
          IconButton(
            icon: const Icon(Icons.info_outline),
            onPressed: _showInfoDialog,
            tooltip: 'Informations',
          ),
        ],
      ),
      drawer: const SidebarMenu(),
      body: SafeArea(
        child: Row(
          children: [
            if (_showHistory)
              HistorySidebar(
                onConversationSelected: _loadConversation,
                onNewConversation: _startNewConversation,
              ),
            Expanded(
              child: Column(
                children: [
                  if (_isLoading) _buildLoadingIndicator(),
                  Expanded(child: _buildMessageList()),
                  _buildMessageInput(),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLoadingIndicator() {
    return const LinearProgressIndicator(
      backgroundColor: Colors.transparent,
      valueColor: AlwaysStoppedAnimation<Color>(AppConstants.primaryColor),
    );
  }

  Widget _buildMessageList() {
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppConstants.primaryColor.withOpacity(0.05),
            Colors.transparent,
          ],
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
        ),
      ),
      child: _messages.isEmpty 
          ? _buildEmptyState() 
          : ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.symmetric(
                horizontal: AppConstants.paddingSmall,
                vertical: AppConstants.paddingMedium,
              ),
              itemCount: _messages.length,
              itemBuilder: (context, index) {
                final message = _messages[index];
                
                if (message.type == MessageType.system && 
                    message.text == 'typing...') {
                  return Container(
                    padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
                    child: Row(
                      children: [
                        SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor: AlwaysStoppedAnimation<Color>(
                              AppConstants.primaryColor,
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Text(
                          'Assistant en train de réfléchir...',
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            fontStyle: FontStyle.italic,
                            color: Colors.grey[600],
                          ),
                        ),
                      ],
                    ),
                  );
                }
                
                return MessageBubble(
                  message: message,
                  isMe: message.isMe,
                );
              },
            ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.chat_bubble_outline,
            size: 64,
            color: Colors.grey.shade400,
          ),
          const SizedBox(height: AppConstants.paddingMedium),
          Text(
            'Commencez une conversation',
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  color: Colors.grey.shade600,
                ),
          ),
          const SizedBox(height: AppConstants.paddingSmall),
          Text(
            'Posez une question sur le système scolaire',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Colors.grey.shade500,
                ),
          ),
          const SizedBox(height: AppConstants.paddingLarge),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              'Combien d\'élèves ?',
              'Classes disponibles',
              'Liste des enseignants',
              'Statistiques',
            ].map((text) => _buildSuggestionChip(text)).toList(),
          ),
          if (!_showHistory) ...[
            const SizedBox(height: AppConstants.paddingLarge),
            OutlinedButton.icon(
              onPressed: () => setState(() => _showHistory = true),
              icon: const Icon(Icons.history),
              label: const Text('Voir l\'historique'),
              style: OutlinedButton.styleFrom(
                foregroundColor: AppConstants.primaryColor,
                side: BorderSide(color: AppConstants.primaryColor),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildSuggestionChip(String text) {
    return GestureDetector(
      onTap: () {
        _messageController.text = text;
        _sendMessage();
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: AppConstants.primaryColor.withOpacity(0.1),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: AppConstants.primaryColor.withOpacity(0.3)),
        ),
        child: Text(
          text,
          style: TextStyle(
            color: AppConstants.primaryColor,
            fontSize: 14,
            fontWeight: FontWeight.w500,
          ),
        ),
      ),
    );
  }

  Widget _buildMessageInput() {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppConstants.paddingMedium,
        vertical: AppConstants.paddingMedium,
      ),
      decoration: BoxDecoration(
        color: Theme.of(context).scaffoldBackgroundColor,
        border: Border(top: BorderSide(color: Colors.grey.shade300)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.1),
            blurRadius: 8,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: SafeArea(
        child: Column(
          children: [
            if (_messages.length <= 1) _buildQuickSuggestions(),
            _buildInputField(),
          ],
        ),
      ),
    );
  }

  Widget _buildQuickSuggestions() {
    return Container(
      margin: const EdgeInsets.only(bottom: AppConstants.paddingMedium),
      padding: const EdgeInsets.all(AppConstants.paddingSmall),
      decoration: BoxDecoration(
        color: AppConstants.primaryColor.withOpacity(0.1),
        borderRadius: BorderRadius.circular(AppConstants.radiusMedium),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '💡 Suggestions rapides:',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              fontWeight: FontWeight.bold,
              color: AppConstants.primaryColor,
            ),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 4,
            children: [
              'élèves', 'classes', 'enseignants', 'parents', 
              'nombre élèves', 'moyennes', 'absences'
            ].map((text) => _buildQuickButton(text)).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildInputField() {
    return Row(
      children: [
        Expanded(child: _buildTextField()),
        const SizedBox(width: AppConstants.paddingSmall),
        _buildSendButton(),
      ],
    );
  }

  Widget _buildTextField() {
    return TextField(
      controller: _messageController,
      decoration: InputDecoration(
        hintText: 'Tapez votre question... (ex: "Combien d\'élèves ?", "Classes de 1ère année")',
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppConstants.radiusRound),
          borderSide: BorderSide.none,
        ),
        filled: true,
        fillColor: Colors.grey.shade100,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AppConstants.paddingLarge,
          vertical: AppConstants.paddingMedium,
        ),
        suffixIcon: _messageController.text.isNotEmpty
            ? IconButton(
                icon: const Icon(Icons.clear),
                onPressed: () {
                  _messageController.clear();
                  setState(() {});
                },
              )
            : null,
      ),
      textCapitalization: TextCapitalization.sentences,
      maxLines: null,
      minLines: 1,
      maxLength: AppConstants.maxMessageLength,
      onSubmitted: (_) => _sendMessage(),
      onChanged: (_) => setState(() {}),
      enabled: !_isLoading,
    );
  }

  Widget _buildSendButton() {
    return Container(
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: LinearGradient(
          colors: _isLoading || _messageController.text.trim().isEmpty
              ? [Colors.grey.shade400, Colors.grey.shade500]
              : [AppConstants.primaryColor, AppConstants.primaryColorDark],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      ),
      child: IconButton(
        icon: _isLoading
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                ),
              )
            : const Icon(Icons.send, color: Colors.white),
        onPressed: _isLoading || _messageController.text.trim().isEmpty 
            ? null 
            : _sendMessage,
      ),
    );
  }

  Widget _buildQuickButton(String text) {
    return GestureDetector(
      onTap: () {
        _messageController.text = text;
        _sendMessage();
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: AppConstants.primaryColor.withOpacity(0.2),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppConstants.primaryColor.withOpacity(0.3)),
        ),
        child: Text(
          text,
          style: TextStyle(
            color: AppConstants.primaryColor,
            fontSize: 12,
            fontWeight: FontWeight.w500,
          ),
        ),
      ),
    );
  }

  void _showInfoDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Row(
          children: [
            Icon(Icons.school, color: AppConstants.primaryColor),
            const SizedBox(width: 8),
            const Text('Assistant Scolaire'),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Cet assistant IA peut répondre à vos questions sur le système scolaire et générer des graphiques automatiquement.',
            ),
            const SizedBox(height: AppConstants.paddingMedium),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.blue[50],
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.blue[200]!),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '✨ Fonctionnalités:',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: Colors.blue[800],
                    ),
                  ),
                  const SizedBox(height: 4),
                  const Text('• Réponses en langage naturel'),
                  const Text('• Génération automatique de graphiques'),
                  const Text('• Statistiques et analyses'),
                  const Text('• Export de documents PDF'),
                  const Text('• 🆕 Historique des conversations'),
                ],
              ),
            ),
            const SizedBox(height: AppConstants.paddingMedium),
            Consumer<AuthService>(
              builder: (context, authService, _) => Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.green[50],
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.green[200]!),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '👤 Informations utilisateur:',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        color: Colors.green[800],
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text('ID: ${authService.user?.idpersonne ?? "Non connecté"}'),
                    if (authService.user?.roles.isNotEmpty ?? false)
                      Text('Rôles: ${authService.user!.roles.join(", ")}'),
                  ],
                ),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: Navigator.of(context).pop,
            child: const Text('Fermer'),
          ),
        ],
      ),
    );
  }
}