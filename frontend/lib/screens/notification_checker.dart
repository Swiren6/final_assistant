import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

class NotificationChecker extends StatefulWidget {
  const NotificationChecker({Key? key}) : super(key: key);

  @override
  State<NotificationChecker> createState() => _NotificationCheckerState();
}

class _NotificationCheckerState extends State<NotificationChecker> {
  final List<String> messages = [];
  final Set<int> seenNotificationIds = {};
  Timer? _timer;

  @override
  void initState() {
    super.initState();
   
    _timer = Timer.periodic(const Duration(seconds: 3000), (_) => fetchNotifications());
  }

  Future<void> fetchNotifications() async {
    try {
      final response = await http.get(Uri.parse('http://ton-backend/check_notifications'));
      if (response.statusCode == 200) {
        final List<dynamic> data = jsonDecode(response.body);
        for (var notif in data) {
          final int id = notif['id'];
          final String message = notif['message'];

          if (!seenNotificationIds.contains(id)) {
            setState(() {
              messages.add(message);
              seenNotificationIds.add(id);
            });
          }
        }
      } else {
        print('Erreur serveur : ${response.statusCode}');
      }
    } catch (e) {
      print('Erreur réseau : $e');
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Notifications')),
      body: ListView.builder(
        itemCount: messages.length,
        itemBuilder: (context, index) {
          // Ici tu peux customiser selon que ce soit message bot ou user
          return ListTile(
            leading: const Icon(Icons.notifications),
            title: Text(messages[index]),
          );
        },
      ),
    );
  }
}