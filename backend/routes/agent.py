from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request, get_jwt
import logging
import re
import os

from routes.auth import login
from services.auth_service import AuthService
from agent.assistant import SQLAssistant  # Import du nouvel assistant unifié
from agent.pdf_utils.attestation import PDFGenerator
from agent.pdf_utils.bulletin import export_bulletin_pdf

from config.database import init_db, get_db, get_db_connection

# Initialize PDF generator
generator = PDFGenerator()

def validate_name(name: str) -> bool:
    """Valide si un nom contient seulement des lettres, espaces, tirets et apostrophes"""
    if not name or not isinstance(name, str):
        return False
    
    # Pattern pour lettres (avec accents), espaces, tirets et apostrophes
    import re
    pattern = r'^[A-Za-zÀ-ÿ\s\-\']+$'
    
    # Vérifications supplémentaires
    name = name.strip()
    if len(name) < 2 or len(name) > 100:
        return False
    
    # Pas d'espaces multiples ou de caractères spéciaux en début/fin
    if re.search(r'\s{2,}|^[\s\-\']|[\s\-\']$', name):
        return False
    
    return bool(re.match(pattern, name))

# Initialize blueprint
agent_bp = Blueprint('agent_bp', __name__)
logger = logging.getLogger(__name__)

# Global assistant instance
unified_assistant = None

def initialize_unified_assistant():
    """Initialize the unified SQL assistant"""
    global unified_assistant
    try:
        unified_assistant = SQLAssistant()
        if unified_assistant and unified_assistant.db:
            logger.info("✅ Assistant unifié initialisé avec succès")
            return True
        else:
            logger.error("❌ Assistant initialisé mais DB manquante")
            return False
    except Exception as e:
        logger.error(f"❌ Erreur initialisation assistant unifié: {e}")
        unified_assistant = None
        return False

# Initialize at import
initialize_unified_assistant()

@agent_bp.route('/ask', methods=['POST'])
def ask_sql():
    """
    Route principale pour les questions SQL avec génération de graphiques
    Utilise le nouvel assistant unifié qui combine SQL + IA + graphiques
    """
    jwt_valid = False
    current_user = None
    jwt_error = None

    # 🔐 Authentification via JWT
    try:
        if 'Authorization' in request.headers:
            try:
                verify_jwt_in_request(optional=True)
                jwt_identity = get_jwt_identity()
                jwt_claims = get_jwt()

                logger.debug(f"JWT Identity: {jwt_identity}")
                logger.debug(f"JWT Claims: {jwt_claims}")

                if jwt_identity and jwt_claims:
                    current_user = {
                        'sub': jwt_identity,
                        'idpersonne': jwt_claims.get('idpersonne'),
                        'roles': jwt_claims.get('roles', []),
                        'username': jwt_claims.get('username', '')
                    }
                    jwt_valid = True

            except Exception as jwt_exc:
                jwt_error = str(jwt_exc)
                logger.debug(f"Erreur JWT: {jwt_error}")

    except Exception as e:
        jwt_error = str(e)
        logger.debug(f"Erreur générale JWT: {jwt_error}")

    # 🧠 Traitement de la question
    try:
        if not request.is_json:
            return jsonify({"error": "Content-Type application/json requis"}), 415

        data = request.get_json()
        if not data:
            return jsonify({"error": "Corps de requête JSON vide"}), 400

        # Extraction de la question avec fallback sur plusieurs champs
        question = next((str(data[field]).strip() for field in ['question', 'subject', 'query', 'text', 'message', 'prompt']
                         if field in data and data[field] and str(data[field]).strip()), None)

        if not question:
            return jsonify({
                "error": "Question manquante",
                "expected_fields": ['question', 'subject', 'query', 'text', 'message', 'prompt'],
                "received_fields": list(data.keys())
            }), 422

        # Extraction des informations utilisateur
        user_id = current_user.get('idpersonne') if current_user else None
        roles = current_user.get('roles', []) if current_user else []

        logger.debug(f"user_id: {user_id}, roles: {roles}")

        # Vérification de l'assistant
        if not unified_assistant:
            if not initialize_unified_assistant():
                return jsonify({
                    "error": "Assistant non disponible",
                    "details": "Impossible d'initialiser l'assistant IA"
                }), 503

        # 🧾 Cas spécial : Attestation de présence
        if "attestation" in question.lower():
            return handle_attestation_request(question)

        # 🧾 Cas spécial : Bulletin scolaire  
        if "bulletin" in question.lower():
            return handle_bulletin_request(question)

        # 🤖 Traitement IA principal avec l'assistant unifié
        try:
            sql_query, ai_response = unified_assistant.ask_question(question, user_id, roles)
            
            # Création de la réponse enrichie
            result = {
                "sql_query": sql_query,
                "response": ai_response,
                "status": "success",
                "question": question,
                "timestamp": pd.Timestamp.now().isoformat()
            }

            # Ajouter les informations utilisateur si authentifié
            if jwt_valid:
                result["user"] = {
                    "id": current_user.get('idpersonne'),
                    "username": current_user.get('username'),
                    "roles": current_user.get('roles', [])
                }

            # Nettoyage périodique de l'historique des conversations
            if hasattr(unified_assistant, 'cleanup_conversation_history'):
                unified_assistant.cleanup_conversation_history()

            logger.info(f"✅ Question traitée avec succès: {question[:50]}...")
            return jsonify(result), 200

        except Exception as processing_error:
            logger.error(f"Erreur traitement question: {processing_error}")
            return jsonify({
                "error": "Erreur de traitement",
                "details": str(processing_error),
                "question": question,
                "status": "error"
            }), 500

    except Exception as e:
        logger.error(f"Erreur générale dans /ask: {e}")
        return jsonify({
            "error": "Erreur serveur interne",
            "details": str(e),
            "status": "error"
        }), 500

def handle_attestation_request(question: str):
    """Gère les demandes d'attestation de présence"""
    try:
        # Extraction du nom
        name_match = re.search(
            r"(?:attestation\s+(?:de|pour)\s+)([A-Za-zÀ-ÿ\s\-\']+)",
            question,
            re.IGNORECASE
        )

        if not name_match:
            return jsonify({
                "response": "Veuillez spécifier un nom complet (ex: 'attestation de Nom Prénom')",
                "status": "info"
            })

        full_name = name_match.group(1).strip()

        if not validate_name(full_name):
            return jsonify({
                "response": "Format de nom invalide. Utilisez uniquement des lettres, espaces, tirets et apostrophes.",
                "status": "error"
            })

        logger.info(f"Recherche élève pour attestation : {full_name}")

        # Recherche de l'élève via l'assistant unifié
        if not unified_assistant:
            return jsonify({
                "response": "Service temporairement indisponible.",
                "status": "error"
            })

        student_data = unified_assistant.get_student_info_by_name(full_name)

        if not student_data:
            return jsonify({
                "response": f"Aucun élève trouvé avec le nom '{full_name}'",
                "status": "not_found"
            })

        # Préparation des données pour le PDF
        student_data['nom_complet'] = f"{student_data['NomFr']} {student_data['PrenomFr']}"
        student_data['lieu_naissance'] = student_data['lieu_de_naissance']
        student_data['annee_scolaire'] = "2024/2025"

        # Génération du PDF
        pdf_result = generator.generate(student_data)
        if pdf_result['status'] != 'success':
            return jsonify({
                "response": "Erreur lors de la génération du document",
                "status": "error"
            })

        pdf_path = pdf_result["path"]
        filename = os.path.basename(pdf_path)
        
        return jsonify({
            "response": (
                f"✅ Attestation générée pour {student_data['nom_complet']}\n\n"
                f"<a href='/static/attestations/{filename}' download>📄 Télécharger l'attestation</a>"
            ),
            "pdf_url": f"/static/attestations/{filename}",
            "status": "success",
            "document_type": "attestation"
        })

    except Exception as e:
        logger.error(f"Erreur génération attestation: {str(e)}")
        return jsonify({
            "response": "Erreur lors de la génération du document",
            "status": "error"
        })

def handle_bulletin_request(question: str):
    """Gère les demandes de bulletin scolaire"""
    try:
        # Extraction du nom
        match = re.search(r"(?:bulletin\s+(?:de|pour)\s+)([A-Za-zÀ-ÿ\s\-']+)", question, re.IGNORECASE)
        if not match:
            return jsonify({
                "response": "Veuillez spécifier un nom complet (ex: 'bulletin de Nom Prénom')",
                "status": "info"
            })

        full_name = match.group(1).strip()
        if not validate_name(full_name):
            return jsonify({
                "response": "Format de nom invalide. Utilisez uniquement des lettres, espaces, tirets et apostrophes.",
                "status": "error"
            })

        # Recherche de l'élève
        if not unified_assistant:
            return jsonify({
                "response": "Service temporairement indisponible.",
                "status": "error"
            })

        student_data = unified_assistant.get_student_info_by_name(full_name)
        if not student_data:
            return jsonify({
                "response": f"Aucun élève trouvé avec le nom '{full_name}'",
                "status": "not_found"
            })

        # Génération du bulletin (trimestre par défaut: 1)
        bulletin_result = export_bulletin_pdf(
            student_id=student_data["matricule"],
            trimestre_id=31,  # Trimestre 1
            annee_scolaire="2024/2025"
        )

        if bulletin_result["status"] != "success":
            return jsonify({
                "response": f"Erreur: {bulletin_result.get('message', 'Erreur inconnue')}",
                "status": "error"
            })

        filename = bulletin_result["filename"]
        return jsonify({
            "response": (
                f"✅ Bulletin généré pour {student_data['NomFr']} {student_data['PrenomFr']}\n\n"
                f"<a href='/static/bulletins/{filename}' download>📊 Télécharger le bulletin</a>"
            ),
            "pdf_url": f"/static/bulletins/{filename}",
            "status": "success",
            "document_type": "bulletin"
        })

    except Exception as e:
        logger.error(f"Erreur génération bulletin : {str(e)}")
        return jsonify({
            "response": "Erreur lors de la génération du bulletin.",
            "status": "error"
        })

@agent_bp.route('/reinit', methods=['POST'])
def reinitialize():
    """Réinitialise l'assistant unifié"""
    try:
        success = initialize_unified_assistant()
        
        message = "Réinitialisation réussie" if success else "Échec de la réinitialisation"
        
        # Ajouter des informations de diagnostic
        diagnostic_info = {}
        if unified_assistant:
            diagnostic_info = {
                "db_connected": unified_assistant.db is not None,
                "schema_loaded": len(unified_assistant.schema) > 0,
                "templates_loaded": len(unified_assistant.templates_questions),
                "cache_available": unified_assistant.cache is not None
            }
        
        return jsonify({
            "success": success,
            "message": message,
            "diagnostic": diagnostic_info,
            "timestamp": pd.Timestamp.now().isoformat()
        }), 200 if success else 500
        
    except Exception as e:
        logger.error(f"Erreur réinitialisation: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": pd.Timestamp.now().isoformat()
        }), 500

@agent_bp.route('/status', methods=['GET'])
def get_assistant_status():
    """Retourne le statut de l'assistant unifié"""
    try:
        if not unified_assistant:
            return jsonify({
                "status": "not_initialized",
                "message": "Assistant non initialisé"
            }), 503
        
        status_info = {
            "status": "active",
            "db_connected": unified_assistant.db is not None,
            "schema_tables": len(unified_assistant.schema),
            "templates_count": len(unified_assistant.templates_questions),
            "conversation_history_size": len(unified_assistant.conversation_history),
            "cache_available": {
                "admin_cache": unified_assistant.cache is not None,
                "parent_cache": unified_assistant.cache1 is not None
            },
            "model_config": {
                "model": unified_assistant.model,
                "temperature": unified_assistant.temperature,
                "max_tokens": unified_assistant.max_tokens
            },
            "last_sql": unified_assistant.last_generated_sql[:100] if unified_assistant.last_generated_sql else None,
            "timestamp": pd.Timestamp.now().isoformat()
        }
        
        return jsonify(status_info), 200
        
    except Exception as e:
        logger.error(f"Erreur statut: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": pd.Timestamp.now().isoformat()
        }), 500

@agent_bp.route('/clear-history', methods=['POST'])
def clear_conversation_history():
    """Efface l'historique des conversations"""
    try:
        if not unified_assistant:
            return jsonify({
                "success": False,
                "message": "Assistant non initialisé"
            }), 503
        
        # Effacer l'historique
        if hasattr(unified_assistant, 'reset_conversation'):
            unified_assistant.reset_conversation()
        
        return jsonify({
            "success": True,
            "message": "Historique des conversations effacé",
            "timestamp": pd.Timestamp.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Erreur effacement historique: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": pd.Timestamp.now().isoformat()
        }), 500

@agent_bp.route('/graph', methods=['POST'])
def generate_graph_only():
    """
    Endpoint dédié pour générer uniquement des graphiques
    à partir de données fournies
    """
    try:
        if not request.is_json:
            return jsonify({"error": "Content-Type application/json requis"}), 415

        data = request.get_json()
        
        # Validation des données requises
        if 'data' not in data or not isinstance(data['data'], list):
            return jsonify({
                "error": "Données manquantes",
                "message": "Le champ 'data' contenant une liste est requis"
            }), 422
        
        # Paramètres optionnels
        graph_type = data.get('graph_type', None)  # 'bar', 'line', 'pie'
        title = data.get('title', 'Graphique')
        
        if not unified_assistant:
            return jsonify({
                "error": "Assistant non disponible"
            }), 503
        
        # Créer DataFrame à partir des données
        import pandas as pd
        df = pd.DataFrame(data['data'])
        
        if df.empty:
            return jsonify({
                "error": "Données vides",
                "message": "Impossible de créer un graphique avec des données vides"
            }), 422
        
        # Générer le graphique
        graph_data = unified_assistant.generate_auto_graph(df, graph_type)
        
        if not graph_data:
            return jsonify({
                "error": "Impossible de générer le graphique",
                "message": "Les données ne sont pas adaptées pour la génération de graphique"
            }), 422
        
        return jsonify({
            "success": True,
            "graph": graph_data,
            "graph_type": graph_type or "auto-detected",
            "data_points": len(df),
            "columns": df.columns.tolist(),
            "timestamp": pd.Timestamp.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Erreur génération graphique: {e}")
        return jsonify({
            "error": "Erreur lors de la génération du graphique",
            "details": str(e),
            "timestamp": pd.Timestamp.now().isoformat()
        }), 500

@agent_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint pour vérifier que le service fonctionne"""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": pd.Timestamp.now().isoformat(),
            "services": {
                "assistant": unified_assistant is not None,
                "database": False,
                "cache": False
            }
        }
        
        # Test de la base de données
        if unified_assistant and unified_assistant.db:
            try:
                # Test simple de connectivité
                result = unified_assistant.execute_sql_query("SELECT 1")
                health_status["services"]["database"] = result["success"]
            except:
                health_status["services"]["database"] = False
        
        # Test du cache
        if unified_assistant:
            health_status["services"]["cache"] = (
                unified_assistant.cache is not None and 
                unified_assistant.cache1 is not None
            )
        
        # Déterminer le statut global
        all_services_ok = all(health_status["services"].values())
        if not all_services_ok:
            health_status["status"] = "degraded"
        
        status_code = 200 if all_services_ok else 503
        return jsonify(health_status), status_code
        
    except Exception as e:
        logger.error(f"Erreur health check: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": pd.Timestamp.now().isoformat()
        }), 503

import pandas as pd