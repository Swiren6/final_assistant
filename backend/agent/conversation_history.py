import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
import json
import os

logger = logging.getLogger(__name__)

class ConversationHistory:
    def __init__(self, db_path: str = None):
        """
        Initialise le gestionnaire d'historique des conversations
        """
        if db_path is None:
            # Utiliser le même chemin que votre base principale ou créer une DB séparée
            db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'conversations.db')
        
        self.db_path = db_path
        self.init_database()
        logger.info(f"ConversationHistory initialisé avec DB: {self.db_path}")
    
    def init_database(self):
        """Crée les tables nécessaires si elles n'existent pas"""
        try:
            # Créer le répertoire si nécessaire
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Table des conversations
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS conversations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        title TEXT NOT NULL DEFAULT 'Nouvelle conversation',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT 1,
                        is_deleted BOOLEAN DEFAULT 0
                    )
                ''')
                
                # Table des messages
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS conversation_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        conversation_id INTEGER NOT NULL,
                        message_type TEXT NOT NULL CHECK (message_type IN ('user', 'assistant', 'system')),
                        content TEXT NOT NULL,
                        sql_query TEXT,
                        graph_data TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                    )
                ''')
                
                # Index pour optimiser les requêtes
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_conv_user_id ON conversations(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_conv_updated_at ON conversations(updated_at DESC)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_conv_id ON conversation_messages(conversation_id)')
                
                conn.commit()
                logger.info("Tables d'historique créées/vérifiées avec succès")
                
        except Exception as e:
            logger.error(f"Erreur initialisation DB historique: {e}")
            raise
    
    def create_conversation(self, user_id: int, first_message: str = '') -> Optional[int]:
        """Crée une nouvelle conversation"""
        try:
            # Générer un titre basé sur le premier message
            title = self._generate_title(first_message)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO conversations (user_id, title, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, title, datetime.now(), datetime.now()))
                
                conversation_id = cursor.lastrowid
                conn.commit()
                
                logger.info(f"Conversation créée: ID={conversation_id}, User={user_id}")
                return conversation_id
                
        except Exception as e:
            logger.error(f"Erreur création conversation: {e}")
            return None
    
    def add_message(self, conversation_id: int, message_type: str, content: str, 
                   sql_query: str = None, graph_data: str = None) -> bool:
        """Ajoute un message à une conversation"""
        try:
            if message_type not in ['user', 'assistant', 'system']:
                logger.error(f"Type de message invalide: {message_type}")
                return False
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Vérifier que la conversation existe et n'est pas supprimée
                cursor.execute('''
                    SELECT id FROM conversations 
                    WHERE id = ? AND is_deleted = 0
                ''', (conversation_id,))
                
                if not cursor.fetchone():
                    logger.error(f"Conversation {conversation_id} non trouvée ou supprimée")
                    return False
                
                # Ajouter le message
                cursor.execute('''
                    INSERT INTO conversation_messages 
                    (conversation_id, message_type, content, sql_query, graph_data)
                    VALUES (?, ?, ?, ?, ?)
                ''', (conversation_id, message_type, content, sql_query, graph_data))
                
                # Mettre à jour la date de dernière modification de la conversation
                cursor.execute('''
                    UPDATE conversations 
                    SET updated_at = ? 
                    WHERE id = ?
                ''', (datetime.now(), conversation_id))
                
                conn.commit()
                logger.debug(f"Message ajouté: Conv={conversation_id}, Type={message_type}")
                return True
                
        except Exception as e:
            logger.error(f"Erreur ajout message: {e}")
            return False
    
    def get_user_conversations(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Récupère les conversations d'un utilisateur"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row  # Pour avoir des dictionnaires
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT 
                        c.id,
                        c.title,
                        c.created_at,
                        c.updated_at,
                        COUNT(cm.id) as message_count,
                        (SELECT cm2.content FROM conversation_messages cm2 
                         WHERE cm2.conversation_id = c.id 
                         ORDER BY cm2.created_at ASC LIMIT 1) as first_message
                    FROM conversations c
                    LEFT JOIN conversation_messages cm ON c.id = cm.conversation_id
                    WHERE c.user_id = ? AND c.is_deleted = 0
                    GROUP BY c.id
                    ORDER BY c.updated_at DESC
                    LIMIT ?
                ''', (user_id, limit))
                
                conversations = []
                for row in cursor.fetchall():
                    conversations.append({
                        'id': row['id'],
                        'title': row['title'],
                        'created_at': row['created_at'],
                        'updated_at': row['updated_at'],
                        'message_count': row['message_count'],
                        'first_message': row['first_message'] or 'Conversation vide'
                    })
                
                logger.info(f"Conversations récupérées: {len(conversations)} pour user {user_id}")
                return conversations
                
        except Exception as e:
            logger.error(f"Erreur récupération conversations pour user {user_id}: {e}")
            return []
    
    def get_conversation_messages(self, conversation_id: int, user_id: int) -> List[Dict[str, Any]]:
        """Récupère tous les messages d'une conversation"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Vérifier que l'utilisateur est propriétaire
                cursor.execute('''
                    SELECT user_id FROM conversations 
                    WHERE id = ? AND is_deleted = 0
                ''', (conversation_id,))
                
                result = cursor.fetchone()
                if not result or result['user_id'] != user_id:
                    logger.warning(f"Accès refusé conv {conversation_id} pour user {user_id}")
                    return []
                
                # Récupérer les messages
                cursor.execute('''
                    SELECT 
                        id, message_type, content, sql_query, 
                        graph_data, created_at
                    FROM conversation_messages
                    WHERE conversation_id = ?
                    ORDER BY created_at ASC
                ''', (conversation_id,))
                
                messages = []
                for row in cursor.fetchall():
                    messages.append({
                        'id': row['id'],
                        'type': row['message_type'],
                        'content': row['content'],
                        'sql_query': row['sql_query'],
                        'graph_data': row['graph_data'],
                        'created_at': row['created_at']
                    })
                
                logger.info(f"Messages récupérés: {len(messages)} pour conv {conversation_id}")
                return messages
                
        except Exception as e:
            logger.error(f"Erreur récupération messages conv {conversation_id}: {e}")
            return []
    
    def is_owner(self, conversation_id: int, user_id: int) -> bool:
        """Vérifie si l'utilisateur est propriétaire de la conversation"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT user_id FROM conversations 
                    WHERE id = ? AND is_deleted = 0
                ''', (conversation_id,))
                
                result = cursor.fetchone()
                return result and result[0] == user_id
                
        except Exception as e:
            logger.error(f"Erreur vérification propriété: {e}")
            return False
    
    def delete_conversation(self, conversation_id: int, user_id: int) -> bool:
        """Supprime une conversation (soft delete)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Vérifier la propriété et supprimer
                cursor.execute('''
                    UPDATE conversations 
                    SET is_deleted = 1, updated_at = ?
                    WHERE id = ? AND user_id = ? AND is_deleted = 0
                ''', (datetime.now(), conversation_id, user_id))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    logger.info(f"Conversation {conversation_id} supprimée pour user {user_id}")
                    return True
                else:
                    logger.warning(f"Impossible de supprimer conv {conversation_id} pour user {user_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"Erreur suppression conversation: {e}")
            return False
    
    def get_last_active_conversation(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Récupère la dernière conversation active d'un utilisateur"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT id, title, created_at, updated_at
                    FROM conversations
                    WHERE user_id = ? AND is_deleted = 0 AND is_active = 1
                    ORDER BY updated_at DESC
                    LIMIT 1
                ''', (user_id,))
                
                result = cursor.fetchone()
                if result:
                    return {
                        'id': result['id'],
                        'title': result['title'],
                        'created_at': result['created_at'],
                        'updated_at': result['updated_at']
                    }
                return None
                
        except Exception as e:
            logger.error(f"Erreur récupération dernière conversation: {e}")
            return None
    
    def _generate_title(self, first_message: str) -> str:
        """Génère un titre pour la conversation basé sur le premier message"""
        if not first_message:
            return "Nouvelle conversation"
        
        # Nettoyer et tronquer le message
        title = first_message.strip()
        if len(title) > 50:
            title = title[:47] + "..."
        
        return title or "Conversation sans titre"
    
    def cleanup_old_conversations(self, days: int = 90):
        """Nettoie les anciennes conversations supprimées"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM conversations 
                    WHERE is_deleted = 1 
                    AND updated_at < datetime('now', '-{} days')
                '''.format(days))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    logger.info(f"Nettoyage: {deleted_count} conversations supprimées définitivement")
                    
        except Exception as e:
            logger.error(f"Erreur nettoyage conversations: {e}")