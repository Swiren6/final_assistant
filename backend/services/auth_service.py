import json
import logging
from flask import current_app
from config.database import get_db  
import re
import MySQLdb.cursors

class AuthService:
    @staticmethod
    def parse_roles(raw_roles):
        current_app.logger.info(f"Raw roles received: {raw_roles} (type: {type(raw_roles)})")
        
        if raw_roles is None:
            return []
        
        if isinstance(raw_roles, list):
            return raw_roles
        
        try:
            if isinstance(raw_roles, str) and raw_roles.startswith('["') and raw_roles.endswith('"]'):
                parsed = json.loads(raw_roles)
                return parsed
            
            if isinstance(raw_roles, str):
                parsed = json.loads(raw_roles)
                return parsed if isinstance(parsed, list) else [parsed]
                
        except json.JSONDecodeError as e:
            current_app.logger.warning(f"JSON decode failed: {str(e)}")
            return [raw_roles] if raw_roles else []
        
        return [raw_roles] if raw_roles else []
    
    

    @staticmethod
    def authenticate_user(login_identifier, password):
        connection = None
        cursor = None
        
        try:
            current_app.logger.info(f"🔍 Tentative authentification: {login_identifier}")
            
            connection = get_db()
            
            if connection is None:
                current_app.logger.error("❌ Impossible d'obtenir une connexion DB")
                return None
                
            cursor = connection.cursor(MySQLdb.cursors.DictCursor)

            current_app.logger.debug("✅ Curseur DB créé")

            # ✅ Requête avec logging
            query = """
                SELECT idpersonne, email, roles, changepassword 
                FROM user 
                WHERE email = %s OR idpersonne = %s
            """
            cursor.execute(query, (login_identifier, login_identifier))
            current_app.logger.debug(f"✅ Requête exécutée: {query}")

            user = cursor.fetchone()
            current_app.logger.debug(f"✅ Résultat DB: {'Utilisateur trouvé' if user else 'Aucun utilisateur'}")

            if not user:
                current_app.logger.warning(f"❌ Utilisateur non trouvé: {login_identifier}")
                return None

            roles = AuthService.parse_roles(user['roles'])

            current_app.logger.info(f"✅ Utilisateur authentifié: {user['idpersonne']} avec rôles: {roles}")
            
            return {
                'idpersonne': user['idpersonne'],
                'email': user['email'],
                'roles': roles,
                'changepassword': user['changepassword']
            }

        except Exception as e:
            current_app.logger.error(f"❌ Erreur authentification: {str(e)}")
            return None
