import openai
import logging
import re
import json
import io
import base64
import os
from functools import lru_cache
from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path

# Imports database
from config.database import get_db_connection, get_db, CustomSQLDatabase, get_db_cursor,get_schema

# Imports agent modules
from agent.llm_utils import ask_llm 
from langchain.prompts import PromptTemplate
from agent.template_matcher.matcher import SemanticTemplateMatcher
from agent.cache_manager import CacheManager
from agent.cache_manager1 import CacheManager1
from agent.pdf_utils.bulletin import export_bulletin_pdf
from agent.pdf_utils.attestation import PDFGenerator

# Imports security and templates
from agent.prompts.templates import PROMPT_TEMPLATE, ADMIN_PROMPT_TEMPLATE, PARENT_PROMPT_TEMPLATE
from security.roles import is_super_admin, is_parent, validate_parent_access, is_admin, validate_admin_access

# Imports for graphs and data processing
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from tabulate import tabulate
import MySQLdb
import traceback

from agent.conversation_history import ConversationHistory

# Configure matplotlib for server environment
matplotlib.use('Agg')  
plt.switch_backend('Agg')

# Configure logging
logger = logging.getLogger(__name__)

class SQLAssistant:
    """
    Assistant SQL unifié combinant les fonctionnalités de SQLAssistant et SQLAgent
    Capable de générer du SQL, exécuter les requêtes, créer des graphiques et répondre en langage naturel
    """
    
    def __init__(self, db=None, model="gpt-4o", temperature=0.3, max_tokens=500):
        # Configuration base
        self.db = db if db is not None else get_db_connection()
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Historique et cache
        self.last_generated_sql = ""
        self.query_history = []
        self.conversation_history = []
        self.cache = CacheManager()
        self.cache1 = CacheManager1()
        
        # Configuration des coûts et schéma
        self.cost_per_1k_tokens = 0.005
        self.schema = self._safe_get_schema()
        
        # Chargement des configurations
        self.relations_description = self._safe_load_relations()
        self.domain_descriptions = self._safe_load_domain_descriptions()
        self.domain_to_tables_mapping = self._safe_load_domain_to_tables_mapping()
        self.ask_llm = ask_llm
        
        # Template matcher et templates questions
        self.template_matcher = SemanticTemplateMatcher()
        self.templates_questions = self._safe_load_templates()
        self.last_generated_sql = ""
        self.query_history = []
        self.conversation_history_old = []  # Renommer pour éviter confusion

        
        # 🆕 NOUVEAU : Gestionnaire d'historique persistant
        self.conversation_manager = ConversationHistory()
        
        logger.info("✅ SQLAssistant initialisé avec succès")

    # ================================
    # MÉTHODES DE CHARGEMENT SÉCURISÉES
    # ================================
    
    def _safe_get_schema(self):
        """Récupère le schéma de base de données de manière sécurisée"""
        try:
            return self.db.get_schema() if self.db else []
        except Exception as e:
            logger.warning(f"⚠️ Impossible de récupérer le schéma: {e}")
            return []

    def _safe_load_relations(self) -> str:
        """Charge les relations avec gestion d'erreurs"""
        try:
            relations_path = Path(__file__).parent  / 'prompts' / 'relations.txt'
            if relations_path.exists():
                return relations_path.read_text(encoding='utf-8')
            logger.warning("⚠️ Fichier relations.txt non trouvé")
            return "# Aucune relation définie"
        except Exception as e:
            logger.error(f"❌ Erreur chargement relations: {e}")
            return "# Erreur chargement relations"

    def _safe_load_domain_descriptions(self) -> dict:
        """Charge les descriptions de domaine avec gestion d'erreurs"""
        try:
            domain_path = Path(__file__).parent  / 'prompts' / 'domain_descriptions.json'
            if domain_path.exists():
                with open(domain_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            logger.warning("⚠️ Fichier domain_descriptions.json non trouvé")
            return {}
        except Exception as e:
            logger.error(f"❌ Erreur chargement domain descriptions: {e}")
            return {}

    def _safe_load_domain_to_tables_mapping(self) -> dict:
        """Charge le mapping domaine-tables avec gestion d'erreurs"""
        try:
            mapping_path = Path(__file__).parent   / 'prompts' / 'domain_tables_mapping.json'
            if mapping_path.exists():
                with open(mapping_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            logger.warning("⚠️ Fichier domain_tables_mapping.json non trouvé")
            return {}
        except Exception as e:
            logger.error(f"❌ Erreur chargement domain mapping: {e}")
            return {}

    def _safe_load_templates(self) -> list:
        """Charge les templates de questions avec gestion d'erreurs"""
        try:
            templates_path = Path(__file__).parent/ 'templates_questions.json'
            
            if not templates_path.exists():
                logger.info(f"⚠️ Fichier non trouvé, création: {templates_path}")
                templates_path.write_text('{"questions": []}', encoding='utf-8')
                return []

            content = templates_path.read_text(encoding='utf-8').strip()
            if not content:
                logger.warning("⚠️ Fichier vide, réinitialisation")
                templates_path.write_text('{"questions": []}', encoding='utf-8')
                return []

            try:
                data = json.loads(content)
                if not isinstance(data.get("questions", []), list):
                    raise ValueError("Format invalide: 'questions' doit être une liste")
                
                valid_templates = []
                for template in data["questions"]:
                    if all(key in template for key in ["template_question", "requete_template"]):
                        valid_templates.append(template)
                    else:
                        logger.warning(f"⚠️ Template incomplet ignoré: {template.get('description', 'sans description')}")
                
                if valid_templates:
                    self.template_matcher.load_templates(valid_templates)
                    logger.info(f"✅ {len(valid_templates)} templates chargés")
                
                return valid_templates

            except json.JSONDecodeError as e:
                logger.error(f"❌ Fichier JSON corrompu, réinitialisation. Erreur: {e}")
                backup_path = templates_path.with_suffix('.bak.json')
                templates_path.rename(backup_path)
                templates_path.write_text('{"questions": []}', encoding='utf-8')
                return []

        except Exception as e:
            logger.error(f"❌ Erreur critique lors du chargement: {e}")
            return []

    # ================================
    # MÉTHODES PRINCIPALES D'INTERACTION
    # ================================

    
    # def ask_question(self, question: str, user_id: Optional[int] = None, roles: Optional[List[str]] = None) -> tuple[str, str, Optional[str]]:
    #     """
    #     Point d'entrée principal pour poser une question
    #     Retourne (sql_query, formatted_response, graph_data)
    #     """
    #     if user_id is None:
    #         user_id = 0
    #     if roles is None:
    #         roles = []

    #     # Validation des rôles
    #     if not roles:
    #         return "", "❌ Accès refusé : Aucun rôle fourni", None
        
    #     valid_roles = ['ROLE_SUPER_ADMIN', 'ROLE_PARENT']
    #     has_valid_role = any(role in valid_roles for role in roles)
        
    #     if not has_valid_role:
    #         return "", f"❌ Accès refusé : Rôles fournis {roles}, requis {valid_roles}", None

    #     # Traitement par rôle
    #     try:
    #         if 'ROLE_SUPER_ADMIN' in roles:
    #             return self._process_super_admin_question(question)  # Retourne 3 valeurs
    #         elif 'ROLE_PARENT' in roles:
    #             return self._process_parent_question(question, user_id)  # Retourne 3 valeurs
    #     except Exception as e:
    #         logger.error(f"Erreur dans ask_question: {e}")
    #         return "", f"❌ Erreur : {str(e)}", None

    def ask_question_with_history(self, question: str, user_id: Optional[int] = None, 
                                 roles: Optional[List[str]] = None, 
                                 conversation_id: Optional[int] = None) -> tuple[str, str, Optional[str], int]:
        """
        Version améliorée qui sauvegarde automatiquement dans l'historique
        Retourne (sql_query, formatted_response, graph_data, conversation_id)
        """
        if user_id is None:
            user_id = 0
        if roles is None:
            roles = []

        # Validation des rôles (identique à la version existante)
        if not roles:
            return "", "❌ Accès refusé : Aucun rôle fourni", None, 0
        
        valid_roles = ['ROLE_SUPER_ADMIN', 'ROLE_PARENT']
        has_valid_role = any(role in valid_roles for role in roles)
        
        if not has_valid_role:
            return "", f"❌ Accès refusé : Rôles fournis {roles}, requis {valid_roles}", None, 0

        try:
            # 🆕 GESTION DE LA CONVERSATION
            if conversation_id is None:
                conversation_id = self.conversation_manager.create_conversation(user_id, question)
            
            # Sauvegarder la question utilisateur
            self.conversation_manager.add_message(conversation_id, 'user', question)

            # Traitement par rôle (utiliser les méthodes existantes)
            if 'ROLE_SUPER_ADMIN' in roles:
                sql_query, formatted_response, graph_data = self._process_super_admin_question(question)
            elif 'ROLE_PARENT' in roles:
                sql_query, formatted_response, graph_data = self._process_parent_question(question, user_id)
            
            # 🆕 SAUVEGARDER LA RÉPONSE ASSISTANT
            self.conversation_manager.add_message(
                conversation_id, 
                'assistant', 
                formatted_response, 
                sql_query, 
                graph_data
            )
            
            logger.info(f"✅ Question traitée et sauvegardée - Conversation {conversation_id}")
            return sql_query, formatted_response, graph_data, conversation_id
            
        except Exception as e:
            logger.error(f"Erreur dans ask_question_with_history: {e}")
            error_message = f"❌ Erreur : {str(e)}"
            
            # Sauvegarder l'erreur aussi
            if conversation_id:
                self.conversation_manager.add_message(conversation_id, 'system', error_message)
            
            return "", error_message, None, conversation_id or 0

    
    def _process_super_admin_question(self, question: str) -> tuple[str, str, Optional[str]]:
        """Traite une question avec accès admin complet - CORRIGÉ POUR RETOURNER 3 VALEURS"""
        
        # 1. Vérifier le cache
        cached = self.cache.get_cached_query(question)
        if cached:
            sql_template, variables = cached
            sql_query = sql_template
            for column, value in variables.items():
                sql_query = sql_query.replace(f"{{{column}}}", value)
            
            logger.info("⚡ Requête admin récupérée depuis le cache")
            try:
                result = self.execute_sql_query(sql_query)
                if result['success']:
                    # 🎯 GÉNÉRATION DE GRAPHIQUE POUR CACHE
                    graph_data = self.generate_graph_if_relevant(result['data'], question)
                    formatted_result = self.format_response_with_ai(result['data'], question, sql_query)
                    return sql_query, formatted_result, graph_data  # 🎯 3 VALEURS
                else:
                    return sql_query, f"❌ Erreur d'exécution SQL : {result['error']}", None
            except Exception as db_error:
                return sql_query, f"❌ Erreur d'exécution SQL : {str(db_error)}", None
        
        # 2. Vérifier les templates existants
        template_match = self.find_matching_template(question)
        if template_match:
            logger.info("🔍 Template admin trouvé")
            sql_query = self.generate_query_from_template(
                template_match["template"],
                template_match["variables"]
            )
            try:
                result = self.execute_sql_query(sql_query)
                if result['success']:
                    # 🎯 GÉNÉRATION DE GRAPHIQUE POUR TEMPLATE
                    graph_data = self.generate_graph_if_relevant(result['data'], question)
                    formatted_result = self.format_response_with_ai(result['data'], question, sql_query)
                    return sql_query, formatted_result, graph_data  # 🎯 3 VALEURS
                else:
                    return sql_query, f"❌ Erreur d'exécution SQL : {result['error']}", None
            except Exception as db_error:
                return sql_query, f"❌ Erreur d'exécution SQL : {str(db_error)}", None
        
        # 3. Génération AI + exécution + formatage
        try:
            # 🎯 GÉNÉRATION SQL MANQUANTE - AJOUT ICI
            sql_query = self.generate_sql_with_ai(question)
            
            if not sql_query:
                return "", "❌ La requête générée est vide.", None
                
            result = self.execute_sql_query(sql_query)
            if result['success']:
                # 🎯 GÉNÉRATION DE GRAPHIQUE
                graph_data = self.generate_graph_if_relevant(result['data'], question)
                
                formatted_result = self.format_response_with_ai(result['data'], question, sql_query)
                self.cache.cache_query(question, sql_query)
                
                return sql_query, formatted_result, graph_data  # 🎯 3 VALEURS
            else:
                # Tentative de correction automatique
                corrected_sql = self._auto_correct_sql(sql_query, result['error'])
                if corrected_sql:
                    retry_result = self.execute_sql_query(corrected_sql)
                    if retry_result['success']:
                        graph_data = self.generate_graph_if_relevant(retry_result['data'], question)
                        formatted_result = self.format_response_with_ai(retry_result['data'], question, corrected_sql)
                        return corrected_sql, formatted_result, graph_data  # 🎯 3 VALEURS
                
                return sql_query, f"❌ Erreur d'exécution SQL : {result['error']}", None
            
        except Exception as e:
            logger.error(f"Erreur dans _process_super_admin_question: {e}")
            return "", f"❌ Erreur de traitement : {str(e)}", None    
    
    def _process_parent_question(self, question: str, user_id: int) -> tuple[str, str, Optional[str]]:
        """Traite une question avec restrictions parent - CORRIGÉ POUR RETOURNER 3 VALEURS"""
        
        # Nettoyage du cache
        self.cache1.clean_double_braces_in_cache()
        
        # Vérification cache parent
        cached = self.cache1.get_cached_query(question, user_id)
        if cached:
            sql_template, variables = cached
            sql_query = sql_template
            for column, value in variables.items():
                sql_query = sql_query.replace(f"{{{column}}}", value)
            
            logger.info("⚡ Requête parent récupérée depuis le cache")
            try:
                result = self.execute_sql_query(sql_query)
                if result['success']:
                    # 🎯 GÉNÉRATION DE GRAPHIQUE POUR CACHE
                    graph_data = self.generate_graph_if_relevant(result['data'], question)
                    formatted_result = self.format_response_with_ai(result['data'], question, sql_query)
                    return sql_query, formatted_result, graph_data  # 🎯 3 VALEURS
                else:
                    return sql_query, f"❌ Erreur d'exécution SQL : {result['error']}", None
            except Exception as db_error:
                return sql_query, f"❌ Erreur d'exécution SQL : {str(db_error)}", None

        # Récupération des données enfants
        children_ids, children_prenoms = self.get_user_children_data(user_id)
        children_ids_str = ", ".join(map(str, children_ids))
        children_names_str = ", ".join(children_prenoms)
        
        if not children_ids:
            return "", "❌ Aucun enfant trouvé pour ce parent ou erreur d'accès.", None
        
        logger.info(f"🔒 Restriction parent - Enfants autorisés: {children_ids}")

        # Validation des noms dans la question
        detected_names = self.detect_names_in_question(question, children_prenoms)
        if detected_names["unauthorized_names"]:
            unauthorized_list = ", ".join(detected_names["unauthorized_names"])
            return "", f"❌ Accès interdit: Vous n'avez pas le droit de consulter les données de {unauthorized_list}", None
        
        # Génération SQL avec template parent
        try:
            sql_query = self.generate_sql_parent(question, user_id, children_ids_str, children_names_str)
            
            if not sql_query:
                return "", "❌ La requête générée est vide.", None

            # Validation de sécurité (sauf pour infos publiques)
            if not self._is_public_info_query(question, sql_query):
                if not self.validate_parent_access(sql_query, children_ids):
                    return "", "❌ Accès refusé: La requête ne respecte pas les restrictions parent.", None
            else:
                logger.info("ℹ️ Question sur information publique - validation bypassée")

            # Exécution
            result = self.execute_sql_query(sql_query)
            
            if result['success']:
                # 🎯 GÉNÉRATION DE GRAPHIQUE
                graph_data = self.generate_graph_if_relevant(result['data'], question)
                formatted_result = self.format_response_with_ai(result['data'], question, sql_query)
                self.cache1.cache_query(question, sql_query)
                return sql_query, formatted_result, graph_data  # 🎯 3 VALEURS
            else:
                return sql_query, f"❌ Erreur d'exécution SQL : {result['error']}", None
                
        except Exception as e:
            logger.error(f"Erreur dans _process_parent_question: {e}")
            return "", f"❌ Erreur de traitement : {str(e)}", None
    
    # ================================
    # GÉNÉRATION SQL
    # ================================

    def generate_sql_with_ai(self, question: str) -> str:
        """Génère une requête SQL via IA pour admin"""
        relevant_domains = self.get_relevant_domains(question, self.domain_descriptions)
        
        if relevant_domains:
            relevant_tables = self.get_tables_from_domains(relevant_domains, self.domain_to_tables_mapping)
            table_info = self.db.get_table_info(relevant_tables)
            relevant_domain_descriptions = "\n".join(
                f"{dom}: {self.domain_descriptions[dom]}" for dom in relevant_domains if dom in self.domain_descriptions
            )
        else:
            table_info = self.db.get_table_info()
            relevant_domain_descriptions = "\n".join(self.domain_descriptions.values())

        prompt = ADMIN_PROMPT_TEMPLATE.format(
            input=question,
            table_info=table_info,
            relevant_domain_descriptions=relevant_domain_descriptions,
            relations=self.relations_description
        )

        llm_response = self.ask_llm(prompt)
        sql_query = self._clean_sql(llm_response)
        sql_query = self._auto_fix_quotes_in_sql(sql_query)
        
        # Validation
        try:
            self._validate_sql(sql_query)
            self.last_generated_sql = sql_query
            return sql_query
        except Exception as e:
            logger.error(f"Erreur validation SQL: {e}")
            raise ValueError(f"Requête SQL invalide: {str(e)}")

    def generate_sql_parent(self, question: str, user_id: int, children_ids_str: str, children_names_str: str) -> str:
        """Génère une requête SQL avec restrictions parent"""
        relevant_domains = self.get_relevant_domains(question, self.domain_descriptions)
        
        if relevant_domains:
            relevant_tables = self.get_tables_from_domains(relevant_domains, self.domain_to_tables_mapping)
            table_info = self.db.get_table_info(relevant_tables)
            relevant_domain_descriptions = "\n".join(
                f"{dom}: {self.domain_descriptions[dom]}" for dom in relevant_domains if dom in self.domain_descriptions
            )
        else:
            table_info = self.db.get_table_info()
            relevant_domain_descriptions = "\n".join(self.domain_descriptions.values())

        prompt = PARENT_PROMPT_TEMPLATE.format(
            input=question,
            table_info=table_info,
            relevant_domain_descriptions=relevant_domain_descriptions,
            relations=self.relations_description,
            user_id=user_id,
            children_ids=children_ids_str,
            children_names=children_names_str
        )
        
        llm_response = self.ask_llm(prompt)
        sql_query = self._clean_sql(llm_response)
        
        # Validation
        try:
            self._validate_sql(sql_query)
            self.last_generated_sql = sql_query
            return sql_query
        except Exception as e:
            logger.error(f"Erreur validation SQL parent: {e}")
            raise ValueError(f"Requête SQL invalide: {str(e)}")

    def _clean_sql(self, text: str) -> str:
        """Nettoie et extrait le SQL du texte généré par l'IA"""
        if not text:
            return ""
        
        sql = re.sub(r'```(sql)?|```', '', text)
        sql = re.sub(r'(?i)^\s*(?:--|#).*$', '', sql, flags=re.MULTILINE)
        return sql.strip().rstrip(';')

    
    def _validate_sql(self, sql: str) -> bool:
        """Valide la syntaxe SQL et vérifie la sécurité"""
        if not sql:
            raise ValueError("❌ Requête SQL vide")
            
        sql_lower = sql.lower()

        # Protection contre les requêtes destructives
        forbidden_keywords = ['drop', 'delete', 'update', 'insert', ';--', 'exec', 'truncate']
        if any(keyword in sql_lower for keyword in forbidden_keywords):
            raise ValueError("❌ Commande SQL dangereuse détectée")

        # Vérification que c'est bien une requête SELECT
        if not sql_lower.strip().startswith('select'):
            raise ValueError("❌ Seules les requêtes SELECT sont autorisées")

        # ✅ SUPPRIME LA VALIDATION EXPLAIN QUI CAUSE LE PROBLÈME
        # L'exécution réelle se fera dans execute_sql_query() qui gère mieux les erreurs
        
        return True
    
    def _validate_sql_semantics(self, sql: str, question: str) -> bool:
        """Valide la cohérence sémantique entre question et SQL"""
        
        # Mappings question → table attendue
        expected_mappings = {
            'section': ['section'],
            'civilité': ['civilite'],
            'nationalité': ['nationalite'],
            'niveau': ['niveau'],
            'élève': ['eleve', 'personne', 'inscriptioneleve'],
            'classe': ['classe'],
            'localité': ['localite']
        }
        
        question_lower = question.lower()
        sql_lower = sql.lower()
        
        # Vérifier que les tables correspondent à la question
        for keyword, expected_tables in expected_mappings.items():
            if keyword in question_lower:
                if not any(table in sql_lower for table in expected_tables):
                    raise ValueError(f"Question sur '{keyword}' mais table correspondante absente")
        
        return True
    
    # ================================
    # EXÉCUTION SQL
    # ================================
    def execute_sql_query(self, sql_query: str) -> dict:
        """Exécute une requête SQL et retourne les résultats"""
        try:
            if not sql_query:
                return {"success": False, "error": "Requête SQL vide", "data": []}
            
            # ✅ FIX: Utiliser directement get_db() au lieu de CustomSQLDatabase
            connection = get_db()
            cursor = connection.cursor()
            
            logger.debug(f"🔍 Exécution SQL: {sql_query}")
            cursor.execute(sql_query)
            
            # ✅ FIX: Récupération correcte des colonnes et données
            columns = [desc[0] for desc in cursor.description]
            results = cursor.fetchall()
            
            logger.debug(f"🔍 Colonnes: {columns}")
            logger.debug(f"🔍 Résultats bruts: {results}")
            
            # ✅ FIX: Construction correcte des dictionnaires
            data = []
            for row in results:
                if isinstance(row, dict):
                    # Si row est déjà un dict (DictCursor)
                    data.append(row)
                else:
                    # Si row est un tuple, créer le dict
                    data.append(dict(zip(columns, row)))
            
            logger.debug(f"🔍 Données finales: {data}")
            
            cursor.close()
            
            # Fermer la connexion si c'est une connexion directe
            if hasattr(connection, '_direct_connection'):
                connection.close()
            
            # Sérialiser les données
            serialized_data = self._serialize_data(data)
            
            return {"success": True, "data": serialized_data}
            
        except Exception as e:
            logger.error(f"❌ Erreur exécution SQL: {e}")
            logger.error(f"❌ SQL qui a échoué: {sql_query}")
            return {"success": False, "error": str(e), "data": []}
    def _serialize_data(self, data):
        """Sérialise les données pour éviter les problèmes de types"""
        if isinstance(data, (list, tuple)):
            return [self._serialize_data(item) for item in data]
        elif isinstance(data, dict):
            return {key: self._serialize_data(value) for key, value in data.items()}
        elif hasattr(data, 'isoformat'):
            return data.isoformat()
        elif isinstance(data, Decimal):
            return float(data)
        return data

    # ================================
    # FORMATAGE DES RÉPONSES
    # ================================

    def format_response_with_ai(self, data: List[Dict], question: str, sql_query: str) -> str:
        """Version améliorée du formatage avec debug"""
        
        logger.debug(f"🔍 Formatage - Données reçues: {data}")
        
        if not data:
            return "✅ Requête exécutée mais aucun résultat trouvé."
        
        # Cas spéciaux avec vérification des données réelles
        if len(data) == 1 and len(data[0]) == 1:
            first_item = data[0]
            column_name = list(first_item.keys())[0]
            value = list(first_item.values())[0]
            
            logger.debug(f"🔍 Une valeur - Colonne: {column_name}, Valeur: {value}, Type: {type(value)}")
            
            # ✅ FIX: Vérification plus stricte
            if value is None or str(value).strip() == "" or str(value) == column_name:
                return "❌ Erreur dans les données : Les résultats semblent corrompus ou vides."
            
            # Améliorer la réponse selon le contexte
            if "combien" in question.lower() or "nombre" in question.lower():
                if "élève" in question.lower():
                    return f"Il y a {value} élèves inscrits cette année."
                elif "inscription" in question.lower():
                    return f"Il y a {value} inscriptions enregistrées."
                else:
                    return f"Nombre trouvé : {value}"
            else:
                return f"Résultat : {value}"
        
        # Pour les listes multiples
        try:
            df = pd.DataFrame(data)
            
            # Formatage normal avec IA
            messages = [
                {
                    "role": "system",
                    "content": """Analysez les données SQL et donnez une réponse claire en français. 
                    Présentez les résultats de manière structurée et utile."""
                },
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nDonnées: {json.dumps(data[:10], ensure_ascii=False)}"
                }
            ]
            
            response = openai.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                max_tokens=400
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Erreur formatage: {e}")
            return self._format_simple_response(data, question)
    def _format_simple_response(self, data: List[Dict], question: str) -> str:
        """Formatage simple sans IA en cas d'erreur"""
        if not data:
            return "✅ Requête exécutée mais aucun résultat trouvé."
        
        # Cas spécial: une seule valeur numérique (COUNT, etc.)
        if len(data) == 1 and len(data[0]) == 1:
            value = list(data[0].values())[0]
            if isinstance(value, (int, float)) and value is not None:
                if "combien" in question.lower() or "nombre" in question.lower():
                    if "élève" in question.lower() or "eleve" in question.lower():
                        return f"Il y a {value} élèves."
                    elif "absence" in question.lower():
                        return f"Nombre d'absences : {value}"
                    else:
                        return f"Résultat : {value}"
                else:
                    return f"Résultat : {value}"
        
        # Cas général: tableau
        try:
            df = pd.DataFrame(data)
            table = tabulate(df.head(20), headers='keys', tablefmt='grid', showindex=False)
            
            result = f"Résultats pour: {question}\n\n{table}"
            if len(data) > 20:
                result += f"\n\n... et {len(data) - 20} autres résultats"
            
            return result
            
        except Exception:
            # Ultimate fallback
            return f"Résultats trouvés: {len(data)} éléments"
    def _auto_fix_quotes_in_sql(self, sql: str) -> str:
        """Corrige automatiquement les guillemets manquants dans les requêtes SQL"""
        
        # Pattern pour détecter les valeurs alphanumériques sans guillemets après =, IN, etc.
        patterns = [
            # Cas: WHERE colonne = valeur_alphanum
            (r'(\w+\s*=\s*)([A-Za-z][A-Za-z0-9]*\b)(?!\s*[,)])', r"\1'\2'"),
            # Cas: WHERE colonne = valeur avec chiffres et lettres
            (r'(\w+\s*=\s*)([0-9][A-Za-z0-9]*\b)', r"\1'\2'"),
            # Cas: IN (valeur1, valeur2)
            (r'(\bIN\s*\(\s*)([A-Za-z0-9][A-Za-z0-9]*)', r"\1'\2'"),
        ]
        
        corrected_sql = sql
        for pattern, replacement in patterns:
            corrected_sql = re.sub(pattern, replacement, corrected_sql, flags=re.IGNORECASE)
        
        return corrected_sql
    # ================================
    # GÉNÉRATION DE GRAPHIQUES
    # ================================

    def generate_graph_if_relevant(self, data: List[Dict], question: str) -> Optional[str]:
        """Génère un graphique si pertinent pour les données"""
        if not data or len(data) < 2:
            return None
            
        try:
            df = pd.DataFrame(data)
            
            # Détection automatique du type de graphique
            graph_type = self.detect_graph_type(question, df.columns.tolist())
            
            if graph_type and len(df) >= 2:
                return self.generate_auto_graph(df, graph_type)
                
        except Exception as e:
            logger.error(f"Erreur génération graphique: {e}")
            
        return None

    def detect_graph_type(self, user_query: str, df_columns: List[str]) -> Optional[str]:
        """Détecte le type de graphique approprié - VERSION AMÉLIORÉE"""
        user_query = user_query.lower()
        columns = [col.lower() for col in df_columns]
        
        # 🎯 DÉTECTION SPÉCIFIQUE pour évolution/courbe
        evolution_keywords = ["évolution", "evolution", "courbe", "tendance", "historique", 
                            "progression", "croissance", "développement", "trend"]
        
        if any(keyword in user_query for keyword in evolution_keywords):
            # Vérifier si on a une colonne temporelle
            temporal_cols = [col for col in columns if any(t in col for t in ["annee", "année", "year", "date", "mois", "month"])]
            if temporal_cols:
                return "line"
        
        # Détection répartition/pie
        if any(k in user_query for k in ["répartition", "repartition", "pourcentage", "ratio", "proportion"]):
            return "pie"
        
        # Détection comparaison/bar
        if any(k in user_query for k in ["comparaison", "comparer", "nombre", "count", "somme", "total"]):
            # Si c'est temporel, préférer line
            temporal_cols = [col for col in columns if any(t in col for t in ["annee", "année", "year", "date"])]
            if temporal_cols and any(k in user_query for k in ["évolution", "evolution", "courbe", "tendance"]):
                return "line"
            else:
                return "bar"
        
        # Détection automatique basée sur les données
        numeric_cols = len([col for col in df_columns if any(num in col.lower() for num in ["count", "nombre", "total", "somme"])])
        if numeric_cols >= 1:
            temporal_cols = [col for col in columns if any(t in col for t in ["annee", "année", "year", "date"])]
            if temporal_cols:
                return "line"
            else:
                return "bar"
        
        return None
    def generate_auto_graph(self, df: pd.DataFrame, graph_type: str = None) -> Optional[str]:
        """Génère automatiquement un graphique - VERSION AMÉLIORÉE"""
        if df.empty or len(df) < 2:
            logger.debug("❌ DataFrame vide ou insuffisant")
            return None
            
        try:
            # Nettoyage des données
            df = df.dropna()
            
            if len(df) < 2:
                logger.debug("❌ Données insuffisantes après nettoyage")
                return None
            
            logger.debug(f"🔍 Génération graphique - Type: {graph_type}")
            logger.debug(f"🔍 Colonnes DataFrame: {df.columns.tolist()}")
            logger.debug(f"🔍 Premières lignes:\n{df.head()}")
            
            # 🎯 DÉTECTION AMÉLIORÉE du type de graphique
            if not graph_type:
                # Identifier colonnes temporelles et numériques
                temporal_cols = [col for col in df.columns if any(t in col.lower() for t in ["annee", "année", "year", "date", "mois", "month"])]
                numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                
                logger.debug(f"🔍 Auto-détection - Temporel: {temporal_cols}, Numérique: {numeric_cols}")
                
                if temporal_cols and numeric_cols:
                    graph_type = "line"  # Privilégier ligne pour données temporelles
                elif len(df) <= 7 and len(numeric_cols) >= 1:
                    graph_type = "pie"
                else:
                    graph_type = "bar"
            
            # Configuration du graphique
            plt.figure(figsize=(12, 7))
            plt.style.use('default')
            
            # 🎯 AMÉLIORATION : Graphique en ligne pour évolution
            if graph_type == "line" and len(df.columns) >= 2:
                # Identifier les colonnes
                temporal_col = None
                numeric_col = None
                
                # 🎯 AMÉLIORATION : Chercher colonne temporelle avec plus de flexibilité
                for col in df.columns:
                    col_lower = col.lower()
                    if any(t in col_lower for t in ["annee", "année", "year", "date", "an"]) or col_lower in ["annee", "année"]:
                        temporal_col = col
                        break
                
                # Chercher colonne numérique
                numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                if numeric_cols:
                    # Prioriser les colonnes avec des mots-clés pertinents
                    priority_keywords = ["inscription", "total", "count", "nombre", "somme"]
                    for keyword in priority_keywords:
                        matching_cols = [col for col in numeric_cols if keyword in col.lower()]
                        if matching_cols:
                            numeric_col = matching_cols[0]
                            break
                    
                    if not numeric_col:
                        numeric_col = numeric_cols[0]
                
                # Si pas de colonne temporelle trouvée, prendre la première
                if not temporal_col:
                    temporal_col = df.columns[0]
                if not numeric_col:
                    numeric_col = df.columns[1]
                
                logger.debug(f"🎯 Colonnes sélectionnées - Temporel: {temporal_col}, Numérique: {numeric_col}")
                
                # Trier par ordre temporel
                df_sorted = df.sort_values(by=temporal_col)
                
                # 🎯 VÉRIFICATION des données
                x_data = df_sorted[temporal_col]
                y_data = df_sorted[numeric_col]
                
                logger.debug(f"🎯 Données X: {x_data.tolist()}")
                logger.debug(f"🎯 Données Y: {y_data.tolist()}")
                
                # Créer le graphique
                plt.plot(x_data, y_data, 
                        marker='o', linewidth=3, markersize=8, 
                        color='#2E86AB', markerfacecolor='#A23B72')
                
                plt.title(f"Évolution des {numeric_col} par {temporal_col}", fontsize=16, fontweight='bold', pad=20)
                plt.xlabel(temporal_col, fontsize=12, fontweight='bold')
                plt.ylabel(numeric_col, fontsize=12, fontweight='bold')
                plt.xticks(rotation=45, fontsize=10)
                plt.yticks(fontsize=10)
                plt.grid(True, alpha=0.3, linestyle='--')
                
                # Ajouter les valeurs sur les points
                for i, (x, y) in enumerate(zip(x_data, y_data)):
                    plt.annotate(f'{y}', (x, y), textcoords="offset points", 
                            xytext=(0,10), ha='center', fontsize=9, fontweight='bold')
            
            # 🎯 AUTRES TYPES DE GRAPHIQUES (pie, bar) - garder le code existant
            elif graph_type == "pie" and len(df.columns) >= 2:
                x_col = df.columns[0]
                y_col = df.columns[1]
                
                if not pd.api.types.is_numeric_dtype(df[y_col]):
                    logger.debug(f"❌ Colonne {y_col} n'est pas numérique")
                    return None
                    
                df_pie = df.nlargest(8, y_col)
                colors = plt.cm.Set3(range(len(df_pie)))
                
                plt.pie(df_pie[y_col], labels=df_pie[x_col], autopct='%1.1f%%', 
                    startangle=90, colors=colors, textprops={'fontsize': 10})
                plt.title(f"Répartition par {x_col}", fontsize=16, fontweight='bold')
                
            elif graph_type == "bar" and len(df.columns) >= 2:
                x_col = df.columns[0]
                y_cols = [col for col in df.columns[1:] if pd.api.types.is_numeric_dtype(df[col])]
                
                if not y_cols:
                    logger.debug("❌ Aucune colonne numérique pour bar chart")
                    return None
                
                df_bar = df.nlargest(15, y_cols[0]) if len(df) > 15 else df
                
                if len(y_cols) == 1:
                    bars = plt.bar(df_bar[x_col], df_bar[y_cols[0]], 
                                color='#2E86AB', alpha=0.8, edgecolor='white', linewidth=1)
                    plt.title(f"Comparaison de {y_cols[0]} par {x_col}", fontsize=16, fontweight='bold')
                    
                    # Ajouter valeurs sur les barres
                    for bar in bars:
                        height = bar.get_height()
                        plt.text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                                f'{int(height)}', ha='center', va='bottom', fontweight='bold')
                else:
                    df_bar.plot.bar(x=x_col, y=y_cols, alpha=0.8, ax=plt.gca())
                    plt.title(f"Comparaison par {x_col}", fontsize=16, fontweight='bold')
                    
                plt.xlabel(x_col, fontsize=12, fontweight='bold')
                plt.ylabel('Valeurs', fontsize=12, fontweight='bold')
                plt.xticks(rotation=45, fontsize=10)
                plt.grid(True, alpha=0.3, axis='y', linestyle='--')
            
            else:
                logger.debug(f"❌ Type de graphique non supporté ou données insuffisantes: {graph_type}")
                return None
            
            plt.tight_layout()
            
            # 🎯 AMÉLIORATION : Meilleure qualité d'image
            img = io.BytesIO()
            plt.savefig(img, format='png', bbox_inches='tight', dpi=150, 
                    facecolor='white', edgecolor='none')
            img.seek(0)
            encoded = base64.b64encode(img.getvalue()).decode('utf-8')
            plt.close()
            
            logger.info(f"📊 Graphique {graph_type} généré avec succès")
            return f"data:image/png;base64,{encoded}"
            
        except Exception as e:
            logger.error(f"Erreur génération graphique: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            plt.close('all')
            return None
    # ================================
    # CORRECTION AUTOMATIQUE SQL
    # ================================

    def _auto_correct_sql(self, bad_sql: str, error_msg: str) -> Optional[str]:
        """Tente de corriger automatiquement une requête SQL défaillante"""
        try:
            correction_prompt = f"""
            Vous êtes un expert SQL. Corrigez cette requête MySQL en vous basant sur l'erreur.
            
            Erreur: {error_msg}
            
            Requête incorrecte:
            ```sql
            {bad_sql}
            ```
            
            Schéma disponible:
            ```json
            {json.dumps(self.schema[:10], indent=2)}
            ```
            
            Règles:
            - Générez UNIQUEMENT du SQL valide
            - Pas d'explications, juste la requête corrigée
            - Utilisez SELECT uniquement
            
            Requête corrigée:
            ```sql
            """
            
            response = openai.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": correction_prompt}],
                temperature=0,
                max_tokens=300
            )
            
            corrected_sql = self._clean_sql(response.choices[0].message.content)
            
            if corrected_sql and self._validate_sql(corrected_sql):
                logger.info("✅ Requête SQL corrigée avec succès")
                return corrected_sql
                
        except Exception as e:
            logger.error(f"Correction SQL échouée: {str(e)}")
            
        return None

    # ================================
    # MÉTHODES UTILITAIRES
    # ================================

    def get_relevant_domains(self, query: str, domain_descriptions: Dict[str, str]) -> List[str]:
        """Identifie les domaines pertinents basés sur la question"""
        domain_desc_str = "\n".join([f"- {name}: {desc}" for name, desc in domain_descriptions.items()])
        domain_prompt_content = f"""
        Based on the following user question, identify ALL relevant domains from the list below.
        Return only the names of the relevant domains, separated by commas. If no domain is relevant, return 'None'.

        User Question: {query}

        Available Domains and Descriptions:
        {domain_desc_str}

        Relevant Domains (comma-separated):
        """
        
        try:
            response = self.ask_llm(domain_prompt_content)
            domain_names = response.strip()
            
            if domain_names.lower() == 'none' or not domain_names:
                return []
                
            return [d.strip() for d in domain_names.split(',')]
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'identification des domaines: {e}")
            return []
    def get_relevant_domains_improved(self, query: str) -> List[str]:
        """Version améliorée de la détection des domaines"""
        
        # Mappings directs question → domaine
        direct_mappings = {
            'section': ['GENERAL_ADMINISTRATION_CONFIG'],
            'civilité': ['GENERAL_ADMINISTRATION_CONFIG'],
            'nationalité': ['GENERAL_ADMINISTRATION_CONFIG'],
            'niveau': ['GENERAL_ADMINISTRATION_CONFIG'],
            'élève': ['ELEVES_INSCRIPTIONS'],
            'inscription': ['ELEVES_INSCRIPTIONS'],
            'classe': ['GENERAL_ADMINISTRATION_CONFIG'],
            'localité': ['GENERAL_ADMINISTRATION_CONFIG'],
            'gouvernorat': ['GENERAL_ADMINISTRATION_CONFIG'],
            'établissement': ['GENERAL_ADMINISTRATION_CONFIG']
        }
        
        query_lower = query.lower()
        relevant_domains = set()
        
        # Recherche directe
        for keyword, domains in direct_mappings.items():
            if keyword in query_lower:
                relevant_domains.update(domains)
        
        # Si aucun domaine trouvé, utiliser l'IA
        if not relevant_domains:
            return self.get_relevant_domains(query, self.domain_descriptions)
    
        return list(relevant_domains)
    def get_tables_from_domains(self, domains: List[str], domain_to_tables_map: Dict[str, List[str]]) -> List[str]:
        """Récupère toutes les tables associées aux domaines donnés"""
        tables = []
        for domain in domains:
            tables.extend(domain_to_tables_map.get(domain, []))
        return sorted(list(set(tables)))

    def find_matching_template(self, question: str) -> Optional[Dict[str, Any]]:
        """Trouve un template correspondant à la question"""
        exact_match = self._find_exact_template_match(question)
        if exact_match:
            return exact_match
        
        semantic_match, score = self.template_matcher.find_similar_template(question)
        if semantic_match:
            logger.info(f"🔍 Template sémantiquement similaire trouvé (score: {score:.2f})")
            return self._extract_variables(question, semantic_match)
        
        return None

    def _find_exact_template_match(self, question: str) -> Optional[Dict[str, Any]]:
        """Trouve un template exact"""
        cleaned_question = question.rstrip(' ?')
        for template in self.templates_questions:
            pattern = template["template_question"]
            regex_pattern = re.sub(r'\{(.+?)\}', r'(?P<\1>.+?)', pattern)
            match = re.fullmatch(regex_pattern, cleaned_question, re.IGNORECASE)
            if match:
                variables = {k: v.strip() for k, v in match.groupdict().items()}
                return {
                    "template": template,
                    "variables": variables if variables else {}
                }
        return None

    def _extract_variables(self, question: str, template: Dict) -> Dict[str, Any]:
        """Extrait les variables d'un template sémantique"""
        # Implémentation simplifiée - peut être améliorée
        return {
            "template": template,
            "variables": {}
        }

    def generate_query_from_template(self, template: Dict, variables: Dict) -> str:
        """Génère une requête à partir d'un template et de variables"""
        sql_template = template["requete_template"]
        
        # Remplace les variables dans le template
        for var_name, var_value in variables.items():
            placeholder = f"{{{var_name}}}"
            sql_template = sql_template.replace(placeholder, str(var_value))
        
        return sql_template

    # ================================
    # MÉTHODES SPÉCIFIQUES AUX PARENTS
    # ================================

    def get_user_children_data(self, user_id: int) -> Tuple[List[int], List[str]]:
        """Récupère les données des enfants pour un parent"""
        connection = None
        cursor = None
        children_ids = []
        children_prenoms = []

        try:
            query = """
            SELECT DISTINCT pe.id AS id_enfant, pe.PrenomFr AS prenom
            FROM personne p
            JOIN parent pa ON p.id = pa.Personne
            JOIN parenteleve pev ON pa.id = pev.Parent
            JOIN eleve e ON pev.Eleve = e.id
            JOIN personne pe ON e.IdPersonne = pe.id
            WHERE p.id = %s
            """
            
            connection = get_db()
            cursor = connection.cursor()
            
            cursor.execute(query, (user_id,))
            children = cursor.fetchall()
            
            if children:
                children_ids = [child['id_enfant'] for child in children]
                children_prenoms = [child['prenom'] for child in children]
                logger.info(f"✅ Found {len(children_ids)} children for parent {user_id}")
            
            return (children_ids, children_prenoms)
            
        except Exception as e:
            logger.error(f"❌ Error getting children data for parent {user_id}: {str(e)}")
            return ([], [])
            
        finally:
            try:
                if cursor:
                    cursor.close()
                    
                if connection and hasattr(connection, '_direct_connection'):
                    connection.close()
                    logger.debug("🔌 Closed direct MySQL connection")
            except Exception as close_error:
                logger.warning(f"⚠️ Error during cleanup: {str(close_error)}")

    def detect_names_in_question(self, question: str, authorized_names: List[str]) -> Dict[str, List[str]]:
        """Détecte les noms dans une question et vérifie les autorisations"""
        import unicodedata
        
        def normalize_name(name):
            name = unicodedata.normalize('NFD', name.lower())
            return ''.join(char for char in name if unicodedata.category(char) != 'Mn')
        
        normalized_authorized = [normalize_name(name) for name in authorized_names]
        
        # Mots à exclure
        excluded_words = {
            'mon', 'ma', 'mes', 'le', 'la', 'les', 'de', 'du', 'des', 'et', 'ou', 'si', 'ce', 
            'cette', 'ces', 'son', 'sa', 'ses', 'notre', 'nos', 'votre', 'vos', 'leur', 'leurs',
            'enfant', 'enfants', 'fils', 'fille', 'garçon', 'petit', 'petite', 'grand', 'grande',
            'eleve', 'élève', 'eleves', 'élèves', 'classe', 'école', 'ecole', 'moyenne', 'note', 
            'notes', 'résultat', 'resultats', 'trimestre', 'année', 'annee', 'matière', 'matiere',
            'emploi', 'temps', 'horaire', 'professeur', 'enseignant', 'directeur', 'principal'
        }
        
        # Extraire les noms potentiels (commence par majuscule)
        potential_names = re.findall(r'\b[A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞŸ][a-zàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ]+', question)
        
        # Filtrer les mots exclus
        potential_names = [name for name in potential_names if normalize_name(name) not in excluded_words]
        
        authorized_found = []
        unauthorized_found = []
        
        for name in potential_names:
            normalized_name = normalize_name(name)
            if normalized_name in normalized_authorized:
                authorized_found.append(name)
            else:
                # Mots français communs à ignorer
                common_words = {'Merci', 'Bonjour', 'Salut', 'Cordialement', 'Madame', 'Monsieur', 
                              'Mademoiselle', 'Docteur', 'Professeur', 'Janvier', 'Février', 'Mars', 
                              'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 
                              'Novembre', 'Décembre', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 
                              'Vendredi', 'Samedi', 'Dimanche', 'France', 'Tunisie', 'Français'}
                
                if name not in common_words:
                    unauthorized_found.append(name)
        
        logger.debug(f"🔍 Prénoms détectés - Autorisés: {authorized_found}, Non autorisés: {unauthorized_found}")
        
        return {
            "authorized_names": authorized_found,
            "unauthorized_names": unauthorized_found
        }

    def validate_parent_access(self, sql_query: str, children_ids: List[int]) -> bool:
        """Valide qu'une requête parent respecte les restrictions de sécurité"""
        if not isinstance(children_ids, list) or not children_ids:
            return False
            
        try:
            children_ids_str = [str(int(id)) for id in children_ids]
        except (ValueError, TypeError):
            raise ValueError("Tous les IDs enfants doivent être numériques")
        
        # Normalisation de la requête
        sql_lower = sql_query.lower().replace("\n", " ").replace("\t", " ")
        sql_lower = re.sub(r'\s+', ' ', sql_lower).strip()
        
        logger.debug(f"🔍 SQL normalisé: {sql_lower}")
        logger.debug(f"👶 IDs enfants: {children_ids_str}")
        
        # Patterns de sécurité à rechercher
        security_patterns = set()
        
        # Filtres directs
        for child_id in children_ids_str:
            security_patterns.update({
                f"idpersonne = {child_id}",
                f"idpersonne={child_id}",
                f"e.idpersonne = {child_id}",
                f"e.idpersonne={child_id}",
                f"eleve.idpersonne = {child_id}",
                f"eleve.idpersonne={child_id}",
                f"idpersonne in ({child_id})",
                f"e.idpersonne in ({child_id})",
                f"eleve.idpersonne in ({child_id})"
            })
        
        # Pour listes d'IDs
        if len(children_ids_str) > 1:
            ids_joined = ",".join(children_ids_str)
            ids_joined_spaced = ", ".join(children_ids_str)
            security_patterns.update({
                f"idpersonne in ({ids_joined})",
                f"idpersonne in ({ids_joined_spaced})",
                f"e.idpersonne in ({ids_joined})",
                f"e.idpersonne in ({ids_joined_spaced})",
                f"eleve.idpersonne in ({ids_joined})",
                f"eleve.idpersonne in ({ids_joined_spaced})"
            })
        
        # Sous-requêtes de sécurité
        for child_id in children_ids_str:
            security_patterns.update({
                f"eleve in (select id from eleve where idpersonne = {child_id}",
                f"eleve in (select id from eleve where idpersonne={child_id}",
                f"exists (select 1 from eleve where idpersonne = {child_id}",
                f"exists (select 1 from eleve where idpersonne={child_id}"
            })
        
        # Vérification des patterns
        found_patterns = [pattern for pattern in security_patterns if pattern in sql_lower]
        
        if not found_patterns:
            logger.warning(f"Requête parent non sécurisée - Filtre enfants manquant: {sql_query}")
            return False
        
        # Vérification des patterns interdits
        forbidden_patterns = {"--", "/*", "*/", " drop ", " truncate ", " insert ", " update ", " delete "}
        found_forbidden = [pattern for pattern in forbidden_patterns if pattern in sql_lower]
        
        if found_forbidden:
            logger.error(f"Tentative de requête non autorisée détectée: {found_forbidden}")
            return False
        
        logger.debug("✅ Validation parent réussie")
        return True

    def _is_public_info_query(self, question: str, sql_query: str) -> bool:
        """Vérifie si la question concerne des informations publiques"""
        question_lower = question.lower()
        sql_lower = sql_query.lower()
        
        # Mots-clés pour informations publiques
        public_keywords = ['cantine', 'repas', 'menu', 'déjeuner', 'restauration', 
                          'actualité', 'actualite', 'actualités', 'actualites', 
                          'nouvelles', 'informations', 'annonces']
        
        # Tables publiques
        public_tables = ['cantine', 'menu', 'actualite', 'actualite1', 'annonces']
        
        # Vérifications
        has_public_keywords = any(keyword in question_lower for keyword in public_keywords)
        has_public_tables = any(table in sql_lower for table in public_tables)
        
        return has_public_keywords or has_public_tables

    # ================================
    # MÉTHODES POUR DOCUMENTS PDF
    # ================================

    def get_student_info_by_name(self, full_name: str) -> Optional[Dict]:
        """Récupère les informations d'un élève par son nom complet"""
        try:
            conn = get_db()
            cursor = conn.cursor(MySQLdb.cursors.DictCursor)

            sql = """
            SELECT 
                p.NomFr, p.PrenomFr,
                CONCAT(p.NomFr, ' ', p.PrenomFr) AS nom_complet,
                e.DateNaissance, IFNULL(e.LieuNaissance, e.AutreLieuNaissance) AS lieu_de_naissance,
                c.CODECLASSEFR as classe, n.NOMNIVAR as niveau,
                e.id as eleve_id, e.IdPersonne as matricule, 
                e.idedusrv as id_service,
                ie.id as inscription_id
            FROM eleve e
            JOIN personne p ON e.IdPersonne = p.id
            JOIN inscriptioneleve ie ON e.id = ie.Eleve
            JOIN classe c ON ie.Classe = c.id
            JOIN niveau n ON c.IDNIV = n.id
            JOIN anneescolaire a ON ie.AnneeScolaire = a.id
            WHERE LOWER(CONCAT(p.NomFr, ' ', p.PrenomFr)) = LOWER(%s)
            AND a.AnneeScolaire = %s
            LIMIT 1
            """

            current_year = "2024/2025"  
            cursor.execute(sql, (full_name, current_year))
            row = cursor.fetchone()
            
            return row

        except Exception as e:
            logger.error(f"Erreur get_student_info_by_name: {str(e)}")
            return None
        finally:
            try:
                if cursor:
                    cursor.close()
                if conn and hasattr(conn, '_direct_connection'):
                    conn.close()
            except:
                pass

    # ================================
    # MÉTHODES DE NETTOYAGE
    # ================================

    def cleanup_conversation_history(self, max_messages: int = 10):
        """Nettoie l'historique des conversations"""
        if len(self.conversation_history) > max_messages:
            # Garder les messages système et les plus récents
            system_messages = [msg for msg in self.conversation_history if msg.get('role') == 'system']
            recent_messages = self.conversation_history[-(max_messages-len(system_messages)):]
            self.conversation_history = system_messages + recent_messages

    def reset_conversation(self):
        """Reset l'historique des conversations"""
        self.conversation_history = []
        self.query_history = []
        logger.info("🔄 Historique des conversations réinitialisé")

    # ================================
    # FONCTIONS UTILITAIRES GLOBALES
    # ================================

    def validate_name(name: str) -> bool:
        """Valide si un nom contient seulement des caractères autorisés"""
        if not name or not isinstance(name, str):
            return False
        
        pattern = r"^[A-Za-zÀ-ÿ\s\-']+$"
        
        name = name.strip()
        if len(name) < 2 or len(name) > 100:
            return False
        
        # Pas d'espaces multiples ou de caractères spéciaux en début/fin
        if re.search(r"\s{2,}|^[\s\-']|[\s\-']$", name):
            return False
        
        return bool(re.match(pattern, name))
    
    def get_user_conversations(self, user_id: int, limit: int = 50) -> List[Dict]:
        """Récupère les conversations d'un utilisateur"""
        try:
            return self.conversation_manager.get_user_conversations(user_id, limit)
        except Exception as e:
            logger.error(f"Erreur récupération conversations: {e}")
            return []

    def get_conversation_messages(self, conversation_id: int, user_id: int) -> List[Dict]:
        """Récupère les messages d'une conversation"""
        try:
            return self.conversation_manager.get_conversation_messages(conversation_id, user_id)
        except Exception as e:
            logger.error(f"Erreur récupération messages: {e}")
            return []

    def search_conversations(self, user_id: int, query: str, limit: int = 20) -> List[Dict]:
        """Recherche dans les conversations"""
        try:
            return self.conversation_manager.search_conversations(user_id, query, limit)
        except Exception as e:
            logger.error(f"Erreur recherche conversations: {e}")
            return []

    def update_conversation_title(self, conversation_id: int, user_id: int, new_title: str) -> bool:
        """Met à jour le titre d'une conversation"""
        try:
            return self.conversation_manager.update_conversation_title(conversation_id, user_id, new_title)
        except Exception as e:
            logger.error(f"Erreur mise à jour titre: {e}")
            return False

    def delete_conversation(self, conversation_id: int, user_id: int) -> bool:
        """Supprime une conversation"""
        try:
            return self.conversation_manager.delete_conversation(conversation_id, user_id)
        except Exception as e:
            logger.error(f"Erreur suppression conversation: {e}")
            return False

    def get_user_stats(self, user_id: int) -> Dict:
        """Récupère les statistiques d'un utilisateur"""
        try:
            return self.conversation_manager.get_user_stats(user_id)
        except Exception as e:
            logger.error(f"Erreur statistiques utilisateur: {e}")
            return {}

    # 🆕 MÉTHODE POUR MIGRER L'HISTORIQUE EXISTANT
    def migrate_existing_conversations(self, user_id: int, old_messages: List[Dict]) -> Optional[int]:
        """Migre une conversation existante vers le nouveau système d'historique"""
        try:
            if not old_messages:
                return None
                
            # Créer une nouvelle conversation
            first_message = old_messages[0].get('text', 'Conversation migrée')
            conversation_id = self.conversation_manager.create_conversation(user_id, first_message)
            
            # Migrer tous les messages
            for msg in old_messages:
                message_type = 'user' if msg.get('isMe', False) else 'assistant'
                content = msg.get('text', '')
                sql_query = msg.get('sqlQuery')
                graph_data = msg.get('graphBase64')
                
                self.conversation_manager.add_message(
                    conversation_id, message_type, content, sql_query, graph_data
                )
            
            logger.info(f"✅ {len(old_messages)} messages migrés vers conversation {conversation_id}")
            return conversation_id
            
        except Exception as e:
            logger.error(f"Erreur migration conversation: {e}")
            return None

    # 🔄 MÉTHODE DE COMPATIBILITÉ : Wrapper pour l'ancienne méthode
    def ask_question(self, question: str, user_id: Optional[int] = None, 
                    roles: Optional[List[str]] = None) -> tuple[str, str, Optional[str]]:
        """
        Méthode de compatibilité qui utilise le nouveau système avec historique
        Retourne (sql_query, formatted_response, graph_data)
        """
        sql_query, formatted_response, graph_data, _ = self.ask_question_with_history(
            question, user_id, roles
        )
        return sql_query, formatted_response, graph_data

    # 🆕 NETTOYAGE PÉRIODIQUE DE L'HISTORIQUE
    def cleanup_user_history(self, user_id: int, keep_recent_days: int = 30) -> int:
        """Nettoie l'historique ancien d'un utilisateur en gardant les conversations récentes"""
        try:
            from datetime import datetime, timedelta
            
            cutoff_date = datetime.now() - timedelta(days=keep_recent_days)
            
            # Récupérer les conversations anciennes
            all_conversations = self.conversation_manager.get_user_conversations(user_id, limit=1000)
            old_conversations = [
                conv for conv in all_conversations 
                if datetime.fromisoformat(conv['updated_at']) < cutoff_date
            ]
            
            # Archiver les anciennes conversations
            deleted_count = 0
            for conv in old_conversations:
                if self.conversation_manager.delete_conversation(conv['id'], user_id):
                    deleted_count += 1
            
            logger.info(f"🧹 {deleted_count} conversations anciennes archivées pour utilisateur {user_id}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Erreur nettoyage historique utilisateur: {e}")
            return 0

    # 🆕 EXPORT/IMPORT DE CONVERSATIONS
    def export_conversation(self, conversation_id: int, user_id: int, format: str = 'json') -> Optional[str]:
        """Exporte une conversation dans différents formats"""
        try:
            messages = self.conversation_manager.get_conversation_messages(conversation_id, user_id)
            if not messages:
                return None
            
            if format == 'json':
                import json
                return json.dumps(messages, indent=2, ensure_ascii=False)
            
            elif format == 'txt':
                output = []
                for msg in messages:
                    timestamp = msg.get('timestamp', '')
                    msg_type = msg.get('type', '').upper()
                    content = msg.get('content', '')
                    output.append(f"[{timestamp}] {msg_type}: {content}")
                return '\n\n'.join(output)
            
            elif format == 'markdown':
                output = ["# Conversation Export", ""]
                for msg in messages:
                    msg_type = msg.get('type', '')
                    content = msg.get('content', '')
                    
                    if msg_type == 'user':
                        output.append(f"**👤 Utilisateur:**")
                        output.append(content)
                    elif msg_type == 'assistant':
                        output.append(f"**🤖 Assistant:**")
                        output.append(content)
                    output.append("")
                
                return '\n'.join(output)
            
            return None
            
        except Exception as e:
            logger.error(f"Erreur export conversation: {e}")
            return None