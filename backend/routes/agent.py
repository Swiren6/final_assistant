from flask import Blueprint, request, jsonify,send_from_directory
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request, get_jwt
import logging
import re
import os
from typing import List, Dict, Optional
import fitz 
import time 
from PIL import Image
import io
import base64

from routes.auth import login
from services.auth_service import AuthService
from agent.assistant import SQLAssistant  
from agent.pdf_utils.attestation import PDFGenerator
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
assistant = None

def initialize_assistant():
    """Initialize the unified SQL assistant"""
    global assistant
    try:
        assistant = SQLAssistant()
        if assistant and assistant.db:
            logger.info("✅ Assistant unifié initialisé avec succès")
            return True
        else:
            logger.warning("❌ Assistant initialisé mais DB manquante")
            return False
    except Exception as e:
        logger.warning(f"❌ Erreur initialisation assistant unifié: {e}")
        assistant = None
        return False

# Initialize at import
initialize_assistant()

# Ajout dans la route /ask du fichier agent.py

@agent_bp.route('/ask', methods=['POST'])
def ask_sql():
    """
    Route principale pour les questions SQL avec génération de graphiques
    Utilise le nouvel assistant unifié qui combine SQL + IA + graphiques + gestion multi-enfants
    """
    jwt_valid = False
    current_user = None
    jwt_error = None

    # 🔍 Authentification via JWT
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
        if not assistant:
            if not initialize_assistant():
                return jsonify({
                    "error": "Assistant non disponible",
                    "details": "Impossible d'initialiser l'assistant IA"
                }), 503

        # 🧾 Cas spécial : Attestation de présence
        if "attestation" in question.lower():
            return handle_attestation_request(question)

        

        # 🤖 Traitement IA principal avec l'assistant unifié
        try:
            # 🎯 MODIFICATION : Récupération de 3 valeurs (sql, response, graph)
            sql_query, ai_response, graph_data = assistant.ask_question(question, user_id, roles)
            
            # 🎯 NOUVELLE LOGIQUE : Vérifier si c'est une demande de clarification multi-enfants
            if not sql_query and ai_response and "plusieurs enfants" in ai_response:
                # C'est une demande de clarification, pas une erreur
                return jsonify({
                    "response": ai_response,
                    "status": "clarification_needed",
                    "question": question,
                    "user_action_required": True,
                    "timestamp": pd.Timestamp.now().isoformat()
                }), 200
            
            if not sql_query:
                return jsonify({
                    "error": "La requête générée est vide",
                    "question": question,
                    "status": "error"
                }), 422
            
            # Création de la réponse enrichie
            result = {
                "sql_query": sql_query,
                "response": ai_response,
                "status": "success",
                "question": question,
                "timestamp": pd.Timestamp.now().isoformat()
            }
            
            # 🎯 AJOUT : Inclure le graphique si généré
            if graph_data:
                result["graph"] = graph_data
                result["has_graph"] = True
                logger.info("📊 Graphique généré automatiquement")
            else:
                result["has_graph"] = False

            # Ajouter les informations utilisateur si authentifié
            if jwt_valid:
                result["user"] = {
                    "id": current_user.get('idpersonne'),
                    "username": current_user.get('username'),
                    "roles": current_user.get('roles', [])
                }

            # Nettoyage périodique de l'historique des conversations
            if hasattr(assistant, 'cleanup_conversation_history'):
                assistant.cleanup_conversation_history()

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

# Nouvelle route pour gérer les clarifications multi-enfants
@agent_bp.route('/clarify-child', methods=['POST'])
def clarify_child_selection():
    """
    Route spéciale pour gérer les clarifications de sélection d'enfant
    """
    try:
        if not request.is_json:
            return jsonify({"error": "Content-Type application/json requis"}), 415

        data = request.get_json()
        if not data:
            return jsonify({"error": "Corps de requête JSON vide"}), 400

        # Extraction des paramètres
        original_question = data.get('original_question', '')
        child_specification = data.get('child_specification', '')  # "Ahmed", "mon fils", "ma grande", etc.
        user_id = data.get('user_id')

        if not all([original_question, child_specification, user_id]):
            return jsonify({
                "error": "Paramètres manquants",
                "required": ["original_question", "child_specification", "user_id"]
            }), 422

        # Reformuler la question avec la spécification de l'enfant
        clarified_question = f"{original_question} pour {child_specification}"
        
        # Retraiter avec la question clarifiée
        roles = ['ROLE_PARENT']  # Assumer parent pour cette route
        sql_query, ai_response, graph_data = assistant.ask_question(clarified_question, user_id, roles)
        
        if not sql_query:
            return jsonify({
                "error": "Impossible de traiter la question clarifiée",
                "clarified_question": clarified_question,
                "status": "error"
            }), 422

        # Réponse enrichie
        result = {
            "sql_query": sql_query,
            "response": ai_response,
            "status": "success",
            "original_question": original_question,
            "clarified_question": clarified_question,
            "child_specification": child_specification,
            "timestamp": pd.Timestamp.now().isoformat()
        }
        
        if graph_data:
            result["graph"] = graph_data
            result["has_graph"] = True
        else:
            result["has_graph"] = False

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Erreur clarification enfant: {e}")
        return jsonify({
            "error": "Erreur lors de la clarification",
            "details": str(e),
            "status": "error"
        }), 500

# Méthode utilitaire pour extraire les informations d'enfant à partir du texte
def extract_child_context_from_question(question: str, children_data: List[Dict]) -> Optional[Dict]:
    """
    Extrait le contexte spécifique d'un enfant à partir de la question
    Retourne les informations de l'enfant ciblé ou None si ambiguë
    """
    question_lower = question.lower()
    
    # 1. Vérifier mention directe du prénom
    for child in children_data:
        if child['prenom'].lower() in question_lower:
            return child
    
    # 2. Vérifier indicateurs de genre
    male_indicators = ['garçon', 'garcon', 'fils', 'mon fils', 'mon garçon']
    female_indicators = ['fille', 'ma fille']
    
    male_children = [child for child in children_data if child.get('genre') == 'M']
    female_children = [child for child in children_data if child.get('genre') == 'F']
    
    for indicator in male_indicators:
        if indicator in question_lower and len(male_children) == 1:
            return male_children[0]
    
    for indicator in female_indicators:
        if indicator in question_lower and len(female_children) == 1:
            return female_children[0]
    
    # 3. Vérifier indicateurs d'âge
    age_indicators_old = ['grand', 'grande', 'aîné', 'ainee', 'aînée']
    age_indicators_young = ['petit', 'petite', 'cadet', 'cadette', 'benjamin', 'benjamine']
    
    for indicator in age_indicators_old:
        if indicator in question_lower:
            return min(children_data, key=lambda x: x.get('age', 0))
    
    for indicator in age_indicators_young:
        if indicator in question_lower:
            return max(children_data, key=lambda x: x.get('age', 0))
    
    return None

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
        if not assistant:
            return jsonify({
                "response": "Service temporairement indisponible.",
                "status": "error"
            })

        student_data = assistant.get_student_info_by_name(full_name)

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
                # f"<a href='/static/attestations/{filename}' download>📄 Télécharger l'attestation</a>"
            ),
            "pdf_url": f'/download-attestation/{filename}',
            "status": "success",
            "document_type": "attestation"
        })

    except Exception as e:
        logger.error(f"Erreur génération attestation: {str(e)}")
        return jsonify({
            "response": "Erreur lors de la génération du document",
            "status": "error"
        })


@agent_bp.route('/reinit', methods=['POST'])
def reinitialize():
    """Réinitialise l'assistant unifié"""
    try:
        success = initialize_assistant()
        
        message = "Réinitialisation réussie" if success else "Échec de la réinitialisation"
        
        # Ajouter des informations de diagnostic
        diagnostic_info = {}
        if assistant:
            diagnostic_info = {
                "db_connected": assistant.db is not None,
                "schema_loaded": len(assistant.schema) > 0,
                "templates_loaded": len(assistant.templates_questions),
                "cache_available": assistant.cache is not None
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
        if not assistant:
            return jsonify({
                "status": "not_initialized",
                "message": "Assistant non initialisé"
            }), 503
        
        status_info = {
            "status": "active",
            "db_connected": assistant.db is not None,
            "schema_tables": len(assistant.schema),
            "templates_count": len(assistant.templates_questions),
            "conversation_history_size": len(assistant.conversation_history),
            "cache_available": {
                "admin_cache": assistant.cache is not None,
                "parent_cache": assistant.cache1 is not None
            },
            "model_config": {
                "model": assistant.model,
                "temperature": assistant.temperature,
                "max_tokens": assistant.max_tokens
            },
            "last_sql": assistant.last_generated_sql[:100] if assistant.last_generated_sql else None,
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
        if not assistant:
            return jsonify({
                "success": False,
                "message": "Assistant non initialisé"
            }), 503
        
        # Effacer l'historique
        if hasattr(assistant, 'reset_conversation'):
            assistant.reset_conversation()
        
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
        
        if not assistant:
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
        graph_data = assistant.generate_auto_graph(df, graph_type)
        
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
@agent_bp.route('/static/images/<path:filename>')
def serve_image(filename):
    """
    Sert les images de prévisualisation des PDF ou les convertit à la volée
            """
    try:
        # Construire le chemin de l'image
        image_path = os.path.join('static', 'images', filename)
        
        # Si l'image existe déjà, la servir directement
        if os.path.exists(image_path):
            logger.info(f"✅ Image trouvée: {image_path}")
            return send_from_directory("static/images", filename)
        
        # Sinon, essayer de la générer depuis le PDF correspondant
        logger.info(f"🔄 Génération image à la volée pour: {filename}")
        
        # Construire le chemin du PDF original
        pdf_filename = filename.replace('.png', '.pdf').replace('.jpg', '.pdf')
        pdf_path = os.path.join('static', 'attestations', pdf_filename)
        
        if not os.path.exists(pdf_path):
            logger.warning(f"❌ PDF source non trouvé: {pdf_path}")
            return jsonify({'error': 'PDF source non trouvé'}), 404
        
        # Créer le dossier images s'il n'existe pas
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        
        # Convertir PDF en image
        logger.info(f"🖼️ Conversion PDF -> PNG: {pdf_path} -> {image_path}")
        pdf_document = fitz.open(pdf_path)
        page = pdf_document[0]  # Première page
        
        # Rendu en image (résolution 200 DPI pour bonne qualité mobile)
        matrix = fitz.Matrix(200/72, 200/72)  # 200 DPI
        pix = page.get_pixmap(matrix=matrix)
        
        # Sauvegarder l'image
        pix.save(image_path)
        pdf_document.close()
        
        logger.info(f"✅ Image générée avec succès: {image_path}")
        
        # Servir l'image nouvellement créée
        return send_from_directory("static/images", filename)
        
    except Exception as e:
        logger.error(f"❌ Erreur conversion PDF vers image: {e}")
        # Fallback: servir une image par défaut ou erreur 404
        return jsonify({'error': f'Erreur génération image: {str(e)}'}), 500


# Endpoint pour générer des attestations
@agent_bp.route('/generate-attestation/<student_name>', methods=['GET'])
def generate_attestation_endpoint(student_name):
    """Endpoint dédié pour générer des attestations"""
    try:
        if not assistant:
            return jsonify({"error": "Assistant non disponible"}), 503
        
        # Récupérer les infos de l'étudiant
        student_data = assistant.get_student_info_by_name(student_name)
        if not student_data:
            return jsonify({"error": f"Aucun élève trouvé avec le nom '{student_name}'"}), 404
        
        # Préparer les données
        student_data['nom_complet'] = f"{student_data['NomFr']} {student_data['PrenomFr']}"
        student_data['classe'] = student_data.get('classe', 'Classe non précisée')
        student_data['lieu_naissance'] = student_data.get('lieu_de_naissance', 'Non précisé')
        student_data['annee_scolaire'] = "2024/2025"
        
        # Générer le PDF
        pdf_result = generator.generate(student_data)
        if pdf_result['status'] != 'success':
            return jsonify({"error": "Erreur lors de la génération du PDF"}), 500
        
        return jsonify({
            "success": True,
            "message": f"Attestation générée pour {student_name}",
            "pdf_url": f"/download-attestation/{pdf_result['filename']}",
            "filename": pdf_result['filename']
        })
        
    except Exception as e:
        logger.error(f"Erreur génération attestation: {e}")
        return jsonify({"error": f"Erreur interne: {str(e)}"}), 500
    
@agent_bp.route('/download-attestation/<filename>')
def download_attestation(filename):
    try:
        return send_from_directory(
            os.path.abspath('static/attestations'),
            filename,
            as_attachment=True
        )
    except FileNotFoundError:
        return jsonify({"error": "Fichier non trouvé"}), 404



@agent_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint pour vérifier que le service fonctionne"""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": pd.Timestamp.now().isoformat(),
            "services": {
                "assistant": assistant is not None,
                "database": False,
                "cache": False
            }
        }
        
        # Test de la base de données
        if assistant and assistant.db:
            try:
                # Test simple de connectivité
                result = assistant.execute_sql_query("SELECT 1")
                health_status["services"]["database"] = result["success"]
            except:
                health_status["services"]["database"] = False
        
        # Test du cache
        if assistant:
            health_status["services"]["cache"] = (
                assistant.cache is not None and 
                assistant.cache1 is not None
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