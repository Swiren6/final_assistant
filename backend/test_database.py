
#!/usr/bin/env python3
"""
Script de test pour la base de données db
"""
import os
import db.connector
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

def test_db_connection():
    """Test la connexion db"""
    config = {
        'host': os.getenv('db_HOST', 'localhost'),
        'port': int(os.getenv('db_PORT', '3306')),
        'user': os.getenv('db_USER', 'root'),
        'password': os.getenv('db_PASSWORD', 'root'),
        'database': os.getenv('db_DATABASE', 'bd_eduise2'),
        'charset': 'utf8mb4',
        'use_unicode': True
    }
    
    print("🔍 Test de connexion db...")
    print(f"Host: {config['host']}:{config['port']}")
    print(f"User: {config['user']}")
    print(f"Database: {config['database']}")
    
    try:
        # Test de connexion
        conn = db.connector.connect(**config)
        print("✅ Connexion db réussie!")
        
        # Test des tables disponibles
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES;")
        tables = cursor.fetchall()
        
        print(f"\n📋 Tables disponibles ({len(tables)}):")
        for table in tables:
            print(f"  - {table[0]}")
        
        # Test de quelques requêtes basiques
        test_queries = [
            "SELECT COUNT(*) as total FROM user;",
            "SELECT COUNT(*) as total FROM personne;",
            "SELECT COUNT(*) as total FROM eleve;",
        ]
        
        print("\n🧪 Test de requêtes basiques:")
        for query in test_queries:
            try:
                cursor.execute(query)
                result = cursor.fetchone()
                table_name = query.split("FROM ")[1].split(";")[0].strip()
                print(f"  ✅ {table_name}: {result[0] if result else 0} enregistrements")
            except Exception as e:
                table_name = query.split("FROM ")[1].split(";")[0].strip()
                print(f"  ❌ {table_name}: {str(e)}")
        
        # Test de la structure d'une table importante
        print("\n🔍 Structure de la table 'user':")
        try:
            cursor.execute("DESCRIBE user;")
            columns = cursor.fetchall()
            for col in columns:
                print(f"  - {col[0]} ({col[1]})")
        except Exception as e:
            print(f"  ❌ Erreur: {str(e)}")
        
        cursor.close()
        conn.close()
        return True
        
    except db.connector.Error as e:
        print(f"❌ Erreur db: {e}")
        print("\n💡 Solutions possibles:")
        print("1. Vérifiez que db est démarré")
        print("2. Vérifiez les paramètres dans le fichier .env")
        print("3. Vérifiez que la base de données 'bd_eduise2' existe")
        print("4. Vérifiez les permissions de l'utilisateur 'root'")
        return False
    except Exception as e:
        print(f"❌ Erreur générale: {e}")
        return False

def test_env_variables():
    """Test les variables d'environnement"""
    print("⚙️ Test des variables d'environnement:")
    
    required_vars = [
        'db_HOST',
        'db_USER', 
        'db_PASSWORD',
        'db_DATABASE',
        'db_PORT'
    ]
    
    
    
    optional_vars = [
        'JWT_SECRET_KEY'    ]
    
    all_good = True
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Masquer les mots de passe
            display_value = "*" * len(value) if 'PASSWORD' in var else value
            print(f"  ✅ {var} = {display_value}")
        else:
            print(f"  ❌ {var} = NON DÉFINIE")
            all_good = False
    
    print("\n🔧 Variables optionnelles:")
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            display_value = f"{value[:10]}..." if len(value) > 10 else value
            print(f"  ✅ {var} = {display_value}")
        else:
            print(f"  ⚠️ {var} = NON DÉFINIE (optionnel)")
    
    return all_good

def main():
    print("🚀 Test de la configuration Assistant Scolaire\n")
    
    # Test des variables d'environnement
    env_ok = test_env_variables()
    print("\n" + "="*50 + "\n")
    
    if env_ok:
        # Test de la base de données
        db_ok = test_db_connection()
        
        if db_ok:
            print("\n🎉 Tous les tests sont passés!")
            print("Vous pouvez maintenant lancer l'application avec: python app.py")
        else:
            print("\n⚠️ Problème avec la base de données")
    else:
        print("\n❌ Veuillez corriger les variables d'environnement manquantes")

if __name__ == "__main__":
    main()