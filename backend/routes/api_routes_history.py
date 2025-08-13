from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from agent.conversation_history import ConversationHistory
import logging
import traceback

logger = logging.getLogger(__name__)
history_bp = Blueprint('history', __name__, url_prefix='/api')

# Instance du gestionnaire d'historique avec initialisation sécurisée
try:
    conversation_history = ConversationHistory()
    logger.info("✅ ConversationHistory initialisé avec succès")
except Exception as e:
    logger.error(f"❌ Erreur initialisation ConversationHistory: {e}")
    conversation_history = None

def get_current_user():
    """Extrait et valide les informations utilisateur du JWT."""
    try:
        jwt_identity = get_jwt_identity()
        jwt_claims = get_jwt()
        
        logger.debug(f"JWT Identity: {jwt_identity}")
        logger.debug(f"JWT Claims: {jwt_claims}")
        
        if not jwt_identity or not jwt_claims:
            logger.error("JWT invalide ou vide")
            return None
        
        idpersonne = jwt_claims.get('idpersonne')
        if idpersonne is None:
            logger.error("idpersonne manquant dans le JWT")
            return None
        
        # Conversion robuste en int
        try:
            idpersonne = int(idpersonne)
        except (ValueError, TypeError) as e:
            logger.error(f"Impossible de convertir idpersonne en int: {idpersonne} -> {e}")
            return None
        
        user_data = {
            'sub': jwt_identity,
            'idpersonne': idpersonne,
            'roles': jwt_claims.get('roles', []),
            'username': jwt_claims.get('username', '')
        }
        
        logger.debug(f"Utilisateur extrait: {user_data}")
        return user_data
        
    except Exception as e:
        logger.error(f"Erreur extraction JWT: {e}")
        logger.error(traceback.format_exc())
        return None

@history_bp.route('/conversations', methods=['GET'])
@jwt_required()
def get_user_conversations():
    """Récupère les conversations d'un utilisateur"""
    if not conversation_history:
        return jsonify({
            'success': False,
            'error': 'Service d\'historique non disponible'
        }), 503
    
    current_user = get_current_user()
    if not current_user:
        return jsonify({
            'success': False,
            'error': 'Authentification invalide'
        }), 401
        
    try:
        user_id = current_user['idpersonne']
        limit = request.args.get('limit', 50, type=int)
        
        # Validation
        if limit > 100:
            limit = 100
        
        logger.info(f"Récupération conversations pour user_id: {user_id} (limit: {limit})")
        
        conversations = conversation_history.get_user_conversations(user_id, limit)
        
        logger.info(f"Conversations trouvées: {len(conversations)}")
        
        return jsonify({
            'success': True,
            'conversations': conversations,
            'total': len(conversations),
            'user_id': user_id
        }), 200
        
    except Exception as e:
        logger.error(f"Erreur récupération conversations: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': 'Erreur lors de la récupération des conversations',
            'details': str(e)
        }), 500

@history_bp.route('/conversations/<int:conversation_id>/messages', methods=['GET'])
@jwt_required()
def get_conversation_messages(conversation_id):
    """Récupère les messages d'une conversation"""
    if not conversation_history:
        return jsonify({
            'success': False,
            'error': 'Service d\'historique non disponible'
        }), 503
    
    current_user = get_current_user()
    if not current_user:
        return jsonify({
            'success': False,
            'error': 'Authentification invalide'
        }), 401
        
    try:
        user_id = current_user['idpersonne']
        
        logger.info(f"Récupération messages conversation {conversation_id} pour user {user_id}")
        
        messages = conversation_history.get_conversation_messages(conversation_id, user_id)
        
        if messages is None:
            return jsonify({
                'success': False,
                'error': 'Conversation non trouvée ou accès refusé'
            }), 404
        
        return jsonify({
            'success': True,
            'messages': messages,
            'conversation_id': conversation_id,
            'total': len(messages)
        }), 200
        
    except Exception as e:
        logger.error(f"Erreur récupération messages: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': 'Erreur lors de la récupération des messages'
        }), 500

@history_bp.route('/conversations/create', methods=['POST'])
@jwt_required()
def create_conversation():
    """Crée une nouvelle conversation"""
    if not conversation_history:
        return jsonify({
            'success': False,
            'error': 'Service d\'historique non disponible'
        }), 503
    
    current_user = get_current_user()
    if not current_user:
        return jsonify({
            'success': False,
            'error': 'Authentification invalide'
        }), 401
        
    try:
        user_id = current_user['idpersonne']
        data = request.get_json() or {}
        
        first_message = data.get('first_message', '').strip()
        
        logger.info(f"Création conversation pour user_id: {user_id}")
        logger.debug(f"Premier message: {first_message[:100]}...")
        
        conversation_id = conversation_history.create_conversation(user_id, first_message)
        
        if conversation_id:
            logger.info(f"✅ Conversation créée avec ID: {conversation_id}")
            return jsonify({
                'success': True,
                'conversation_id': conversation_id,
                'message': 'Conversation créée avec succès'
            }), 201
        else:
            logger.error("❌ Échec création conversation")
            return jsonify({
                'success': False,
                'error': 'Erreur lors de la création de la conversation'
            }), 500
            
    except Exception as e:
        logger.error(f"Erreur création conversation: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': 'Erreur lors de la création de la conversation'
        }), 500

@history_bp.route('/conversations/<int:conversation_id>/messages', methods=['POST'])
@jwt_required()
def add_message_to_conversation(conversation_id):
    """Ajoute un message à une conversation existante"""
    if not conversation_history:
        return jsonify({
            'success': False,
            'error': 'Service d\'historique non disponible'
        }), 503
    
    current_user = get_current_user()
    if not current_user:
        return jsonify({
            'success': False,
            'error': 'Authentification invalide'
        }), 401
    
    try:
        user_id = current_user['idpersonne']
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'Données JSON manquantes'
            }), 400

        # Validation des champs requis
        message_type = data.get('message_type', '').strip()
        content = data.get('content', '').strip()
        
        if not message_type or not content:
            return jsonify({
                'success': False,
                'error': 'Champs requis manquants: message_type et content'
            }), 400
        
        if message_type not in ['user', 'assistant', 'system']:
            return jsonify({
                'success': False,
                'error': f'Type de message invalide: {message_type}. Types autorisés: user, assistant, system'
            }), 400

        # Vérification de la propriété
        if not conversation_history.is_owner(conversation_id, user_id):
            return jsonify({
                'success': False,
                'error': 'Conversation non trouvée ou accès refusé'
            }), 404

        # Extraction des données optionnelles
        sql_query = data.get('sql_query')
        graph_data = data.get('graph_data')
        
        logger.info(f"Ajout message type '{message_type}' à conversation {conversation_id}")
        logger.debug(f"Content: {content[:100]}...")
        
        # Ajout du message
        success = conversation_history.add_message(
            conversation_id=conversation_id,
            message_type=message_type,
            content=content,
            sql_query=sql_query,
            graph_data=graph_data
        )

        if success:
            logger.info(f"✅ Message ajouté avec succès à conversation {conversation_id}")
            return jsonify({
                'success': True,
                'message': 'Message ajouté avec succès'
            }), 201
        else:
            logger.error(f"❌ Échec ajout message à conversation {conversation_id}")
            return jsonify({
                'success': False,
                'error': 'Échec de l\'ajout du message'
            }), 500

    except Exception as e:
        logger.error(f"Erreur ajout message à conversation {conversation_id}: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': 'Erreur lors de l\'ajout du message'
        }), 500

@history_bp.route('/conversations/<int:conversation_id>/delete', methods=['POST'])
@jwt_required()
def delete_conversation(conversation_id):
    """Supprime une conversation (soft delete)"""
    if not conversation_history:
        return jsonify({
            'success': False,
            'error': 'Service d\'historique non disponible'
        }), 503
    
    current_user = get_current_user()
    if not current_user:
        return jsonify({
            'success': False,
            'error': 'Authentification invalide'
        }), 401
        
    try:
        user_id = current_user['idpersonne']
        
        logger.info(f"Suppression conversation {conversation_id} pour user {user_id}")
        
        success = conversation_history.delete_conversation(conversation_id, user_id)
        
        if success:
            logger.info(f"✅ Conversation {conversation_id} supprimée")
            return jsonify({
                'success': True,
                'message': 'Conversation supprimée avec succès'
            }), 200
        else:
            logger.warning(f"❌ Impossible de supprimer conversation {conversation_id}")
            return jsonify({
                'success': False,
                'error': 'Conversation non trouvée ou accès refusé'
            }), 404
            
    except Exception as e:
        logger.error(f"Erreur suppression conversation {conversation_id}: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': 'Erreur lors de la suppression de la conversation'
        }), 500

@history_bp.route('/conversations/start', methods=['POST'])
@jwt_required()
def start_conversation():
    """Crée ou récupère une conversation active pour l'utilisateur"""
    if not conversation_history:
        return jsonify({
            'success': False,
            'error': 'Service d\'historique non disponible'
        }), 503
    
    current_user = get_current_user()
    if not current_user:
        return jsonify({
            'success': False, 
            'error': 'Authentification invalide'
        }), 401
    
    try:
        user_id = current_user['idpersonne']
        data = request.get_json() or {}
        initial_message = data.get('first_message', '')

        # Récupère la dernière conversation active ou en crée une nouvelle
        last_conv = conversation_history.get_last_active_conversation(user_id)
        
        if last_conv:
            conversation_id = last_conv['id']
            logger.info(f"Conversation active récupérée: {conversation_id}")
        else:
            conversation_id = conversation_history.create_conversation(user_id, initial_message)
            logger.info(f"Nouvelle conversation créée: {conversation_id}")

        if not conversation_id:
            return jsonify({
                'success': False,
                'error': 'Impossible de créer/récupérer la conversation'
            }), 500
        
        return jsonify({
            'success': True,
            'conversation_id': conversation_id,
            'is_new': last_conv is None
        }), 200

    except Exception as e:
        logger.error(f"Erreur démarrage conversation: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': 'Erreur lors de la gestion de la conversation'
        }), 500

# Route de diagnostic pour déboguer
@history_bp.route('/conversations/debug', methods=['GET'])
@jwt_required()
def debug_conversations():
    """Route de diagnostic pour déboguer les conversations"""
    if not conversation_history:
        return jsonify({
            'error': 'Service d\'historique non disponible'
        }), 503
    
    current_user = get_current_user()
    if not current_user:
        return jsonify({
            'error': 'Authentification invalide',
            'jwt_identity': get_jwt_identity(),
            'jwt_claims': get_jwt()
        }), 401
    
    try:
        user_id = current_user['idpersonne']
        
        # Test direct de la base de données
        import sqlite3
        with sqlite3.connect(conversation_history.db_path) as conn:
            cursor = conn.cursor()
            
            # Compter les conversations totales
            cursor.execute('SELECT COUNT(*) FROM conversations')
            total_conversations = cursor.fetchone()[0]
            
            # Compter les conversations de cet utilisateur
            cursor.execute('SELECT COUNT(*) FROM conversations WHERE user_id = ?', (user_id,))
            user_conversations = cursor.fetchone()[0]
            
            # Dernières conversations
            cursor.execute('''
                SELECT id, title, created_at, is_deleted
                FROM conversations 
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 5
            ''', (user_id,))
            recent_conversations = cursor.fetchall()
        
        return jsonify({
            'user_info': current_user,
            'db_path': conversation_history.db_path,
            'total_conversations': total_conversations,
            'user_conversations': user_conversations,
            'recent_conversations': recent_conversations,
            'db_exists': os.path.exists(conversation_history.db_path)
        }), 200
        
    except Exception as e:
        logger.error(f"Erreur debug: {e}")
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

import os