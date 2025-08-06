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
import 'dart:convert';

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
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _addWelcomeMessage();
  }

  void _addWelcomeMessage() {
    setState(() {
      _messages.add(
        Message.assistant(
          text: AppConstants.defaultWelcomeMessage,
        ),
      );
    });
  }
  
Future<void> _sendMessage() async {
  if (_messageController.text.trim().isEmpty || _isLoading) return;

  final userMessage = _messageController.text.trim();
  _messageController.clear();

  setState(() {
    _messages.add(Message.user(text: userMessage));
    _messages.add(Message.typing());
    _isLoading = true;
  });
  _scrollToBottom();

  try {
    final authService = Provider.of<AuthService>(context, listen: false);
    
    final token = authService.token ?? '';
    
    print('🔑 Token présent: ${token.isNotEmpty}');
    print('💬 Envoi de la question: $userMessage');

    final response = await _apiService.askQuestion(userMessage, token);

    setState(() {
      _messages.removeLast();
      _messages.add(
        Message.assistant(
          text: response['response'] ?? 'Aucune réponse reçue',
          sqlQuery: response['sql_query'],
        ),
      );
      _isLoading = false;
    });

  } on ApiException catch (e) {
    print('❌ ApiException: ${e.message} (Code: ${e.statusCode})');

    setState(() {
      _messages.removeLast();

      String errorMessage;
      switch (e.statusCode) {
        case 422:
          if (e.message.toLowerCase().contains('subject') ||
              e.message.toLowerCase().contains('question')) {
            errorMessage =
                'Hmm, je n\'ai pas bien compris votre question. Pouvez-vous essayer de reformuler ?';
          } else {
            errorMessage =
                'Question trop courte ou mal comprise. ';
          }
          break;
        case 401:
          errorMessage = 'Session expirée. Veuillez vous reconnecter.';
          break;
        case 503:
          errorMessage =
              'Service temporairement indisponible. Veuillez réessayer dans quelques instants.';
          break;
        case 500:
          errorMessage =
              'Erreur serveur. Si le problème persiste, contactez l\'administrateur.';
          break;
        default:
          errorMessage =
              'Une erreur s\'est produite. Essayez de reformuler votre question.';
      }

      _messages.add(Message.error(text: errorMessage));
      _isLoading = false;
    });

    if (e.statusCode == 401) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Session expirée. Veuillez vous reconnecter.'),
          backgroundColor: Colors.orange,
        ),
      );
    }
  }
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
      builder: (BuildContext context) {
        return AlertDialog(
          title: const Text('Effacer la conversation'),
          content: const Text(
              'Êtes-vous sûr de vouloir effacer toute la conversation ?'),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Annuler'),
            ),
            TextButton(
              onPressed: () {
                Navigator.of(context).pop();
                setState(() {
                  _messages.clear();
                });
                _addWelcomeMessage();
              },
              child: const Text('Effacer'),
            ),
          ],
        );
      },
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
            onPressed: () => _showInfoDialog(),
            tooltip: 'Informations',
          ),
        ],
      ),
      drawer: const SidebarMenu(),
      body: SafeArea(
        // Ajout de SafeArea pour éviter l'overflow
        child: Column(
          children: [
            if (_isLoading)
              const LinearProgressIndicator(
                backgroundColor: Colors.transparent,
                valueColor:
                    AlwaysStoppedAnimation<Color>(AppConstants.primaryColor),
              ),
            Expanded(
              child: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [
                      AppConstants.primaryColor.withOpacity(0.05),
                      Colors.transparent,
                    ],
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
                          return MessageBubble(
                            message: message,
                            isMe: message.isMe,
                          );
                        },
                      ),
              ),
            ),
            _buildMessageInput(),
          ],
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

  // Dans votre chat_screen.dart, modifiez le _buildMessageInput pour encourager les questions courtes :

  Widget _buildMessageInput() {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppConstants.paddingMedium,
        vertical: AppConstants.paddingMedium,
      ),
      decoration: BoxDecoration(
        color: Theme.of(context).scaffoldBackgroundColor,
        border: Border(
          top: BorderSide(
            color: Colors.grey.shade300,
            width: 0.5,
          ),
        ),
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
            // ✅ AJOUT de suggestions pour encourager les questions courtes
            if (_messages.length <= 1) // Afficher seulement au début
              Container(
                margin:
                    const EdgeInsets.only(bottom: AppConstants.paddingMedium),
                padding: const EdgeInsets.all(AppConstants.paddingSmall),
                decoration: BoxDecoration(
                  color: AppConstants.primaryColor.withOpacity(0.1),
                  borderRadius:
                      BorderRadius.circular(AppConstants.radiusMedium),
                ),
                child: Wrap(
                  spacing: 8,
                  children: [
                    _buildQuickButton('élèves'),
                    _buildQuickButton('classes'),
                    _buildQuickButton('enseignants'),
                    _buildQuickButton('parents'),
                    _buildQuickButton('nombre élèves'),
                  ],
                ),
              ),

            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _messageController,
                    decoration: InputDecoration(
                      // ✅ Nouveau placeholder plus encourageant
                      hintText:
                          'Tapez votre question... Même courte ! Ex: "élèves", "classes"',
                      border: OutlineInputBorder(
                        borderRadius:
                            BorderRadius.circular(AppConstants.radiusRound),
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
                  ),
                ),
                const SizedBox(width: AppConstants.paddingSmall),
                Container(
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: LinearGradient(
                      colors: _isLoading
                          ? [Colors.grey.shade400, Colors.grey.shade500]
                          : [
                              AppConstants.primaryColor,
                              AppConstants.primaryColorDark
                            ],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                  ),
                  child: IconButton(
                    icon: _isLoading
                        ? SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              valueColor:
                                  AlwaysStoppedAnimation<Color>(Colors.white),
                            ),
                          )
                        : const Icon(Icons.send, color: Colors.white),
                    onPressed: _isLoading ? null : _sendMessage,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

// ✅ NOUVELLE méthode pour les boutons de suggestion rapide
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
          border: Border.all(
            color: AppConstants.primaryColor.withOpacity(0.3),
          ),
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
      builder: (BuildContext context) {
        return AlertDialog(
          title: const Text('Assistant Scolaire'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                  'Cet assistant peut répondre à vos questions sur le système scolaire.'),
              const SizedBox(height: AppConstants.paddingMedium),
              Consumer<AuthService>(
                builder: (context, authService, child) {
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                          'Utilisateur: ${authService.user?.idpersonne ?? "Non connecté"}'),
                      if (authService.user?.roles.isNotEmpty ?? false)
                        Text('Rôles: ${authService.user!.roles.join(", ")}'),
                    ],
                  );
                },
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Fermer'),
            ),
          ],
        );
      },
    );
  }

  @override
  void dispose() {
    _messageController.dispose();
    _scrollController.dispose();
    super.dispose();
  }
}
