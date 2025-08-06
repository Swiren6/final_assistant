

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
import logging
import traceback
from config.database import init_db, get_db, get_db_connection
import os
import re
from agent.assistant import SQLAssistant
from langchain_community.utilities import SQLDatabase
from agent.pdf_utils.attestation import export_attestation_pdf
from agent.sql_agent import SQLAgent 


agent_bp = Blueprint('agent_bp', __name__)
logger = logging.getLogger(__name__)

engine = SQLAgent(get_db_connection())

# Initialisation assistant avec gestion d'erreurs
assistant = None


def initialize_assistant():
    global assistant
    db = get_db_connection()
    try:
       
        assistant = SQLAssistant(db) 
        required_vars = ['MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_HOST', 'MYSQL_DATABASE', 'TOGETHER_API_KEY']
        missing = [var for var in required_vars if not os.getenv(var)]
        
        if missing:
            print(f"❌ Variables manquantes: {missing}")
            return False
        
        # Utiliser SQLDatabase de langchain
        db_uri = f"mysql://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}@{os.getenv('MYSQL_HOST')}/{os.getenv('MYSQL_DATABASE')}"
        db = SQLDatabase.from_uri(db_uri)
        
        assistant = SQLAssistant(db)
        print("✅ Assistant initialisé avec succès")
        return True
        
    except Exception as e:
        print(f"❌ Erreur initialisation: {e}")
        traceback.print_exc()  # ✅ AJOUT pour debug
        return False

@agent_bp.route('/ask', methods=['POST'])
def ask_sql():
    """Endpoint principal avec gestion d'erreurs robuste"""
    
    # Gestion JWT optionnelle
    jwt_valid = False
    current_user = None
    
    try:
        if 'Authorization' in request.headers:
            verify_jwt_in_request(optional=True)
            current_user = get_jwt_identity()
            jwt_valid = True
    except Exception:
        pass  
    
    try:
        # Validation JSON
        if not request.is_json:
            return jsonify({"error": "Content-Type application/json requis"}), 415
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Corps de requête JSON vide"}), 400
        
        # Extraction de la question
        question = None
        possible_fields = ['question', 'subject', 'query', 'text', 'message', 'prompt']
        
        for field in possible_fields:
            if field in data and data[field] and str(data[field]).strip():
                question = str(data[field]).strip()
                break
        
        if not question:
            return jsonify({
                "error": "Question manquante",
                "expected_fields": possible_fields,
                "received_fields": list(data.keys())
            }), 422
        
        # Vérification assistant
        if not assistant:
            # Tentative de réinitialisation
            if not initialize_assistant():
                return jsonify({
                    "error": "Assistant non disponible",
                    "details": "Impossible d'initialiser l'assistant IA"
                }), 503
        
        # Gestion spécifique pour génération d'attestation
        if "attestation" in question.lower():
            name_match = re.search(
                r"(?:attestation\s+(?:de|pour)\s+)([A-Za-zÀ-ÿ\s\-\']+)", 
                question, 
                re.IGNORECASE
            )
            
            if not name_match:
                return jsonify({
                    "response": "Veuillez spécifier un nom (ex: 'attestation de Nom Prénom')"
                })

            full_name = name_match.group(1).strip()
            
            if not validate_name(full_name):
                return jsonify({
                    "response": "Format de nom invalide. Utilisez uniquement des lettres et espaces"
                })
            print(f"Recherche élève pour nom complet : {full_name}")

            # Récupération des données
            student_data = engine.get_student_info_by_name(full_name)
            
            print(f"Résultat de recherche: {student_data}")
            
            if not student_data:
                return jsonify({
                    "response": f"Aucun élève trouvé avec le nom '{full_name}'"
                })

            # Harmoniser les champs pour le PDF
            student_data['nom_complet'] = student_data.get('nom_complet')
            student_data['lieu_naissance'] = student_data.get('lieu_de_naissance')
            student_data['annee_scolaire'] = "2024/2025"

            # Génération du PDF
            try:
                result = export_attestation_pdf(student_data)
                
                if result.get("status") != "success":
                    return jsonify({
                        "response": "Erreur lors de la génération du PDF"
                    }), 500

                filename = result["filename"]

                return jsonify({
                    "response": (
                        f"✅ Attestation générée pour {student_data['nom_complet']}\n\n"
                        f"<a href='/static/attestations/{filename}' download>Télécharger</a>"
                    ),
                    "pdf_url": f"/static/attestations/{filename}"
                })

            except Exception as e:
                logger.error(f"Erreur génération PDF: {str(e)}")
                return jsonify({
                    "response": "Erreur lors de la génération du document"
                })

        # Si pas attestation, on traite la question SQL classique
        try:
            sql_query, response = assistant.ask_question(question)

            # Exécution de la requête SQL
            try:
                rows = engine.execute_natural_query(sql_query)  # Doit retourner List[Dict]
            except Exception as e:
                logger.error(f"Erreur d'exécution SQL : {e}")
                return jsonify({
                    "error": "Erreur d'exécution SQL",
                    "sql_query": sql_query,
                    "details": str(e)
                }), 500

            result = {
                "sql_query": sql_query,
                "response": response,
                "status": "success",
                "question": question,
                "data": rows
            }
            if jwt_valid:
                result["user"] = current_user

            return jsonify(result), 200
        
        except Exception as processing_error:
            logger.error(f"Erreur traitement: {processing_error}")
            return jsonify({
                "error": "Erreur de traitement",
                "details": str(processing_error),
                "question": question
            }), 500
    
    except Exception as e:
        logger.error(f"Erreur générale: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": "Erreur serveur interne",
            "details": str(e)
        }), 500

def validate_name(full_name):
    """Valide le format du nom"""
    return bool(re.match(r'^[A-Za-zÀ-ÿ\s\-\']{3,50}$', full_name))

def validate_name(full_name):
    """Valide le format du nom"""
    return bool(re.match(r'^[A-Za-zÀ-ÿ\s\-\']{3,50}$', full_name))
@agent_bp.route('/ask', methods=['GET'])
def ask_info():
    """Information sur l'endpoint"""
    return jsonify({
        "message": "Assistant IA pour questions scolaires",
        "method": "POST",
        "format": {"question": "Votre question ici"},
        "status": "OK" if assistant else "ERROR",
        "assistant_available": assistant is not None
    })

@agent_bp.route('/health', methods=['GET'])
def health():
    """Vérification de santé détaillée"""
    health_status = {
        "status": "OK",
        "assistant": "OK" if assistant else "ERROR",
        "database": "OK" if assistant and assistant.db else "ERROR",
        "timestamp": "2024-01-01T00:00:00Z"  # Vous pouvez ajouter datetime.utcnow().isoformat()
    }
    
    status_code = 200 if assistant else 503
    return jsonify(health_status), status_code

@agent_bp.route('/reinit', methods=['POST'])
def reinitialize():
    """Endpoint pour réinitialiser l'assistant"""
    try:
        success = initialize_assistant()
        return jsonify({
            "success": success,
            "message": "Réinitialisation réussie" if success else "Échec de la réinitialisation"
        }), 200 if success else 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
        
@agent_bp.route('/bulletin', methods=['POST'])
def generate_bulletin():
    try:
        data = request.get_json()
        if not data or "nom" not in data:
            return jsonify({"error": "Le champ 'nom' est requis"}), 400
        
        full_name = data["nom"]
        trimestre_id = data.get("trimestre_id", 31)  # Par défaut T1
        annee_scolaire = data.get("annee_scolaire", "2024/2025")

        student = engine.get_student_info_by_name(full_name)
        if not student:
            return jsonify({"error": f"Aucun élève trouvé pour '{full_name}'"}), 404

        student_id = student.get("matricule")
        if not student_id:
            return jsonify({"error": "ID élève manquant"}), 400

        from agent.pdf_utils.bulletin import export_bulletin_pdf
        result = export_bulletin_pdf(student_id, trimestre_id, annee_scolaire)

        if result["status"] != "success":
            return jsonify({"error": result.get("message", "Erreur inconnue")}), 500

        return jsonify({
            "response": f"✅ Bulletin généré pour {full_name}",
            "pdf_url": f"/static/bulletins/{result['filename']}"
        })

    except Exception as e:
        logger.error(f"Erreur génération bulletin: {str(e)}")
        return jsonify({"error": "Erreur serveur"}), 500


@agent_bp.route('/debug', methods=['GET'])
def debug():
    try:
        db = get_db_connection()
        return jsonify({
            "db_connection": "OK" if db else "FAILED",
            "SQLAssistant_import": "OK",
            "env_vars": {
                "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
                "DB_CONNECTION": bool(os.getenv("DB_HOST"))
            }
        })
    except Exception as e:
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500