Documentation – assistant.py
Introduction
### SQLAssistant est une classe Python qui centralise toutes les fonctionnalités d’un assistant IA SQL :
**Analyse des questions utilisateurs
**Génération de requêtes SQL via LLM
**Validation et exécution sécurisée des requêtes
**Formatage des résultats (texte + graphiques)
**Gestion du cache pour éviter les recalculs
**Restrictions d’accès par rôle (admin/parent)

 ## 1. Méthodes de chargement sécurisé
               _safe_get_schema()
Récupère le schéma de la base via self.db.get_schema().
En cas d’erreur (connexion ou absence de DB), retourne une liste vide.
Utilisé à l’initialisation pour éviter un crash si la BDD est inaccessible.

                _safe_load_relations()
Lit le fichier prompts/relations.txt pour charger les relations entre tables.
Retourne un texte décrivant ces relations ou un message par défaut si absent.

                _safe_load_domain_descriptions()
Charge prompts/domain_descriptions.json contenant la description des domaines fonctionnels.
Retourne un dictionnaire {domaine: description}.
Gère erreurs de lecture ou JSON invalide.

                _safe_load_domain_to_tables_mapping()
Charge prompts/domain_tables_mapping.json qui mappe domaines → tables.
Retourne {domaine: [tables...]}.

                _safe_load_templates()
Charge templates_questions.json contenant des templates de questions avec leur SQL.
Valide la structure du JSON, filtre les templates incomplets et les enregistre dans template_matcher.

## 2. Interaction principale
                ask_question(question, user_id, roles)
Point d’entrée de l’assistant.
Vérifie si roles contient ROLE_SUPER_ADMIN ou ROLE_PARENT.
Oriente la requête vers :
_process_super_admin_question() si admin
_process_parent_question() si parent
Retourne (requête SQL, réponse formatée, graphique).

## 3. Traitement par rôle
                _process_super_admin_question(question)
Cherche dans le cache une requête déjà calculée pour la même question.
Sinon, cherche un template correspondant.
Sinon, génère le SQL avec IA via generate_sql_with_ai().
Exécute le SQL et formate la réponse.
Tente une correction auto _auto_correct_sql() si erreur.

                _process_parent_question(question, user_id)
Nettoie le cache spécifique parent.
Vérifie si la requête est déjà en cache.
Récupère la liste des enfants autorisés (get_user_children_detailed_data).
Analyse le contexte enfant dans la question (analyze_child_context_in_question).
Génère SQL avec restrictions (generate_sql_parent).
Valide l’accès aux données (validate_parent_access).
Exécute et formate la réponse.

## 4. Gestion des enfants (Parents)
                get_user_children_detailed_data(user_id)
Récupère via SQL les informations détaillées des enfants (nom, prénom, âge, classe…).
Filtre sur l’année scolaire en cours.

                handle_multiple_children_logic(question, children_data, user_id)
Détecte si la question concerne un enfant spécifique (nom, genre, âge…).
Demande clarification si ambigu.

                detect_names_in_question_improved(question, authorized_names, children_data)
Détecte les prénoms dans la question.
Sépare en autorisés / non autorisés.
Fournit des suggestions en cas de faute d’orthographe.

                analyze_child_context_in_question(question, children_data)
Analyse plus poussée :
Enfant nommé → process spécifique
Genre détecté → filtre
Âge (plus grand/petit) → sélection
Question générale → tous les enfants
Sinon → demande clarification

5. Génération de SQL
generate_sql_with_ai(question)
Identifie les domaines pertinents (get_relevant_domains).

Prépare un prompt ADMIN_PROMPT_TEMPLATE avec tables, relations, domaines.

Appelle ask_llm() pour générer du SQL.

Nettoie (_clean_sql) et valide (_validate_sql).

generate_sql_parent(question, user_id, children_ids_str, children_names_str)
Similaire mais utilise PARENT_PROMPT_TEMPLATE avec restrictions.

_clean_sql(text)
Supprime les balises sql et commentaires.

Retire le ; final.

_validate_sql(sql)
Refuse les requêtes dangereuses (drop, delete…).

Accepte uniquement SELECT.

_validate_sql_semantics(sql, question)
Vérifie que la requête interroge les tables cohérentes avec la question.

6. Exécution SQL
execute_sql_query(sql_query)
Exécute la requête SQL avec get_db().

Retourne {"success": bool, "data": [...]}.

Sérialise les dates, décimaux (_serialize_data).

_serialize_data(data)
Convertit les objets en formats compatibles JSON.

7. Formatage des réponses
format_response_with_ai(data, question, sql_query)
Si une seule valeur, retourne directement.

Sinon, appelle OpenAI pour formater le texte.

Fallback sur _format_simple_response si erreur.

_format_simple_response(data, question)
Utilise tabulate pour présenter les données sous forme de tableau.

8. Graphiques
generate_graph_if_relevant(data, question)
Si les données s’y prêtent, choisit un type de graphique (detect_graph_type) et appelle generate_auto_graph.

detect_graph_type(user_query, df_columns)
Détermine line, pie, bar selon mots-clés et structure.

generate_auto_graph(df, graph_type)
Crée le graphique Matplotlib.

Encode en Base64 pour affichage dans navigateur.

9. Correction automatique
_auto_correct_sql(bad_sql, error_msg)
Envoie à l’IA la requête et le message d’erreur.

Retourne la version corrigée si valide.

10. Utilitaires
get_relevant_domains(query, domain_descriptions)
Identifie les domaines pertinents via LLM.

get_relevant_domains_improved(query)
Version optimisée avec mapping direct avant fallback LLM.

get_tables_from_domains(domains, domain_to_tables_map)
Retourne toutes les tables liées aux domaines donnés.

find_matching_template(question)
Cherche correspondance exacte ou sémantique dans les templates.

_find_exact_template_match(question)
Recherche regex sur les templates.

_extract_variables(question, template)
Extrait les variables d’un template.

generate_query_from_template(template, variables)
Remplace les placeholders {var} dans un SQL template.

get_user_children_data(user_id)
Version simplifiée de récupération des enfants (id, prénom).




