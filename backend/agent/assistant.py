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
    
        def __init__(self,db=None   ):
            self.db = db if db is not None else get_db_connection()
            self.sql_agent = SQLAgent(self.db)
            self.relations_description = self._safe_load_relations()
            self.domain_descriptions = self._safe_load_domain_descriptions()
            self.domain_to_tables_mapping = self._safe_load_domain_to_tables_mapping()
            self.ask_llm = ask_llm
            self.cache = CacheManager()
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
                
                # Get connection - CORRIGER ICI
                connection = get_db()
                cursor = connection.cursor()
                
                # Execute query
                cursor.execute(query, (user_id,))
                users = cursor.fetchall()
                
                # Process results - CORRIGER la clé
                if users:
                    children_ids = [user['id_enfant'] for user in users]
                    logger.info(f"✅ Found {len(children_ids)} children for parent {user_id}")
                
                return children_ids
            except Exception as e:
                logger.error(f"❌ Error getting children for parent {user_id}: {str(e)}")
                return []
            finally:
                # Cleanup
                try:
                    if cursor:
                        cursor.close()
                    
                    # Ne fermer que si c'est une connexion directe
                    if connection and hasattr(connection, '_direct_connection'):
                        connection.close()
                        logger.debug("🔌 Closed direct MySQL connection")
                except Exception as close_error:
                    logger.warning(f"⚠️ Error during cleanup: {str(close_error)}")
        def load_question_templates(self) -> list:
            print("🔍 Chargement des templates de questions...")
            try:
                # Chemin absolu plus fiable
                templates_path = Path(__file__).parent / 'templates_questions.json'
                
                # Vérification approfondie du fichier
                if not templates_path.exists():
                    print(f"⚠️ Fichier non trouvé, création: {templates_path}")
                    templates_path.write_text('{"questions": []}', encoding='utf-8')
                    return []

                content = templates_path.read_text(encoding='utf-8').strip()
                if not content:
                    print("⚠️ Fichier vide, réinitialisation")
                    templates_path.write_text('{"questions": []}', encoding='utf-8')
                    return []

                # Validation JSON stricte
                try:
                    data = json.loads(content)
                    if not isinstance(data.get("questions", []), list):
                        raise ValueError("Format invalide: 'questions' doit être une liste")
                    
                    # Validation de chaque template
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
            print(f"🔍 Recherche de template pour la question")
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
        def _filter_table_columns(self, table_block: str, question: str) -> str:
            lines = table_block.split('\n')
            if not lines:  # ← Ajouter cette vérification
                return table_block
                
            filtered_lines = [lines[0]]  
            
            for line in lines[1:]:
                if any(keyword.lower() in line.lower() for keyword in ['nom', 'prenom', 'date', 'absence']):
                    filtered_lines.append(line)
            
            return '\n'.join(filtered_lines) 
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
        def _format_tabular_result(self, headers: list, rows: list, question: str = "") -> str:
            """Formate les résultats sous forme de tableau"""
            output = [f"**{question}**"] if question else []
            output.append(" | ".join(headers))
            output.append("-+-".join(['-' * len(h) for h in headers]))
            for row in rows:
                output.append(" | ".join(row))
            return "\n".join(output) 
        def _format_string_result(self, result_str: str, question: str = "") -> str:
            """Formate un résultat de type string retourné par db.run()"""
            if not result_str.strip():
                return "✅ Requête exécutée mais aucun résultat trouvé."
            
            # Si c'est un résultat simple (nombre, etc.)
            lines = result_str.strip().split('\n')
            if len(lines) == 1:
                return f"Résultat : {lines[0]}"
            
            # Si c'est un tableau de résultats
            output = [f"**{question}**"] if question else []
            output.extend(lines)
            return "\n".join(output)        
        def get_tables_from_domains(self, domains: List[str], domain_to_tables_map: Dict[str, List[str]]) -> List[str]:
            """Retrieves all tables associated with the given domains."""
            tables = []
            for domain in domains:
                tables.extend(domain_to_tables_map.get(domain, []))
            return sorted(list(set(tables)))                
        def debug_table_info(self, tables=None):
            """Debug pour voir exactement ce que retourne get_table_info"""
            try:
                if tables:
                    table_info = self.db.get_table_info(table_names=tables)
                else:
                    table_info = self.db.get_table_info()
                
                print("="*50)
                print("DEBUG TABLE INFO:")
                print("="*50)
                print(table_info)
                print("="*50)
                return table_info
            except Exception as e:
                print(f"❌ Erreur debug_table_info: {e}")
                return "Erreur debug"            
        def _safe_load_relations(self) -> str:
            """Charge les relations avec gestion d'erreurs"""
            try:
                relations_path = Path(__file__).parent / 'prompts' / 'relations.txt'  
                print(f"🔍 Tentative de chargement depuis : {relations_path.absolute()}")# Log du chemin

                          
                if relations_path.exists():
                    content = relations_path.read_text(encoding='utf-8')
                    print(f"✅ Contenu chargé (premières 50 lignes) :\n{content[:500]}...")  # Aperçu du contenu
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
        def _safe_load_question_templates(self) -> list:
            """Charge les templates avec gestion d'erreurs robuste"""
            try:
                templates_path = Path(__file__).parent / 'templates_questions.json'
                
                if not templates_path.exists():
                    print(f"⚠️ Création fichier templates: {templates_path}")
                    templates_path.write_text('{"questions": []}', encoding='utf-8')
                    return []

                content = templates_path.read_text(encoding='utf-8').strip()
                if not content:
                    return []

                data = json.loads(content)
                if not isinstance(data.get("questions", []), list):
                    return []
                
                valid_templates = []
                for template in data["questions"]:
                    if all(key in template for key in ["template_question", "requete_template"]):
                        valid_templates.append(template)
                
                return valid_templates

            except Exception as e:
                print(f"❌ Erreur chargement templates: {e}")
                return []
        def get_student_info_by_name(self, full_name):
            """Récupère les infos d'un élève depuis la base de données"""
            return self.sql_agent.get_student_info_by_name(full_name)
        def _trim_history(self):
            while self.conversation_history and sum(msg['tokens'] for msg in self.conversation_history) > self.max_history_tokens:
                self.conversation_history.pop(0)
        def _build_response(self, response, sql_query=None, db_results=None, tokens=0, cost=0):
            return {
                "response": response,
                "sql_query": sql_query,
                "db_results": db_results,
                "tokens_used": tokens,
                "estimated_cost_usd": cost,
                "conversation_id": id(self.conversation_history)
            }
        def ask_question(self, question: str, user_id: Optional[int] = None, roles: Optional[List[str]] = None) -> Tuple[str, str]:
            """Méthode centralisée : authentifiée, compatible rôle, fallback LLM, cache, validation parent"""
            import re

            if roles is None:
                roles = []

            from security.roles import is_super_admin, is_parent, validate_parent_access

            if roles and not (is_super_admin(roles) or is_parent(roles)):
                return "", f"❌ Accès refusé : Rôles non autorisés. Requis : ROLE_SUPER_ADMIN ou ROLE_PARENT"

            # 1. Vérifie le cache
            cache_manager = self.cache if is_super_admin(roles) else self.cache
            cached = cache_manager.get_cached_query(question)
            if cached:
                sql_query = cached.get("sql_query")
                result = cached.get("result", "")
                return sql_query, result or self.format_sql_result([], question)

            # 2. Essaye un template
            template_match = self.find_matching_template(question)
            if template_match:
                sql_query = self.generate_query_from_template(
                    template_match["template"],
                    template_match.get("variables", {})
                )
                try:
                    conn = get_db()
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute(sql_query)
                    result = cursor.fetchall()
                    cursor.close()
                    if hasattr(conn, '_direct_connection'):
                        conn.close()
                    formatted = self.format_sql_result(result, question)
                    cache_manager.cache_query(question, sql_query)
                    return sql_query, formatted
                except Exception as e:
                    return sql_query, f"❌ Erreur d'exécution SQL : {str(e)}"

            # Choix du prompt
            if is_super_admin(roles):
                prompt = ADMIN_PROMPT_TEMPLATE.format(
                    input=question,
                    # table_info="\n\n".join(relevant_blocks),
                    # relevant_domain_descriptions=domain_desc or "informations générales",
                    relations=self.relations_description
                )
            elif  is_parent(roles):
                children_ids = self.get_user_children_ids(user_id)
                if not validate_parent_access(sql_query, children_ids):
                    return "", "❌ Accès refusé: La requête ne respecte pas les restrictions parent."
                prompt = PARENT_PROMPT_TEMPLATE.format(
                    input=question,
                    # table_info="\n\n".join(relevant_blocks),
                    relevant_domain_descriptions=domain_desc or "informations spécifiques aux enfants",
                    relations=self.relations_description,
                    user_id=user_id,
                    children_ids=",".join(map(str, children_ids))
                )
            else:
                prompt = PROMPT_TEMPLATE.format(
                    input=question,
                    # table_info="\n\n".join(relevant_blocks),
                    # relevant_domain_descriptions=domain_desc,
                    relations=self.relations_description
                )
            # Appel LLM
            sql_query = self.ask_llm(prompt).replace("```sql", "").replace("```", "").strip()
            if not sql_query:
                return "", "❌ La requête générée est vide."

            if is_parent(roles):
                children_ids = self.get_user_children_ids(user_id)
                if not validate_parent_access(sql_query, children_ids):
                    return "", "❌ Accès refusé: La requête ne respecte pas les restrictions parent."

            # Exécution finale
            try:
                conn = get_db()
                cursor = conn.cursor(dictionary=True)
                cursor.execute(sql_query)
                result = cursor.fetchall()
                cursor.close()
                if hasattr(conn, '_direct_connection'):
                    conn.close()
                formatted_result = self.format_sql_result(result, question)
                cache_manager.cache_query(question, sql_query)
                return sql_query, formatted_result
            except Exception as db_error:
                return sql_query, f"❌ Erreur d'exécution SQL : {str(db_error)}"
        def format_structured_result(self, result: Any, question: str = "") -> str:
            """Formate les résultats SQL de manière structurée"""
            # ✅ Réutiliser la même logique que format_sql_result
            return self.format_sql_result(result, question)
        def get_response(self, user_query, user_id=None):
            if user_id:
                print(f"🔐 Utilisateur connecté : {user_id}")
            if "bulletin" in user_query.lower():
                full_name = self.extract_name_from_query(user_query)
                if not full_name:
                    return {"response": "Veuillez préciser le nom de l'élève."}
                
                student_info = self.get_student_info_by_name(full_name)
                if not student_info:
                    return {"response": f"Aucun élève trouvé avec le nom {full_name}"}

                from agent.pdf_utils.bulletin import export_bulletin_pdf
                student_id = student_info.get("matricule")
                result = export_bulletin_pdf(student_id)

                if result["status"] == "success":
                    filename = result["filename"]
                    return {
                        "response": f"✅ Bulletin généré pour {full_name} : <a href='/static/bulletins/{filename}' download>Télécharger</a>",
                        "pdf_url": f"/static/bulletins/{filename}"
                    }
                else:
                    return {"response": "Erreur lors de la génération du bulletin"}

            if "attestation" in user_query.lower():
                # Extract student name from query
                
                student_name = SQLAgent.extract_name_from_query(user_query)
                if not student_name:
                    return {"response": "Veuillez spécifier le nom complet de l'élève pour générer l'attestation."}
                
                # Get student info from database
                student_info = self.get_student_info_by_name(student_name)
                if not student_info:
                    return {"response": f"Aucun élève trouvé avec le nom {student_name}"}
                
                # Generate PDF with actual student data
                pdf_result =export_attestation_pdf(student_info)

                if pdf_result["status"] == "success":
                    pdf_path = pdf_result["path"]
                    return {
                        "response": f"L'attestation a été générée : <a href='/{pdf_path.replace(os.sep, '/')}' download>Télécharger le PDF</a>"
                    }
                else:
                    return {
                        "response": f"❌ Échec lors de la génération du PDF : {pdf_result.get('message', 'Erreur inconnue')}"
                    }
            try:
                # Utilisation de la logique SQL existante
                sql_query, formatted_result = self.ask_question(user_query)
                
                # Generate natural language response using LLM
                if formatted_result and not formatted_result.startswith("❌"):
                    prompt = f"""
                    Question de l'utilisateur: {user_query}
                    Requête SQL générée: {sql_query}
                    Résultats: {formatted_result[:1000]}
                    
                    Tu es un assistant pédagogique. Reformule ces résultats SQL bruts en réponse naturelle, utile et claire en français.
                    """
                    
                    try:
                        natural_response = self.ask_llm(prompt)
                        return {
                            "response": natural_response,
                            "sql_query": sql_query,
                            "raw_results": formatted_result
                        }
                    except Exception as llm_error:
                        # Fallback: retourner le résultat formaté si LLM échoue
                        return {
                            "response": formatted_result,
                            "sql_query": sql_query,
                            "raw_results": formatted_result,
                            "llm_error": str(llm_error)
                        }
                else:
                    return {
                        "response": formatted_result or "Aucun résultat trouvé.",
                        "sql_query": sql_query
                    }
                    
            except Exception as e:
                return {
                    "response": f"Désolé, une erreur s'est produite: {str(e)}",
                    "sql_query": None,
                    "error": str(e)
                }                
        def format_sql_result(self, result: Any, question: str = "") -> str:
            """Formate les résultats SQL de manière robuste"""
            if not result:
                return "✅ Requête exécutée mais aucun résultat trouvé."

            try:
                # Cas 1: Résultat est déjà une string
                if isinstance(result, str):
                    return self._format_string_result(result, question)
                
                # Cas 2: Résultat est un dictionnaire (pour COUNT, SUM etc.)
                if isinstance(result, dict):
                    return "\n".join([f"{k}: {v}" for k, v in result.items()])
                
                # Cas 3: Résultat est une liste
                if isinstance(result, list):
                    if not result:
                        return "✅ Requête exécutée mais aucun résultat trouvé."
                        
                    # Cas 3.1: Liste de dictionnaires
                    if isinstance(result[0], dict):
                        headers = list(result[0].keys())
                        rows = [[str(row.get(h, '')) for h in headers] for row in result]
                        return self._format_tabular_result(headers, rows, question)
                    
                    # Cas 3.2: Liste de tuples/listes
                    elif isinstance(result[0], (tuple, list)):
                        if cursor := getattr(self.db, '_last_cursor', None):
                            headers = [desc[0] for desc in cursor.description]
                        else:
                            headers = [f"Colonne_{i+1}" for i in range(len(result[0]))]
                        
                        rows = [[str(cell) for cell in row] for row in result]
                        return self._format_tabular_result(headers, rows, question)
                
                # Cas par défaut
                return f"Résultat : {str(result)}"
            
            except Exception as e:
                return f"❌ Erreur de formatage : {str(e)}\nRésultat brut: {str(result)[:500]}"       
        def validate_parent_access(self, sql_query: str, children_ids: List[int]) -> bool:
            """Valide qu'une requête SQL respecte les restrictions parent"""
            if not children_ids:
                return False
            
            sql_lower = sql_query.lower()
            
            # Vérifier que la requête contient une restriction sur les enfants
            children_str = ','.join(map(str, children_ids))
            
            # Patterns de restrictions valides
            valid_patterns = [
                f"e.idpersonne in ({children_str})",
                f"p.id in ({children_str})",
                f"eleve.idpersonne in ({children_str})"
            ]
            
            return any(pattern in sql_lower for pattern in valid_patterns)
        def _process_admin_question(self, question: str) -> tuple[str, str]:
            """Traite une question avec accès admin complet"""
            
            # 1. Vérifier le cache
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
            prompt = ADMIN_PROMPT_TEMPLATE.format(
                input=question,
                table_info=self.db.get_table_info(),
                relevant_domain_descriptions="\n".join(self.domain_descriptions.values()),
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
            
            cached = self.cache.get_cached_query(question)
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
            

            prompt = PARENT_PROMPT_TEMPLATE.format(
                input=question,
                table_info=self.db.get_table_info(),
                relevant_domain_descriptions="\n".join(self.domain_descriptions.values()),
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
                self.cache.cache_query(question, sql_query)
                return sql_query, formatted_result
            except Exception as db_error:
                return sql_query, f"❌ Erreur d'exécution SQL : {str(db_error)}"