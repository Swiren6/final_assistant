structure du Projet Assistant Scolaire
assistant_scolaire/
├── backend/
│   ├── app.py                    # Serveur Flask principal
│   ├── requirements.txt          # Dépendances Python
│   ├── .env                      # Variables d'environnement
│   ├── config/
│   │   └── database.py           # Configuration base de données
│   ├── models/
│   │   ├── user.py               # Modèle utilisateur
│   │   └── message.py            # Modèle message
│   ├── routes/
│   │   ├── auth.py               # Routes d'authentification
│   │   ├── notifications.py      # Routes de notifications
│   │   └── agent.py               # Routes de chat
│   ├── services/
│   │   ├── auth_service.py       # Service d'authentification
|   ├──agent/
│   │   ├──assistant.py
│   │   ├──sql_agent.py
│   │   ├──cache_manager.py
│   │   ├──llm_utils.py
│   │   ├──sql_query_cache.json
│   │   ├──templates_questions.json
│   │   ├── pdf_utils/
|   |   |   ├── attestation.py
|   |   |   ├── bulletin.py
|   |   |   ├── fonts/ #contient les fonts d'ecriture 
│   │   ├── static/ #contient les pdfs 
│   │   ├── prompts/
|   |   |   ├── domain_description.json
|   |   |   ├── domain_tables_mapping.json
|   |   |   ├── prompt_eleve.txt
|   |   |   ├── prompt_finance.txt
|   |   |   ├── prompt_inscriptions.txt
|   |   |   ├── prompt_pedagogie.txt
|   |   |   ├── relation.txt
│   │   └── template_matcher
|   |   |   ├── matcher.py
│   └── utils/
│       ├── jwt_utils.py          # Utilitaires JWT
│       └── sql_utils.py          # Utilitaires SQL
├── frontend/
│   ├── lib/
│   │   ├── main.dart
│   │   ├── models/
│   │   │   ├── user_model.dart
│   │   │   └── message_model.dart
│   │   ├── screens/
│   │   │   ├── login_screen.dart
│   │   │   ├── chat_screen.dart
│   │   │   └── home_screen.dart
│   │   ├── services/
│   │   │   ├── auth_service.dart
│   │   │   ├── api_service.dart
│   │   │   └── storage_service.dart
│   │   ├── widgets/
│   │   │   ├── custom_appbar.dart
│   │   │   ├── message_bubble.dart
│   │   │   └── sidebar_menu.dart
│   │   └── utils/
│   │       ├── constants.dart
│   │       └── theme.dart
│   ├── pubspec.yaml
│   ├── assets/
│   │   └── logo.png
│   └── android/
└── docs/
    ├── API.md
    ├── INSTALL.md
    └── README.md