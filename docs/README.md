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
│   │   ├──cache_manager.py       #gestion de cache de l'admin
│   │   ├──cache_manager1.py      #gestion de cache du parent
│   │   ├──llm_utils.py
│   │   ├──sql_query_cache.json    #cache de l'admin
│   │   ├──sql_query_cache1.json   #cache de parent
│   │   ├──templates_questions.json #requetes sql compliquees 
│   │   ├── pdf_utils/
|   |   |   ├── attestation.py      #
|   |   |   ├── fonts/              #contient les fonts d'ecriture 
│   │   ├── static/                 #contient les pdfs 
│   │   ├── security/
|   |   |   ├── roles.py
│   │   ├── prompts/
|   |   |   ├── domain_description.json
|   |   |   ├── domain_tables_mapping.json
|   |   |   ├── templates.py
│   │   └── template_matcher
|   |   |   ├── matcher.py
│   └── utils/
│       ├── jwt_utils.py          # Utilitaires JWT
│       └── sql_utils.py          # Utilitaires SQL
├── frontend/
│   ├── lib/
│   │   ├── main.dart
│   │   ├── models/
│   │   │   ├── conversation_model.dart
│   │   │   ├── user_model.dart
│   │   │   └── message_model.dart
│   │   ├── screens/
│   │   │   ├── login_screen.dart
│   │   │   ├── chat_screen.dart
│   │   │   └── notification_checker.dart
│   │   ├── services/
│   │   │   ├── auth_service.dart
│   │   │   ├── api_service.dart
│   │   │   └── storage_service.dart
│   │   ├── widgets/
│   │   │   ├── custom_appbar.dart
│   │   │   ├── message_bubble.dart
│   │   │   └── sidebar_menu.dart
│   │   │   └── history_sidebar.dart
│   │   │   └── graph_widget.dart
│   │   └── utils/
│   │       ├── constants.dart
│   │       └── theme.dart
│   ├── pubspec.yaml
│   ├── assets/
│   │   └── logo.png
└── docs/
    ├── API.md
    ├── INSTALL.md
    └── README.md
    └── assistant.md