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

  void _handleSuccessfulResponse(Map<String, dynamic> response) {
    setState(() {
      _messages.removeLast();
      _messages.add(
        Message.assistant(
          text: response['response'] ?? 'Aucune réponse reçue',
          sqlQuery: response['sql_query'],
          graphBase64: response['data']?['graph'] as String?,
        ),
      );
    });
    _scrollToBottom();
  }

  void _handleErrorResponse(dynamic error) {
    debugPrint('Erreur: $error');
    setState(() {
      _messages.removeLast();
      _messages.add(Message.error(text: _getErrorMessage(error)));
    });
  }

  String _getErrorMessage(dynamic error) {
    if (error is http.ClientException) return 'Erreur de connexion';
    if (error is TimeoutException) return 'Temps d\'attente dépassé';
    return 'Une erreur est survenue';
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
              setState(() => _messages.clear());
              _addWelcomeMessage();
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
            'Posez une question sur le système scolaire',
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
      child: Wrap(
        spacing: 8,
        children: [
          'élèves', 'classes', 'enseignants', 'parents', 'nombre élèves'
        ].map((text) => _buildQuickButton(text)).toList(),
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
        hintText: 'Tapez votre question... Même courte ! Ex: "élèves", "classes"',
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
          colors: _isLoading
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
        onPressed: _isLoading ? null : _sendMessage,
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
        title: const Text('Assistant Scolaire'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Cet assistant peut répondre à vos questions sur le système scolaire.'),
            const SizedBox(height: AppConstants.paddingMedium),
            Consumer<AuthService>(
              builder: (context, authService, _) => Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Utilisateur: ${authService.user?.idpersonne ?? "Non connecté"}'),
                  if (authService.user?.roles.isNotEmpty ?? false)
                    Text('Rôles: ${authService.user!.roles.join(", ")}'),
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
