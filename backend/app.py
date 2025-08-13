import os
import logging
from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from datetime import timedelta
from dotenv import load_dotenv
from config.database import get_db
# Chargement des variables d'environnement
load_dotenv()

# Configuration logging plus détaillée
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)

# Validation de la configuration
required_vars = ['MYSQL_HOST', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_DATABASE']
missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    logger.error(f"❌ Variables manquantes: {missing_vars}")
    exit(1)

# ✅ Affichage de la configuration (masquer le mot de passe)
logger.info(f"🔧 Configuration DB:")
logger.info(f"   Host: {os.getenv('MYSQL_HOST')}")
logger.info(f"   User: {os.getenv('MYSQL_USER')}")
logger.info(f"   Database: {os.getenv('MYSQL_DATABASE')}")
logger.info(f"   Password: {'*' * len(os.getenv('MYSQL_PASSWORD', ''))}")

def create_app():
    """Factory pour créer l'application Flask"""
    app = Flask(__name__)
    
    # 🔧 Configuration JWT - CRITIQUE
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'dev-secret-key-2025')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
    app.config['JWT_TOKEN_LOCATION'] = ['headers']
    app.config['JWT_HEADER_NAME'] = 'Authorization'
    app.config['JWT_HEADER_TYPE'] = 'Bearer'
    
    jwt = JWTManager(app)
    
    # 🔧 Gestion d'erreur JWT
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "Token expired"}), 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({"error": "Invalid token"}), 401
    
    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({"error": "Token required"}), 401
    
    # Configuration CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": ["*"],
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    
    # ✅ Initialisation base de données avec test
    logger.info("🔄 Initialisation de la base de données...")
    try:
        from config.database import init_db
        db = init_db(app)
        logger.info("✅ Base de données initialisée avec succès")
    except Exception as e:
        logger.error(f"❌ Erreur initialisation DB: {e}")
        raise
    
    # Enregistrement des routes
    from routes.auth import auth_bp
    from routes.agent import agent_bp
    from routes.notifications import notifications_bp
    from routes.api_routes_history import history_bp

    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(agent_bp, url_prefix='/api')
    app.register_blueprint(notifications_bp, url_prefix='/api')
    app.register_blueprint(history_bp, url_prefix='/api')


    
    @app.route('/api/test-mysql')
    def test_mysql():
        try:
            conn = get_db()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT 1 as test, NOW() as time")
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            return {"status": "OK", "result": result}
        except Exception as e:
            return {"error": str(e)}, 500
        # Route de santé avec test DB
    @app.route('/api/health')
    def health():
        try:
            from config.database import get_db
            conn = get_db()
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 as test")
                result = cursor.fetchone()
                cursor.close()
                if hasattr(conn, '_direct_connection'):
                    conn.close()
                return {"status": "OK", "database": "Connected", "test": result}
            else:
                return {"status": "OK", "database": "Disconnected"}, 503
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return {"status": "ERROR", "database": str(e)}, 503
    
    # @app.route('/api/notifications', methods=['GET'])
    # def check_exam_notifications():
    #     conn = None
    #     cursor = None
    #     try:
    #         conn = get_db()
    #         cursor = conn.cursor(dictionary=True)
            
    #         cursor.execute("SELECT * FROM notification_queue WHERE seen = 0")
    #         notifications_non_vues = cursor.fetchall()

    #         messages = [{"id": notif["id"], "message": notif["message"]} 
    #                 for notif in notifications_non_vues]

    #         if notifications_non_vues:
    #             ids = [str(notif['id']) for notif in notifications_non_vues]
    #             format_strings = ",".join(["%s"] * len(ids))
    #             update_query = f"UPDATE notification_queue SET seen = 1 WHERE id IN ({format_strings})"
    #             cursor.execute(update_query, ids)
    #             conn.commit()

    #         return jsonify(messages)

    #     except Exception as e:
    #         if conn:
    #             conn.rollback()
    #         return jsonify({"error": str(e)}), 500

    #     finally:
    #         if cursor:
    #             cursor.close()
    #         if conn:
    #             conn.close()

    #Route de test d'authentification
    @app.route('/api/test-db')
    def test_db():
        try:
            from config.database import get_db
            conn = get_db()
            if not conn:
                return {"error": "No database connection"}, 500
                
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM user")
            result = cursor.fetchone()
            cursor.close()
            
            if hasattr(conn, '_direct_connection'):
                conn.close()
                
            return {"status": "OK", "user_count": result['count']}
        except Exception as e:
            logger.error(f"❌ DB test failed: {e}")
            return {"error": str(e)}, 500
    
    return app
        
def main():
    """Point d'entrée principal"""
    # Création de l'application
    app = create_app()
    
    logger.info("🚀 Assistant Scolaire - Backend démarré")
    logger.info(f"📍 URL: http://localhost:5000")
    logger.info(f"🏥 Health: http://localhost:5000/api/health")
    logger.info(f"🧪 Test DB: http://localhost:5000/api/test-db")
    
    # Démarrage du serveur
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        logger.info("👋 Serveur arrêté")

if __name__ == "__main__":
    main()