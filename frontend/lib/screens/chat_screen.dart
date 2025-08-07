import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:http/http.dart' as http;
import '../widgets/custom_appbar.dart';
import '../widgets/message_bubble.dart';
import '../widgets/sidebar_menu.dart';
import '../models/message_model.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';
import '../utils/constants.dart';

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
  Timer? _notificationTimer;

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
      const Duration(seconds: 15),
      (_) => _checkNotifications(),
    );
  }

  Future<void> _checkNotifications() async {
    try {
      final authService = Provider.of<AuthService>(context, listen: false);
      if (authService.token == null) return;

      final response = await http.get(
        Uri.parse('${AppConstants.apiBaseUrl}/notifications'),
        headers: {'Authorization': 'Bearer ${authService.token}'},
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final List<dynamic> data = jsonDecode(response.body);
        bool hasNew = false;

        for (var notif in data) {
          final int id = notif['id'];
          if (!_seenNotificationIds.contains(id)) {
            setState(() {
              _messages.add(Message.notification(
                text: notif['message'],
                // timestamp: DateTime.parse(notif['created_at']), // Retiré si non supporté
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
      _messages.add(Message.assistant(
        text: AppConstants.defaultWelcomeMessage,
        // timestamp: DateTime.now(), // Retiré si non supporté
      ));
    });
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
      _messages.add(Message.user(
        text: message,
        // timestamp: DateTime.now(), // Retiré si non supporté
      ));
      _messages.add(Message.typing());
      _isLoading = true;
    });
    _scrollToBottom();
  }

  Future<void> _processBotResponse(String userMessage) async {
    try {
      final authService = Provider.of<AuthService>(context, listen: false);
      final response = await _apiService.askQuestion(
        userMessage, 
        authService.token ?? '',
      );

      _handleSuccessfulResponse(response);
    } on ApiException catch (e) {
      _handleApiError(e);
    } catch (e) {
      _handleGenericError(e);
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _handleSuccessfulResponse(Map<String, dynamic> response) {
    setState(() {
      _messages.removeLast();
      _messages.add(
        Message.assistant(
          text: response['response'] ?? 'Aucune réponse reçue',
          sqlQuery: response['sql_query'],
          graphBase64: response['data']?['graph'] as String?,
          // timestamp: DateTime.now(), // Retiré si non supporté
        ),
      );
    });
    _scrollToBottom();
  }

  void _handleApiError(ApiException e) {
    debugPrint('ApiException: ${e.message} (Code: ${e.statusCode})');
    
    String errorMessage;
    switch (e.statusCode) {
      case 422:
        errorMessage = 'Question incomplète ou mal formulée. Reformulez svp.';
        break;
      case 401:
        errorMessage = 'Session expirée. Veuillez vous reconnecter.';
        _showSessionExpiredSnackbar();
        break;
      case 500:
        errorMessage = 'Erreur serveur. Contactez l\'administrateur.';
        break;
      default:
        errorMessage = 'Erreur: ${e.message}';
    }

    setState(() {
      _messages.removeLast();
      _messages.add(Message.error(
        text: errorMessage,
        // timestamp: DateTime.now(), // Retiré si non supporté
      ));
    });
  }

  void _handleGenericError(dynamic error) {
    debugPrint('Erreur: $error');
    
    final errorMessage = error is TimeoutException
        ? 'Temps d\'attente dépassé'
        : 'Erreur de connexion au serveur';

    setState(() {
      _messages.removeLast();
      _messages.add(Message.error(
        text: errorMessage,
        // timestamp: DateTime.now(), // Retiré si non supporté
      ));
    });
  }

  void _showSessionExpiredSnackbar() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Session expirée. Veuillez vous reconnecter.'),
        backgroundColor: Colors.orange,
      ),
    );
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
        content: const Text('Voulez-vous vraiment effacer cette conversation ?'),
        actions: [
          TextButton(
            onPressed: Navigator.of(context).pop,
            child: const Text('Annuler'),
          ),
          TextButton(
            onPressed: () {
              Navigator.of(context).pop();
              setState(() => _messages.clear());
              _addWelcomeMessage();
            },
            child: const Text('Effacer', style: TextStyle(color: Colors.red)),
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
        child: Column(
          children: [
            if (_isLoading) _buildLoadingIndicator(),
            Expanded(child: _buildMessageList()),
            _buildMessageInput(),
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
            AppConstants.primaryColor.withAlpha(20), // Remplace withOpacity
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
                horizontal: AppConstants.paddingMedium,
                vertical: AppConstants.paddingSmall,
              ),
              itemCount: _messages.length,
              itemBuilder: (context, index) => MessageBubble(
                message: _messages[index],
                isMe: _messages[index].isMe,
              ),
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
            'Posez votre question sur le système scolaire',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Colors.grey.shade500,
                ),
          ),
        ],
      ),
    );
  }

  Widget _buildMessageInput() {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppConstants.paddingMedium,
        vertical: AppConstants.paddingSmall,
      ),
      decoration: BoxDecoration(
        color: Theme.of(context).scaffoldBackgroundColor,
        border: Border(top: BorderSide(color: Colors.grey.shade300)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withAlpha(25), // Remplace withOpacity
            blurRadius: 12,
            offset: const Offset(0, -4),
          ),
        ],
      ),
      child: SafeArea(
        child: Column(
          children: [
            if (_messages.length <= 1) _buildQuickSuggestions(),
            Row(
              children: [
                Expanded(child: _buildTextField()),
                const SizedBox(width: AppConstants.paddingSmall),
                _buildSendButton(),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildQuickSuggestions() {
    const suggestions = [
      'élèves', 'classes', 'enseignants', 
      'parents', 'effectifs', 'statistiques'
    ];

    return Container(
      margin: const EdgeInsets.only(bottom: AppConstants.paddingMedium),
      padding: const EdgeInsets.all(AppConstants.paddingSmall),
      decoration: BoxDecoration(
        color: AppConstants.primaryColor.withAlpha(20), // Remplace withOpacity
        borderRadius: BorderRadius.circular(AppConstants.radiusLarge),
      ),
      child: Wrap(
        spacing: 8,
        runSpacing: 6,
        children: suggestions.map(_buildQuickButton).toList(),
      ),
    );
  }

  Widget _buildTextField() {
    return TextField(
      controller: _messageController,
      decoration: InputDecoration(
        hintText: 'Posez votre question... Ex: "Nombre d\'élèves en CP"',
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(30), // Remplace radiusExtraLarge
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
                icon: const Icon(Icons.clear, size: 20),
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
        gradient: _isLoading
            ? LinearGradient(colors: [Colors.grey.shade400, Colors.grey.shade600])
            : LinearGradient( // Remplace primaryGradient
                colors: [AppConstants.primaryColor, AppConstants.primaryColorDark],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
      ),
      child: IconButton(
        icon: _isLoading
            ? const SizedBox(
                width: 24,
                height: 24,
                child: CircularProgressIndicator(
                  strokeWidth: 3,
                  valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                ),
              )
            : const Icon(Icons.send_rounded, color: Colors.white),
        onPressed: _isLoading ? null : _sendMessage,
      ),
    );
  }

  Widget _buildQuickButton(String text) {
    return InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: () {
        _messageController.text = text;
        _sendMessage();
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: AppConstants.primaryColor.withAlpha(38), // Remplace withOpacity(0.15)
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: AppConstants.primaryColor.withAlpha(64), // Remplace withOpacity(0.25)
            width: 1,
          ),
        ),
        child: Text(
          text,
          style: TextStyle(
            color: AppConstants.primaryColor,
            fontSize: 13,
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
        title: const Text('À propos'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Assistant scolaire - Version ${AppConstants.appVersion}',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: AppConstants.paddingMedium),
            Consumer<AuthService>(
              builder: (context, authService, _) => Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (authService.user != null) ...[
                    Text('Utilisateur: ${authService.user!.idpersonne}'),
                    if (authService.user!.roles.isNotEmpty)
                      Text('Rôles: ${authService.user!.roles.join(", ")}'),
                    const SizedBox(height: AppConstants.paddingSmall),
                  ],
                  Text(
                    // Retiré lastLogin si non disponible
                    'Connecté depuis: ${DateTime.now().toString()}',
                    style: TextStyle(color: Colors.grey.shade600, fontSize: 13),
                  ),
                ],
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
