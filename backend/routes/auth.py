from flask_jwt_extended import jwt_required, get_jwt
from flask import Blueprint, jsonify, request, Response,g
from flask_jwt_extended import create_access_token
import json
import logging
from services.auth_service import AuthService

auth_bp = Blueprint('auth', __name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)



@auth_bp.route('/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        response = jsonify({"status": "preflight"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "*")
        response.headers.add("Access-Control-Allow-Methods", "*")
        return response

    try:
        data = request.get_json()
        logger.debug(f"Received data: {data}")  # Log les données reçues
        
        if not data:
            logger.error("No data received")
            return jsonify({"error": "No data received"}), 400

        login_identifier = data.get('login_identifier')
        password = data.get('password')
        
        if not login_identifier or not password:
            logger.error("Missing login_identifier or password")
            return jsonify({"error": "Missing login_identifier or password"}), 400

        # Authentification via le service
        user = AuthService.authenticate_user(login_identifier, password)
        logger.debug(f"User from AuthService: {user}")  # Log le résultat de l'authentification
        if not user:
            logger.error("Invalid credentials")
            return jsonify({"message": "Invalid credentials"}), 401
        
        identity = str(user['idpersonne'])
        # Création du token
        token_data = {
            'idpersonne': user['idpersonne'],
            'roles': user['roles'],
            'changepassword': user['changepassword']
        }

        access_token = create_access_token(identity=identity,additional_claims=token_data)

        # Construction de la réponse
        response_data = {
            'token': access_token,
            'idpersonne': user['idpersonne'],
            'roles': user['roles'],
            'changepassword': user['changepassword']
        }
        return Response(
            response=json.dumps(response_data, ensure_ascii=False),
            status=200,
            mimetype='application/json'
        )

    except Exception as e:
        logger.error(f"Error during login: {str(e)}", exc_info=True)  
        return jsonify({"error": str(e)}), 500
    
@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    jti = get_jwt()['jti']
    
    return jsonify({
        "message": "Déconnexion réussie",
        "status": "success"
    }), 200