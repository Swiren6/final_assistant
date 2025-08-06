from flask import Blueprint, jsonify, request, Response
from flask_jwt_extended import create_access_token
import json
from services.auth_service import AuthService

auth_bp = Blueprint('auth', __name__)

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
        
        if not data:
            return jsonify({"error": "No data received"}), 400

        login_identifier = data.get('login_identifier')
        password = data.get('password')
        
        # Authentification via le service
        user = AuthService.authenticate_user(login_identifier, password)
        
        if not user:
            return jsonify({"message": "Invalid credentials"}), 401

        # Création du token
        token_data = {
            'idpersonne': user['idpersonne'],
            'roles': user['roles'],
            'changepassword': user['changepassword']
        }

        access_token = create_access_token(identity=token_data)

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
        return jsonify({"error": "Server error"}), 500