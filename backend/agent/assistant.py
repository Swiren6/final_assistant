from config.database import get_db_connection,get_db
from langchain_community.utilities import SQLDatabase
from typing import List, Dict, Optional, Any, Tuple
from agent.llm_utils import ask_llm 
from langchain.prompts import PromptTemplate
import os
from dotenv import load_dotenv  
from agent.template_matcher.matcher import SemanticTemplateMatcher
import re
from pathlib import Path
from agent.cache_manager import CacheManager
from agent.cache_manager1 import CacheManager1
from agent.pdf_utils.bulletin import export_bulletin_pdf
from agent.sql_agent import SQLAgent
import json
from agent.prompts.templates import PROMPT_TEMPLATE, ADMIN_PROMPT_TEMPLATE, PARENT_PROMPT_TEMPLATE
from security.roles import is_super_admin, is_parent, validate_parent_access
import traceback
from agent.pdf_utils.attestation import PDFGenerator


import logging
logger = logging.getLogger(__name__)
load_dotenv()
class SQLAssistant:
    def __init__(self, db=None):
        self.db = db if db is not None else get_db_connection()
        self.relations_description = self._safe_load_relations()
        self.domain_descriptions = self._safe_load_domain_descriptions()
        self.domain_to_tables_mapping = self._safe_load_domain_to_tables_mapping()
        self.ask_llm = ask_llm
        self.cache = CacheManager()
        self.cache1 = CacheManager1()
        self.template_matcher = SemanticTemplateMatcher()
        
        try:
            self.templates_questions = self.load_question_templates()
            if self.templates_questions:
                print(f"✅ {len(self.templates_questions)} templates chargés")
                self.template_matcher.load_templates(self.templates_questions)
            else:
                print("⚠️ Aucun template valide - fonctionnement en mode LLM seul")
                
        except ValueError as e:
            print(f"❌ Erreur de chargement des templates: {str(e)}")
            self.templates_questions = []

    def get_user_children_ids(self, user_id: int) -> List[int]:
        """Récupère les IDs des enfants d'un parent avec gestion robuste des connexions"""
        connection = None
        cursor = None
        children_ids = []

        try:
            query = """
            SELECT DISTINCT pe.id AS id_enfant
            FROM personne p
            JOIN parent pa ON p.id = pa.Personne
            JOIN parenteleve pev ON pa.id = pev.Parent
            JOIN eleve e ON pev.Eleve = e.id
            JOIN personne pe ON e.IdPersonne = pe.id
            WHERE p.id = %s
            """
            
            # Get connection
            connection = get_db()
            cursor = connection.cursor()
            
            # Execute query
            cursor.execute(query, (user_id,))
            users = cursor.fetchall()
            
            # Process results
            if users:
                children_ids = [user['id_enfant'] for user in users]
                logger.info(f"✅ Found {len(children_ids)} children for parent {user_id}")
            
            return children_ids
        except Exception as e:
            logger.error(f"❌ Error getting children for parent {user_id}: {str(e)}")
            logger.error(traceback.format_exc())
            return []
        finally:
            # Only close if we created a direct connection
            try:
                if cursor:
                    cursor.close()
                
                # Check if this is a Flask-managed connection
                from flask import current_app
                is_flask_connection = current_app and hasattr(current_app, 'extensions') and 'mysql' in current_app.extensions and connection == current_app.extensions['mysql'].connection
                
                if connection and not is_flask_connection:
                    connection.close()
                    logger.debug("🔌 Closed direct MySQL connection")
            except Exception as close_error:
                logger.warning(f"⚠️ Error during cleanup: {str(close_error)}")


    def validate_parent_access(self, sql_query: str, children_ids: List[int]) -> bool:
        # Validation des inputs
        if not isinstance(children_ids, list):
            raise TypeError("children_ids doit être une liste")
            
        if not children_ids:
            return False
            
        try:
            children_ids_str = [str(int(id)) for id in children_ids]
        except (ValueError, TypeError):
            raise ValueError("Tous les IDs enfants doivent être numériques")
        
        # Normalisation plus douce de la requête (garder un espace pour séparer les mots)
        sql_lower = sql_query.lower().replace("\n", " ").replace("\t", " ")
        # Normaliser les espaces multiples en un seul
        import re
        sql_lower = re.sub(r'\s+', ' ', sql_lower).strip()
        
        print(f"🔍 SQL normalisé: {sql_lower}")  # Debug
        print(f"👶 IDs enfants: {children_ids_str}")  # Debug
        
        # Préparation des motifs de sécurité
        security_patterns = set()
        
        # 1. Filtres directs avec plus de variantes
        if len(children_ids_str) == 1:
            child_id = children_ids_str[0]
            security_patterns.update({
                f"idpersonne = {child_id}",
                f"idpersonne={child_id}",
                f"e.idpersonne = {child_id}",
                f"e.idpersonne={child_id}",
                f"eleve.idpersonne = {child_id}",
                f"eleve.idpersonne={child_id}",
                f"idpersonne in ({child_id})",
                f"eleve = ({child_id})",
                f"Eleve = ({child_id})",
                f"eleve = {child_id}",
                f"Eleve = {child_id}"
            })
        else:
            ids_joined = ",".join(children_ids_str)
            ids_joined_spaced = ", ".join(children_ids_str)
            security_patterns.update({
                f"idpersonne in ({ids_joined})",
                f"idpersonne in({ids_joined})",
                f"idpersonne in ({ids_joined_spaced})",
                f"e.idpersonne in ({ids_joined})",
                f"e.idpersonne in({ids_joined})",
                f"e.idpersonne in ({ids_joined_spaced})",
                f"eleve.idpersonne in ({ids_joined})",
                f"eleve.idpersonne in({ids_joined})",
                f"eleve.idpersonne in ({ids_joined_spaced})",
                f"id_personne in ({ids_joined})",
                f"id_personne in({ids_joined})",
                f"id_personne in ({ids_joined_spaced})"
            })
        
        # 2. Sous-requêtes de sécurité (patterns plus complets)
        for child_id in children_ids_str:
            security_patterns.update({
                f"eleve in (select id from eleve where idpersonne = {child_id}",
                f"eleve in (select id from eleve where idpersonne={child_id}",
                f"exists (select 1 from eleve where idpersonne = {child_id}",
                f"exists (select 1 from eleve where idpersonne={child_id}",
                f"exists(select 1 from eleve where idpersonne = {child_id}",
                f"exists(select 1 from eleve where idpersonne={child_id}",
                f"ed.idenelev IN (SELECT id FROM eleve WHERE IdPersonne IN {child_id})",
                f"e.idpersonne in ({child_id})",
                f"eleve = ({child_id})",
                f"Eleve = ({child_id})",
                f"eleve = {child_id}",
                f"Eleve = {child_id}"
            })
        
        # Pour les listes d'IDs
        if len(children_ids_str) > 1:
            ids_joined = ",".join(children_ids_str)
            ids_joined_spaced = ", ".join(children_ids_str)
            security_patterns.update({
                f"eleve in (select id from eleve where idpersonne in ({ids_joined})",
                f"eleve in (select id from eleve where idpersonne in({ids_joined})",
                f"eleve in (select id from eleve where idpersonne in ({ids_joined_spaced})",
                f"exists (select 1 from eleve where idpersonne in ({ids_joined})",
                f"exists (select 1 from eleve where idpersonne in({ids_joined})",
                f"exists (select 1 from eleve where idpersonne in ({ids_joined_spaced})",
                f"exists(select 1 from eleve where idpersonne in ({ids_joined})",
                f"exists(select 1 from eleve where idpersonne in({ids_joined})",
                f"exists(select 1 from eleve where idpersonne in ({ids_joined_spaced})"
            })
        
        print(f"🔒 Patterns de sécurité recherchés:")
        for pattern in sorted(security_patterns):
            print(f"   - '{pattern}'")
        
        # 3. Vérification des motifs
        found_patterns = []
        for pattern in security_patterns:
            if pattern in sql_lower:
                found_patterns.append(pattern)
        
        print(f"✅ Patterns trouvés: {found_patterns}")
        
        if not found_patterns:
            logger.warning(f"Requête parent non sécurisée - Filtre enfants manquant: {sql_query}")
            print(f"❌ Aucun pattern de sécurité trouvé dans la requête")
            return False
        
        # 4. Vérification des injections potentielles
        forbidden_patterns = {
             "--", "/*", "*/", " drop ", " truncate ", " insert ", " update ", " delete "
        }
        found_forbidden = [pattern for pattern in forbidden_patterns if pattern in sql_lower]
        
        if found_forbidden:
            logger.error(f"Tentative de requête non autorisée détectée: {found_forbidden}")
            print(f"❌ Patterns interdits trouvés: {found_forbidden}")
            return False
        
        print(f"✅ Validation parent réussie")
        return True

    def ask_question(self, question: str, user_id: Optional[int] = None, roles: Optional[List[str]] = None) -> tuple[str, str]:
        """Version strictement authentifiée"""
        if user_id is None:
            user_id = 0  # Or some default system user
    
        if roles is None:
            roles = []
        # 1. Validation des rôles
        if not roles:
            return "", "❌ Accès refusé : Aucun rôle fourni"
        
        valid_roles = ['ROLE_SUPER_ADMIN', 'ROLE_PARENT']
        has_valid_role = any(role in valid_roles for role in roles)
        
        print(f"DEBUG - has_valid_role: {has_valid_role}")
        
        if not has_valid_role:
            return "", f"❌ Accès refusé : Rôles fournis {roles}, requis {valid_roles}"

        # 2. Traitement par rôle
        try:
            if 'ROLE_SUPER_ADMIN' in roles:
                return self._process_admin_question(question)
            elif 'ROLE_PARENT' in roles:
                return self._process_parent_question(question, user_id)
        except Exception as e:
            return "", f"❌ Erreur : {str(e)}"

    def _process_admin_question(self, question: str) -> tuple[str, str]:
        """Traite une question avec accès admin complet"""
        
        cached = self.cache.get_cached_query(question)
        if cached:
            sql_template, variables = cached
            sql_query = sql_template
            for column, value in variables.items():
                sql_query = sql_query.replace(f"{{{column}}}", value)
            
            print("⚡ Requête admin récupérée depuis le cache")
            try:
                result = self.db.run(sql_query)
                return sql_query, self.format_result(result, question)
            except Exception as db_error:
                return sql_query, f"❌ Erreur d'exécution SQL : {str(db_error)}"
        
        # 2. Vérifier les templates
        template_match = self.find_matching_template(question)
        if template_match:
            print("🔍 Template admin trouvé")
            sql_query = self.generate_query_from_template(
                template_match["template"],
                template_match["variables"]
            )
            try:
                result = self.db.run(sql_query)
                formatted_result = self.format_result(result, question)
                return sql_query, formatted_result
            except Exception as db_error:
                return sql_query, f"❌ Erreur d'exécution SQL : {str(db_error)}"
        
        # 3. Génération via LLM (template admin)
        print("🔍 Génération LLM pour admin")
        relevant_domains = self.get_relevant_domains(question, self.domain_descriptions)
        if relevant_domains:
            # 2. Tables associées
            relevant_tables = self.get_tables_from_domains(relevant_domains, self.domain_to_tables_mapping)
            # 3. Structure SQL réduite
            table_info = self.db.get_table_info(relevant_tables)
            # 4. Descriptions réduites
            relevant_domain_descriptions = "\n".join(
                f"{dom}: {self.domain_descriptions[dom]}" for dom in relevant_domains if dom in self.domain_descriptions
            )
        else:
            # fallback : tout injecter si rien trouvé
            table_info = self.db.get_table_info()
            relevant_domain_descriptions = "\n".join(self.domain_descriptions.values())

        prompt = ADMIN_PROMPT_TEMPLATE.format(
            input=question,
            table_info=self.db.get_table_info(),
            relevant_domain_descriptions=relevant_domain_descriptions,
            relations=self.relations_description
        )

        llm_response = self.ask_llm(prompt)
        sql_query = llm_response.replace("```sql", "").replace("```", "").strip()
        
        if not sql_query:
            return "", "❌ La requête générée est vide."

        try:
            result = self.db.run(sql_query)
            formatted_result = self.format_result(result, question)
            self.cache.cache_query(question, sql_query)
            return sql_query, formatted_result
        except Exception as db_error:
            return sql_query, f"❌ Erreur d'exécution SQL : {str(db_error)}"

    def _process_parent_question(self, question: str, user_id: int) -> tuple[str, str]:
        """Traite une question avec restrictions parent"""
        
        self.cache1.clean_double_braces_in_cache()
        cached = self.cache1.get_cached_query(question,user_id)
        if cached:
            sql_template, variables = cached
            sql_query = sql_template
            for column, value in variables.items():
                sql_query = sql_query.replace(f"{{{column}}}", value)
            
            print("⚡ Requête parent récupérée depuis le cache")
            try:
                result = self.db.run(sql_query)
                return sql_query, self.format_result(result, question)
            except Exception as db_error:
                return sql_query, f"❌ Erreur d'exécution SQL : {str(db_error)}"
            
        children_ids = self.get_user_children_ids(user_id)
        if not children_ids:
             return "", "❌ Aucun enfant trouvé pour ce parent  ou erreur d'accès."
        
        print(f"🔒 Restriction parent - Enfants autorisés: {children_ids}")
        
        # Génération via LLM avec template parent
        children_ids_str = ','.join(map(str, children_ids))
        
        relevant_domains = self.get_relevant_domains(question, self.domain_descriptions)
        if relevant_domains:
            # 2. Tables associées
            relevant_tables = self.get_tables_from_domains(relevant_domains, self.domain_to_tables_mapping)
            # 3. Structure SQL réduite
            table_info = self.db.get_table_info(relevant_tables)
            # 4. Descriptions réduites
            relevant_domain_descriptions = "\n".join(
                f"{dom}: {self.domain_descriptions[dom]}" for dom in relevant_domains if dom in self.domain_descriptions
            )
        else:
            # fallback : tout injecter si rien trouvé
            table_info = self.db.get_table_info()
            relevant_domain_descriptions = "\n".join(self.domain_descriptions.values())

        prompt = PARENT_PROMPT_TEMPLATE.format(
            input=question,
            table_info=self.db.get_table_info(),
            relevant_domain_descriptions=relevant_domain_descriptions,
            relations=self.relations_description,
            user_id=user_id,
            children_ids=children_ids_str
        )
        llm_response = self.ask_llm(prompt)
        sql_query = llm_response.replace("```sql", "").replace("```", "").strip()
        
        if not sql_query:
            return "", "❌ La requête générée est vide."

        # Validation de sécurité pour les parents
        if not self.validate_parent_access(sql_query, children_ids):
            return "", "❌ Accès refusé: La requête ne respecte pas les restrictions parent."

        try:
            result = self.db.run(sql_query)
            formatted_result = self.format_result(result, question)
            self.cache1.cache_query(question, sql_query)
            return sql_query, formatted_result
        except Exception as db_error:
            return sql_query, f"❌ Erreur d'exécution SQL : {str(db_error)}"

    def load_question_templates(self) -> list:
        try:
            templates_path = Path(__file__).parent / 'templates_questions.json'
            
            if not templates_path.exists():
                print(f"⚠️ Fichier non trouvé, création: {templates_path}")
                templates_path.write_text('{"questions": []}', encoding='utf-8')
                return []

            content = templates_path.read_text(encoding='utf-8').strip()
            if not content:
                print("⚠️ Fichier vide, réinitialisation")
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
                        print(f"⚠️ Template incomplet ignoré: {template.get('description', 'sans description')}")
                
                return valid_templates

            except json.JSONDecodeError as e:
                print(f"❌ Fichier JSON corrompu, réinitialisation. Erreur: {e}")
                backup_path = templates_path.with_suffix('.bak.json')
                templates_path.rename(backup_path)
                templates_path.write_text('{"questions": []}', encoding='utf-8')
                return []

        except Exception as e:
            print(f"❌ Erreur critique lors du chargement: {e}")
            return []
    
    def find_matching_template(self, question: str) -> Optional[Dict[str, Any]]:
        exact_match = self._find_exact_template_match(question)
        if exact_match:
            return exact_match
        
        semantic_match, score = self.template_matcher.find_similar_template(question)
        if semantic_match:
            print(f"🔍 Template sémantiquement similaire trouvé (score: {score:.2f})")
            return self._extract_variables(question, semantic_match)
        
        return None

    def _find_exact_template_match(self, question: str) -> Optional[Dict[str, Any]]:
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
        template_text = template["template_question"]
        variables = {}

        annee_pattern = r"(20\d{2}[-\/]20\d{2})"
        annee_match = re.search(annee_pattern, question)
        if annee_match:
            variables["AnneeScolaire"] = annee_match.group(1).replace("-", "/")
        
        var_names = re.findall(r'\{(.+?)\}', template_text)
        for var_name in var_names:
            if var_name not in variables:  
                keyword_pattern = re.escape(template_text.split(f"{{{var_name}}}")[0].split()[-1])
                pattern = fr"{keyword_pattern}\s+([^\s]+)"
                match = re.search(pattern, question, re.IGNORECASE)
                if match:
                    variables[var_name] = match.group(1).strip(",.?!")
        
        return {
            "template": template,
            "variables": variables if variables else {}
        }

    def generate_query_from_template(self, template: Dict, variables: Dict) -> str:
        requete = template["requete_template"]
        if not variables:
            return requete
        
        for var_name, var_value in variables.items():
            clean_value = str(var_value).split('?')[0].strip(",.!?\"'")
            
            if var_name.lower() == "anneescolaire":
                clean_value = clean_value.replace("-", "/")
            
            requete = requete.replace(f'{{{var_name}}}', clean_value)
        
        return requete

    def get_relevant_domains(self, query: str, domain_descriptions: Dict[str, str]) -> List[str]:
        """Identifies relevant domains based on a user query using DeepSeek."""
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
            print(f"❌ Erreur lors de l'identification des domaines: {e}")
            return []
    
    def get_tables_from_domains(self, domains: List[str], domain_to_tables_map: Dict[str, List[str]]) -> List[str]:
        """Retrieves all tables associated with the given domains."""
        tables = []
        for domain in domains:
            tables.extend(domain_to_tables_map.get(domain, []))
        return sorted(list(set(tables)))

    def format_result(self, result: str, question: str = "") -> str:
        """
        Formate les résultats SQL bruts en une table lisible
        Args:
            result: Le résultat brut de la requête SQL
            question: La question originale (optionnelle)
        Returns:
            str: Le résultat formaté ou un message approprié
        """
        if not result or result.strip() in ["[]", ""] or "0 rows" in result.lower():
            return "✅ Requête exécutée mais aucun résultat trouvé."
        
        try:
            lines = [line.strip() for line in result.split('\n') if line.strip()]
            if len(lines) == 1 and lines[0].startswith('(') and lines[0].endswith(')'):
                value = lines[0][1:-1].strip()  
                return f"Résultat : {value}"
            
            if len(lines) > 1:
                headers = [h.strip() for h in lines[0].split('|')]
                rows = []
                
                for line in lines[1:]:
                    row = [cell.strip() for cell in line.split('|')]
                    rows.append(row)
                
                formatted = []
                if question:
                    formatted.append(f"Résultats pour: {question}\n")
                
                # En-tête
                header_line = " | ".join(headers)
                formatted.append(header_line)
                
                # Séparateur
                separator = "-+-".join(['-' * len(h) for h in headers])
                formatted.append(separator)
                
                # Données
                for row in rows:
                    formatted.append(" | ".join(row))
                
                return "\n".join(formatted)
            
            return f"{result}"
        
        except Exception as e:
            return f"❌ Erreur de formatage: {str(e)}\nRésultat brut:\n{result}"

    def _safe_load_relations(self) -> str:
        """Charge les relations avec gestion d'erreurs"""
        try:
            relations_path = Path(__file__).parent / 'prompts' / 'relations.txt'
            print(f"🔍 Tentative de chargement depuis : {relations_path.absolute()}")
                      
            if relations_path.exists():
                content = relations_path.read_text(encoding='utf-8')
                print(f"✅ Contenu chargé (premières 50 lignes) :\n{content[:500]}...")
                return content
            else:
                print("⚠️ Fichier relations.txt non trouvé")
                return "# Aucune relation définie"
                
        except Exception as e:
            print(f"❌ Erreur lors du chargement : {str(e)}")
            return "# Erreur chargement relations"

    def _safe_load_domain_descriptions(self) -> dict:
        """Charge les descriptions de domaine avec gestion d'erreurs"""
        try:
            domain_path = Path(__file__).parent / 'prompts' / 'domain_descriptions.json'
            if domain_path.exists():
                with open(domain_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            print("⚠️ Fichier domain_descriptions.json non trouvé")
            return {}
        except Exception as e:
            print(f"❌ Erreur chargement domain descriptions: {e}")
            return {}

    def _safe_load_domain_to_tables_mapping(self) -> dict:
        """Charge le mapping domaine-tables avec gestion d'erreurs"""
        try:
            mapping_path = Path(__file__).parent / 'prompts' / 'domain_tables_mapping.json'
            if mapping_path.exists():
                with open(mapping_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            print("⚠️ Fichier domain_tables_mapping.json non trouvé")
            return {}
        except Exception as e:
            print(f"❌ Erreur chargement domain mapping: {e}")
            return {}
    
    # def process_parent_question(self, question: str, user_id: int) -> Tuple[str, Any]:
    #     """Traite une question posée par un parent avec restrictions de sécurité"""
    #     cached = self.cache.get_cached_query(question, current_user_id=user_id)
    #     if cached:
    #         sql_template, variables = cached
    #         sql_query = sql_template
    #         for column, value in variables.items():
    #             sql_query = sql_query.replace(f"{{{column}}}", value)
            
    #         print("⚡ Requête parent récupérée depuis le cache")
    #         try:
    #             result = self.db.run(sql_query)
    #             return sql_query, self.format_result(result, question)
    #         except Exception as db_error:
    #             return sql_query, f"❌ Erreur d'exécution SQL : {str(db_error)}"
        
    #     # Si pas trouvé dans le cache, utiliser le LLM
    #     children_ids = self.get_user_children_ids(user_id)
    #     if not children_ids:
    #         return "", "❌ Aucun enfant trouvé pour ce parent ou erreur d'accès."
        
    #     print(f"🔒 Restriction parent - Enfants autorisés: {children_ids}")
    #     children_ids_str = ','.join(map(str, children_ids))

    #     prompt = PARENT_PROMPT_TEMPLATE.format(
    #         input=question,
    #         table_info=self.db.get_table_info(),
    #         relevant_domain_descriptions="\n".join(self.domain_descriptions.values()),
    #         relations=self.relations_description,
    #         user_id=user_id,
    #         children_ids=children_ids_str
    #     )

    #     llm_response = self.ask_llm(prompt)
    #     sql_query = llm_response.replace("```sql", "").replace("```", "").strip()

    #     if not sql_query:
    #         return "", "❌ La requête générée est vide."

    #     # Validation de sécurité pour les parents
    #     if not self.validate_parent_access(sql_query, children_ids):
    #         return "", "❌ Accès refusé: La requête ne respecte pas les restrictions parent."

    #     try:
    #         result = self.db.run(sql_query)
    #         formatted_result = self.format_result(result, question)
    #         self.cache.cache_query(question, sql_query)
    #         return sql_query, formatted_result
    #     except Exception as db_error:
    #         return sql_query, f"❌ Erreur d'exécution SQL : {str(db_error)}"
