import 'package:flutter/material.dart';
import '../models/message_model.dart';

class MessageBubble extends StatelessWidget {
  final Message message;
  final bool isMe;

  const MessageBubble({
    super.key,
    required this.message,
    required this.isMe,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 4, horizontal: 8),
      child: Row(
        mainAxisAlignment: isMe ? MainAxisAlignment.end : MainAxisAlignment.start,
        children: [
          if (!isMe) _buildAvatar(),
          Flexible(
            child: Container(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.75,
              ),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              decoration: BoxDecoration(
                color: isMe ? Colors.blue : Colors.grey[200],
                borderRadius: BorderRadius.circular(20),
              ),
              child: message.isTyping 
                  ? _buildTypingIndicator()
                  : Text(
                      message.text,
                      style: TextStyle(
                        color: isMe ? Colors.white : Colors.black87,
                        fontSize: 16,
                      ),
                    ),
            ),
          ),
          if (isMe) _buildAvatar(),
        ],
      ),
    );
  }

  Widget _buildAvatar() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 8),
      child: CircleAvatar(
        radius: 16,
        backgroundColor: isMe ? Colors.blue : Colors.grey,
        child: Icon(
          isMe ? Icons.person : Icons.smart_toy,
          size: 18,
          color: Colors.white,
        ),
      ),
    );
  }

  Widget _buildTypingIndicator() {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        for (int i = 0; i < 3; i++)
          Container(
            margin: EdgeInsets.only(right: i < 2 ? 4 : 0),
            child: const SizedBox(
              width: 8,
              height: 8,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                valueColor: AlwaysStoppedAnimation<Color>(Colors.grey),
              ),
            ),
          ),
      ],
    );
  }
}