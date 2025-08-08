from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request, get_jwt
import logging
import re
import os

from routes.auth import login
from services.auth_service import AuthService
from agent.assistant import SQLAssistant
from agent.pdf_utils.attestation import PDFGenerator
from agent.sql_agent import SQLAgent 
from agent.pdf_utils.attestation import export_attestation_pdf
from agent.pdf_utils.bulletin import export_bulletin_pdf


from config.database import init_db, get_db, get_db_connection

generator = PDFGenerator()
# result = generator.generate(student_data)

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


# Alternative plus simple si vous voulez juste vérifier la longueur
# def validate_name_simple(name: str) -> bool:
#     """Validation simple du nom"""
#     if not name or not isinstance(name, str):
#         return False
#     name = name.strip()
#     return 2 <= len(name) <= 100 and not any(char in name for char in ['<', '>', '{', '}', '[', ']', '(', ')'])

agent_bp = Blueprint('agent_bp', __name__)
logger = logging.getLogger(__name__)

assistant = None
engine = SQLAgent(db=None)
def initialize_assistant():
    global assistant
    try:
        assistant = SQLAssistant()
        if assistant and assistant.db:
            print("✅ Assistant initialisé avec succès")
            return True
        else:
            print("❌ Assistant initialisé mais DB manquante")
            return False
    except Exception as e:
        print(f"❌ Erreur initialisation assistant: {e}")
        assistant = None
        return False

# Initialisation à l'import
initialize_assistant()


@agent_bp.route('/ask', methods=['POST'])
def ask_sql():
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

                print(f"DEBUG - JWT Identity: {jwt_identity}")
                print(f"DEBUG - JWT Claims: {jwt_claims}")

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
                print(f"DEBUG - Erreur JWT: {jwt_error}")

    except Exception as e:
        jwt_error = str(e)
        print(f"DEBUG - Erreur générale JWT: {jwt_error}")

    # 🧠 Traitement de la question
    try:
        if not request.is_json:
            return jsonify({"error": "Content-Type application/json requis"}), 415

        data = request.get_json()
        if not data:
            return jsonify({"error": "Corps de requête JSON vide"}), 400

        question = next((str(data[field]).strip() for field in ['question', 'subject', 'query', 'text', 'message', 'prompt']
                         if field in data and data[field] and str(data[field]).strip()), None)

        if not question:
            return jsonify({
                "error": "Question manquante",
                "expected_fields": ['question', 'subject', 'query', 'text', 'message', 'prompt'],
                "received_fields": list(data.keys())
            }), 422

        user_id = current_user.get('idpersonne') if current_user else None
        roles = current_user.get('roles', []) if current_user else []

        print(f"DEBUG FINAL - user_id: {user_id}, roles: {roles}")

        if not assistant:
            if not initialize_assistant():
                return jsonify({
                    "error": "Assistant non disponible",
                    "details": "Impossible d'initialiser l'assistant IA"
                }), 503

        # 🧾 Cas spécial attestation
        if "attestation" in question.lower():
            name_match = re.search(
                r"(?:attestation\s+(?:de|pour)\s+)([A-Za-zÀ-ÿ\s\-\']+)",
                question,
                re.IGNORECASE
            )

            if not name_match:
                return jsonify({"response": "Veuillez spécifier un nom (ex: 'attestation de Nom Prénom')"})

            full_name = name_match.group(1).strip()

            if not validate_name(full_name):
                return jsonify({"response": "Format de nom invalide. Utilisez uniquement des lettres et espaces"})

            print(f"Recherche élève pour nom complet : {full_name}")

            student_data = engine.get_student_info_by_name(full_name)

            print(f"Résultat de recherche: {student_data}")

            if not student_data:
                return jsonify({"response": f"Aucun élève trouvé avec le nom '{full_name}'"})

            student_data['nom_complet'] = f"{student_data['NomFr']} {student_data['PrenomFr']}"
            student_data['lieu_naissance'] = student_data['lieu_de_naissance']
            student_data['annee_scolaire'] = "2024/2025"

            try:
                pdf_result = generator.generate(student_data)
                if pdf_result['status'] != 'success':
                    return jsonify({"response": "Erreur lors de la génération du document"})

                pdf_path = pdf_result["path"]
                filename = os.path.basename(pdf_path)
                return jsonify({
                    "response": (
                        f"✅ Attestation générée pour {student_data['nom_complet']}\n\n"
                        f"<a href='/static/attestations/{filename}' download>Télécharger</a>"
                    ),
                    "pdf_url": f"/static/attestations/{filename}"
                })

            except Exception as e:
                logger.error(f"Erreur génération PDF: {str(e)}")
                return jsonify({"response": "Erreur lors de la génération du document"})
        
        # 🧾 Cas spécial bulletin
        if "bulletin" in question.lower():
            match = re.search(r"(?:bulletin\s+(?:de|pour)\s+)([A-Za-zÀ-ÿ\s\-']+)", question, re.IGNORECASE)
            if not match:
                return jsonify({"response": "Veuillez spécifier un nom complet (ex: 'bulletin de Nom Prénom')"})

            full_name = match.group(1).strip()
            if not validate_name(full_name):
                return jsonify({"response": "Format de nom invalide. Utilisez uniquement des lettres et espaces"})

            student_data = engine.get_student_info_by_name(full_name)
            if not student_data:
                return jsonify({"response": f"Aucun élève trouvé avec le nom '{full_name}'"})

            try:
                bulletin_result = export_bulletin_pdf(
                    student_id=student_data["matricule"],
                    trimestre_id=31,
                    annee_scolaire="2024/2025"
                )

                if bulletin_result["status"] != "success":
                    return jsonify({"response": f"Erreur: {bulletin_result['message']}"})

                filename = bulletin_result["filename"]
                return jsonify({
                    "response": (
                        f"✅ Bulletin généré pour {student_data['NomFr']} {student_data['PrenomFr']}\n\n"
                        f"<a href='/static/bulletins/{filename}' download>Télécharger le PDF</a>"
                    ),
                    "pdf_url": f"/static/bulletins/{filename}"
                })

            except Exception as e:
                logger.error(f"Erreur génération bulletin : {str(e)}")
                return jsonify({"response": "Erreur lors de la génération du bulletin."})

        # Traitement IA classique
        try:
            sql_query, response = assistant.ask_question(question, user_id, roles)
            
            # Récupérer les données brutes pour générer un graphique si pertinent
            db_results = engine.execute_natural_query(question)
            graph_data = None
            
            if db_results and 'data' in db_results and len(db_results['data']) > 1:
                try:
                    df = pd.DataFrame(db_results['data'])
                    graph_type = engine.detect_graph_type(question, df.columns)
                    if graph_type:
                        graph_data = engine.generate_auto_graph(df, graph_type)
                except Exception as graph_error:
                    logger.error(f"Erreur génération graphique: {graph_error}")

            result = {
                "sql_query": sql_query,
                "response": response,
                "status": "success",
                "question": question,
                "data": db_results['data'] if db_results and 'data' in db_results else None
            }

            if graph_data:
                result["graph"] = graph_data

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
        return jsonify({
            "error": "Erreur serveur interne",
            "details": str(e)
        }), 500

@agent_bp.route('/reinit', methods=['POST'])
def reinitialize():
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