flowchart TD
A[assistant.ask_question(question, user_id, roles)] --> B{ROLE_SUPER_ADMIN ?}
B -->|Oui| C[_process_super_admin_question()]
B -->|Non et ROLE_PARENT| D[_process_parent_question()]
B -->|Sinon| Z[Retour "Accès refusé"]

%% --- ADMIN ---
C --> C1{Question en cache ?}
C1 -->|Oui| C2[Retour résultat cache]
C1 -->|Non| C3{Template correspondant ?}
C3 -->|Oui| C4[Générer SQL depuis template]
C3 -->|Non| C5[generate_sql_with_ai()]
C4 --> C6[execute_sql_query()]
C5 --> C6
C6 -->|Succès| C7[generate_graph_if_relevant()]
C7 --> C8[format_response_with_ai()]
C6 -->|Erreur| C9[_auto_correct_sql()]
C9 -->|Corrigé| C6
C8 --> R1[(Réponse texte + Graph)]

%% --- PARENT ---
D --> D1[Nettoyage cache parent]
D1 --> D2{Question en cache ?}
D2 -->|Oui| D3[Retour résultat cache]
D2 -->|Non| D4[get_user_children_detailed_data()]
D4 --> D5[analyze_child_context_in_question()]
D5 -->|Enfant clair| D6[generate_sql_parent()]
D5 -->|Ambigu| D10[Retour 'clarification_needed']
D6 --> D7[validate_parent_access()]
D7 -->|Autorisé| D8[execute_sql_query()]
D8 -->|Succès| D9[generate_graph_if_relevant()]
D9 --> D11[format_response_with_ai()]
D8 -->|Erreur| E1[Retour erreur SQL]
D11 --> R1
D10 --> R2[(Demande précision)]

%% --- SORTIE ---
R1 --> F[Retour (SQL, Réponse, Graph)]
R2 --> F
Z --> F
