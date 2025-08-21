#!/usr/bin/env python3
"""
Script d'installation des dépendances pour Assistant Scolaire
"""
import subprocess
import sys
import os

def run_command(command, description=""):
    """Exécute une commande avec gestion d'erreur"""
    print(f"🔧 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, 
                              capture_output=True, text=True)
        print(f"✅ {description} - Succès")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - Erreur: {e.stderr}")
        return False

# Mettre à jour les versions dans install_basic_requirements():
def install_basic_requirements():
    basic_packages = [
        # Flask core
        "flask==3.1.1",  # Mise à jour version
        "flask-jwt-extended==4.7.1",
        "flask-cors==6.0.1",
        
        # DB + ORM
        "mysql-connector-python==9.4.0",
        "PyMySQL==1.1.1",
        "SQLAlchemy==2.0.42",
        
        # Config et logs
        "python-dotenv==1.1.1",
        "colorlog==6.8.0",
        
        # PDF et texte arabe
        "fpdf2==2.7.4",
        "arabic-reshaper==3.0.0",
        "python-bidi==0.6.6"
    ]
def install_extended_requirements():
    """Installation des dépendances supplémentaires"""
    extended_packages = [
        # Analyse et Data
        "pandas",
        "matplotlib",
        "tabulate",

        # API alternative (FastAPI)
        "fastapi",
        "uvicorn",

        # Validation
        "pydantic>=2.0"
    ]

    print("\n📦 Installation des packages supplémentaires...")
    for package in extended_packages:
        run_command(f"pip install {package}", f"Installation de {package}")

def install_optional_requirements():
    """Installation des dépendances optionnelles IA / LLM"""
    optional_packages = [
        ("tiktoken", "Tokenizer OpenAI"), 
        ("langchain", "Framework Langchain"),
        ("langchain-community", "Langchain Community"),
        ("openai", "Client OpenAI")
    ]
    
    print("\n📦 Installation des packages IA optionnels...")
    for package, description in optional_packages:
        run_command(f"pip install {package}", f"{description}")

def create_env_template():
    """Crée un template .env si inexistant"""
    env_file = ".env"
    if not os.path.exists(env_file):
        env_template = """# Configuration MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=assistant_scolaire

# Configuration JWT
JWT_SECRET_KEY=your-super-secret-jwt-key-change-this


# Configuration OpenAI (optionnel) 
OPENAI_API_KEY=your-openai-api-key
"""
        try:
            with open(env_file, 'w') as f:
                f.write(env_template)
            print(f"✅ Fichier {env_file} créé - Veuillez le configurer!")
        except Exception as e:
            print(f"❌ Erreur création {env_file}: {e}")

def test_imports():
    """Test les imports principaux"""
    print("\n🧪 Test des imports essentiels...")

    imports_to_test = [
        ("flask", "Flask"),
        ("mysql.connector", "MySQL Connector"),
        ("dotenv", "Python Dotenv"),
        ("flask_jwt_extended", "Flask JWT Extended"),
        ("flask_cors", "Flask CORS"),
        ("pandas", "Pandas"),
        ("matplotlib", "Matplotlib"),
        ("tabulate", "Tabulate"),
        ("pydantic", "Pydantic"),
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn")
    ]
    
    success_count = 0
    for module, name in imports_to_test:
        try:
            __import__(module)
            print(f"✅ {name} - OK")
            success_count += 1
        except ImportError:
            print(f"❌ {name} - Manquant")

    # Test imports IA optionnels
    print("\n🔍 Test des imports IA optionnels...")
    optional_imports = [
        ("tiktoken", "Tiktoken"),
        ("langchain", "Langchain"),
        ("openai", "OpenAI")
    ]
    
    for module, name in optional_imports:
        try:
            __import__(module)
            print(f"✅ {name} - Disponible")
        except ImportError:
            print(f"⚠️ {name} - Non disponible (optionnel)")

    print(f"\n📊 Résultat: {success_count}/{len(imports_to_test)} imports essentiels réussis")
    return success_count == len(imports_to_test)

def main():
    print("🚀 Installation des dépendances Assistant Scolaire\n")
    
    # Mise à jour pip
    run_command("python -m pip install --upgrade pip", "Mise à jour pip")
    
    # Installation des dépendances
    print("\n📦 Étape 1: Dépendances essentielles...")
    install_basic_requirements()
    
    print("\n📦 Étape 2: Dépendances supplémentaires...")
    install_extended_requirements()
    
    print("\n📦 Étape 3: Dépendances IA optionnelles...")
    install_optional_requirements()
    
    # Fichier .env
    print("\n⚙️ Configuration...")
    create_env_template()
    
    # Test
    if test_imports():
        print("\n🎉 Installation terminée avec succès!")
        print("\n📋 Prochaines étapes:")
        print("1. Configurez le fichier .env avec vos paramètres")
        print("2. Créez votre base de données MySQL")
        print("3. Lancez l'application avec: python app.py")
    else:
        print("\n⚠️ Installation terminée avec des avertissements")
        print("Certaines dépendances peuvent manquer ou échouer")

if __name__ == "__main__":
    main()
