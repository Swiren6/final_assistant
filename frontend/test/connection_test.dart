// test/connection_test.dart
// import 'package:frontend/services/api_service.dart';
import '../lib/services/api_service.dart';

class ConnectionTest {
  static final ApiService _apiService = ApiService();

  static Future<void> runAllTests() async {
    print('🔄 Démarrage des tests de connectivité...\n');

    await testHealthEndpoint();
    await testAskQuestion();
  }

  static Future<void> testHealthEndpoint() async {
    print('🏥 Test de l\'endpoint /health...');
    try {
      final isConnected = await _apiService.testConnection();
      if (isConnected == true) {
        print('✅ Endpoint /health : OK');
      } else {
        print('❌ Endpoint /health : Échec');
      }
    } catch (e) {
      print('❌ Erreur /health : $e');
    }
    print('');
  }

  

  static Future<void> testAskQuestion() async {
    print('🤖 Test d\'une question...');
    try {
      final response = await _apiService.askQuestion(
          'Combien d\'élèves sont inscrits cette année?',
          '' // Sans token pour le test
          );
      print('✅ Question test réussie :');
      print('   SQL: ${response.sqlQuery}');
      print('   Réponse: ${response.response}');
    } catch (e) {
      print('❌ Erreur question test : $e');
    }
    print('');
  }
}

// Pour exécuter le test depuis votre app
void main() async {
  await ConnectionTest.runAllTests();
}
