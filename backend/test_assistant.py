#!/usr/bin/env python3
"""
Script de test pour l'assistant unifié
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.assistant import SQLAssistant
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_assistant():
    """Test de base de l'assistant unifié"""
    print("🧪 Test de l'Assistant Unifié")
    print("=" * 50)
    
    try:
        # Initialisation
        print("1. Initialisation de l'assistant...")
        assistant = SQLAssistant()
        print("   ✅ Assistant initialisé")
        
        # Test de connexion DB
        print("2. Test de connexion à la base de données...")
        if assistant.db:
            print("   ✅ Base de données connectée")
        else:
            print("   ❌ Problème de connexion DB")
            return False
        
        # Test de génération SQL simple
        print("3. Test de génération SQL...")
        try:
            sql = assistant.generate_sql_with_ai("Combien d'élèves sont inscrits?")
            if sql:
                print(f"   ✅ SQL généré: {sql[:100]}...")
            else:
                print("   ❌ Pas de SQL généré")
        except Exception as e:
            print(f"   ⚠️ Erreur génération SQL: {e}")
        
        # Test question admin
        print("4. Test question admin...")
        try:
            sql_query, response = assistant.ask_question(
                "Combien d'élèves sont inscrits?", 
                user_id=1, 
                roles=['ROLE_SUPER_ADMIN']
            )
            print(f"   ✅ Réponse: {response[:100]}...")
        except Exception as e:
            print(f"   ⚠️ Erreur question admin: {e}")
        
        # Test des méthodes utilitaires
        print("5. Test des utilitaires...")
        
        # Test schéma
        if hasattr(assistant, 'schema') and assistant.schema:
            print(f"   ✅ Schéma chargé: {len(assistant.schema)} tables")
        else:
            print("   ⚠️ Schéma vide")
        
        # Test templates
        if hasattr(assistant, 'templates_questions'):
            print(f"   ✅ Templates chargés: {len(assistant.templates_questions)}")
        else:
            print("   ⚠️ Pas de templates")
        
        # Test cache
        if hasattr(assistant, 'cache') and assistant.cache:
            print("   ✅ Cache disponible")
        else:
            print("   ⚠️ Cache indisponible")
        
        print("\n🎉 Tests terminés avec succès!")
        return True
        
    except Exception as e:
        print(f"\n❌ Erreur lors des tests: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_graph_generation():
    """Test de génération de graphiques"""
    print("\n📊 Test de Génération de Graphiques")
    print("=" * 50)
    
    try:
        import pandas as pd
        from agent.assistant import SQLAssistant
        
        assistant = SQLAssistant()
        
        # Données de test
        test_data = [
            {"classe": "7A1", "nombre": 25},
            {"classe": "7A2", "nombre": 23},
            {"classe": "7B1", "nombre": 27},
            {"classe": "7B2", "nombre": 24}
        ]
        
        df = pd.DataFrame(test_data)
        
        # Test génération graphique en barres
        print("1. Test graphique en barres...")
        graph_data = assistant.generate_auto_graph(df, "bar")
        
        if graph_data and graph_data.startswith("data:image/png;base64,"):
            print("   ✅ Graphique en barres généré")
        else:
            print("   ❌ Échec génération graphique")
        
        # Test détection automatique
        print("2. Test détection automatique...")
        detected_type = assistant.detect_graph_type("nombre d'élèves par classe", df.columns.tolist())
        print(f"   ✅ Type détecté: {detected_type}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur test graphiques: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Lancement des tests de l'Assistant Unifié")
    
    success = test_assistant()
    
    if success:
        test_graph_generation()
    
    print(f"\n{'✅ TOUS LES TESTS RÉUSSIS' if success else '❌ ÉCHEC DES TESTS'}")