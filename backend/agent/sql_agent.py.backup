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
from config.database import get_db_connection,get_db,CustomSQLDatabase
from tabulate import tabulate
import matplotlib.pyplot as plt
import pandas as pd
import matplotlib
import io
import base64
import matplotlib.pyplot as plt
import MySQLdb


matplotlib.use('Agg')  
plt.switch_backend('Agg')

logger = logging.getLogger(__name__)

class SQLAgent:
    def __init__(self, db=None, model="gpt-4o", temperature=0.3, max_tokens=500):
        self.db = db if db else get_db_connection()
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.last_generated_sql = ""
        self.query_history = []
        self.conversation_history = []
        self.cost_per_1k_tokens = 0.005  # par exemple

        try:
            self.schema = self.db.get_schema()
        except Exception as e:
            logger.warning(f"⚠️ Impossible de récupérer le schéma: {e}")
            self.schema = []

    def _serialize_data(self, data):
        if isinstance(data, (list, tuple)):
            return [self._serialize_data(item) for item in data]
        elif isinstance(data, dict):
            return {key: self._serialize_data(value) for key, value in data.items()}
        elif hasattr(data, 'isoformat'):
            return data.isoformat()
        elif isinstance(data, Decimal):
            return float(data)
        return data

    def load_prompt_for_query(self, query):
        query_lower = query.lower()
        extra_info = ""

        if any(word in query_lower for word in ["nom", "élève", "classe", "parent", "inscription"]):
            path = "agent/prompts/prompt_eleve.txt"
        elif any(word in query_lower for word in ["note", "matière", "absence", "emploi", "moyenne"]):
            path = "agent/prompts/prompt_pedagogie.txt"
            try:
                extra_info = "\n\n" + self.db.get_simplified_relations_text()
            except Exception as e:
                logger.error(f"Erreur récupération relations FK : {e}")
        elif any(word in query_lower for word in ["paiement", "tranche", "cantine", "montant", "transport"]):
            path = "agent/prompts/prompt_finance.txt"
        else:
            path = "agent/prompts/prompt_eleve.txt"

        try:
            with open(path, 'r', encoding='utf-8') as f:
                prompt = f.read()
            return prompt + extra_info
        except Exception as e:
            logger.error(f"Erreur chargement prompt: {e}")
            raise
    

    def generate_sql(self, natural_query):
        """Génère une requête SQL à partir d'une question en langage naturel"""
        try:
            prompt = self.load_prompt_for_query(natural_query)
            prompt += f"\n### Schéma de base de données:\n{json.dumps(self.schema, indent=2)}\n\n"
            prompt += f"### Question:\n{natural_query}\n### SQL:"
            
            messages = [{"role": "system", "content": prompt}]
            
            response = openai.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=200
            )
            
            sql = response.choices[0].message.content
            clean_sql = self._clean_sql(sql)
            
            # More robust validation
            if not clean_sql or "select" not in clean_sql.lower():
                raise ValueError("Requête SQL invalide générée")
                
            # Additional validation to prevent natural language in SQL
            if any(word in clean_sql.lower() for word in ["pour", "corriger", "erreur", "nous"]):
                raise ValueError("La requête contient du langage naturel")
                
            self._validate_sql(clean_sql)
            self.last_generated_sql = clean_sql
            return clean_sql
            
        except Exception as e:
            logger.error(f"Erreur dans generate_sql: {str(e)}")
            # Retry once with stricter instructions
            try:
                retry_prompt = prompt + "\nIMPORTANT: Ne générer QUE du code SQL valide, sans explications ni commentaires."
                messages = [{"role": "system", "content": retry_prompt}]
                
                response = openai.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.1,
                    max_tokens=200
                )
                
                sql = response.choices[0].message.content
                clean_sql = self._clean_sql(sql)
                self._validate_sql(clean_sql)
                self.last_generated_sql = clean_sql
                return clean_sql
                
            except Exception as retry_error:
                logger.error(f"Erreur dans la tentative de réessai: {str(retry_error)}")
                raise ValueError(f"Impossible de générer une requête SQL valide: {str(retry_error)}")
        
    def _clean_sql(self, text):
            """Nettoie et extrait le SQL du texte généré par l'IA"""
            sql = re.sub(r'```(sql)?|```', '', text)
            sql = re.sub(r'(?i)^\s*(?:--|#).*$', '', sql, flags=re.MULTILINE)
            return sql.strip().rstrip(';')
    def _strip_db_prefix(self, table_name):
            return table_name.split('.')[-1]
    def generate_sql(self, natural_query):
            """Génère une requête SQL à partir d'une question en langage naturel"""
            try:
                prompt = self.load_prompt_for_query(natural_query)
                prompt += f"\n### Schéma de base de données:\n{json.dumps(self.schema, indent=2)}\n\n"
                prompt += f"### Question:\n{natural_query}\n### SQL:"
                
                messages = [{"role": "system", "content": prompt}]
                
                response = openai.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.1,
                    max_tokens=200
                )
                
                sql = response.choices[0].message.content
                clean_sql = self._clean_sql(sql)  # Utilisation de _clean_sql au lieu de _extract_sql
                
                # Validation stricte avant retour
                self._validate_sql(clean_sql)
                self.last_generated_sql = clean_sql  # Stocke la dernière requête générée
                return clean_sql
                
            except Exception as e:
                logger.error(f"Erreur dans generate_sql: {str(e)}")
                raise ValueError(f"Impossible de générer une requête SQL valide: {str(e)}")
    def execute_natural_query(self, natural_query):
            try:
                sql = self.generate_sql(natural_query)
                result = self.db.execute_query(sql)
                
                if not result['success']:
                    error_msg = result['error']
                    logger.error(f"Erreur SQL: {error_msg}")
                    
                    # Tentative de correction automatique
                    corrected_sql = self._auto_correct(sql, error_msg)
                    if corrected_sql:
                        result = self.db.execute_query(corrected_sql)
                        if result['success']:
                            return self._format_results(result['data'], natural_query)
                    
                    raise ValueError(f"Erreur SQL: {error_msg}")
                    
                return self._format_results(result['data'], natural_query)
            
            except Exception as e:
                logger.error(f"Erreur dans execute_natural_query: {str(e)}")
                return None
        
    def _auto_correct(self, bad_sql, error_msg):
            try:
                correction_prompt = f"""
                Vous êtes un expert SQL. Corrigez cette requête en vous basant sur l'erreur et le schéma.

                Erreur: {error_msg}

                Requête incorrecte:
                ```sql
                {bad_sql}
                ```

                Schéma disponible:
                ```json
                {json.dumps(self.schema, indent=2)}
                ```

                Requête corrigée:
                ```sql
                """
                response = openai.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": correction_prompt}],
                    temperature=0,
                    max_tokens=500
                )
                corrected_sql = self._clean_sql(response.choices[0].message.content)  # Utilisation de _clean_sql
                if self._validate_sql(corrected_sql):
                    return corrected_sql
            except Exception as e:
                logger.error(f"Correction échouée: {str(e)}")
            return None
        
    def detect_graph_type(self, user_query, df_columns):
            user_query = user_query.lower()
            columns = [col.lower() for col in df_columns]
            
            # Détection basée sur la requête et les colonnes disponibles
            if any(k in user_query for k in ["évolution", "progress", "tendance", "historique"]):
                return "line"
            elif any(k in user_query for k in ["répartition", "pourcentage", "ratio", "proportion"]):
                return "pie"
            elif any(k in user_query for k in ["comparaison", "nombre", "count", "somme", "total"]):
                if any(k in columns for k in ["date", "année", "mois", "jour", "semaine"]):
                    return "line"
                elif any(k in columns for k in ["délégation", "localité", "région", "ville", "classe"]):
                    return "bar"
                else:
                    return "bar"
            return None
    def extract_name_from_query(self, query):
            pattern = r"attestation de\s+([A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+)*)"
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return match.group(1).strip()
            return None

    def get_student_info_by_name(self, full_name):
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
                cursor.close()
                conn.close()

                if not row:
                    return None

                return row

            except Exception as e:
                logger.error(f"Erreur get_student_info_by_name: {str(e)}")
                return None
    def _validate_sql(self, sql):
        """
        Valide la syntaxe SQL et vérifie l'existence des tables et colonnes utilisées.
        """
        sql_lower = sql.lower()

        #  Protection contre les requêtes destructives
        forbidden_keywords = ['drop', 'delete', 'update', 'insert', ';--', 'exec']
        if any(keyword in sql_lower for keyword in forbidden_keywords):
            raise ValueError("❌ Commande SQL dangereuse détectée")

        try:
            with get_db_cursor() as cursor:
                # ✅ Validation de la requête avec EXPLAIN
                cursor.execute(f"EXPLAIN {sql}")

                # 📊 Vérifie si les tables utilisées sont connues
                used_tables = set(re.findall(r'\bfrom\s+([a-zA-Z0-9_.]+)|\bjoin\s+([a-zA-Z0-9_.]+)', sql_lower))
                table_list = [t for group in used_tables for t in group if t]
                known_tables = set(self.schema)

                for table in table_list:
                    clean_table = self._strip_db_prefix(table)
                    if clean_table not in known_tables:
                        raise ValueError(f"❌ Table inconnue : `{clean_table}`")

                

            return True

        except Exception as e:
            raise ValueError(f"❌ Requête invalide détectée : {str(e)}")

    def get_response(self, user_query):
            if "attestation de présence" in user_query.lower():
                from pdf_utils.attestation import export_attestation_pdf
                return {
                    "response": f"L'attestation a été générée : <a href='/{pdf_path.replace(os.sep, '/')}' download>Télécharger le PDF</a>"
                }

            try:
                # Version simplifiée sans gestion des tokens
                self.conversation_history.append({'role': 'user', 'content': user_query})

                db_results = self.execute_natural_query(user_query)
                if not db_results:
                    return {"response": "Aucun résultat."}

                messages = [
                    {
                        "role": "system", 
                        "content": "Tu es un assistant pédagogique. Reformule les résultats SQL bruts en réponse naturelle, utile et claire."
                    },
                    {
                        "role": "user", 
                        "content": f"Question: {user_query}\nRequête SQL générée: {self.last_generated_sql}\nRésultats:\n{json.dumps(db_results, ensure_ascii=False)[:800]}\n\nFormule une réponse claire et concise en français avec les données ci-dessus."
                    }
                ]

                response = openai.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=400
                )

                response_text = response.choices[0].message.content.strip()
                self.conversation_history.append({'role': 'assistant', 'content': response_text})
                # self._trim_history()

                return {
                    "response": response_text,
                    "sql_query": self.last_generated_sql,
                    "results": db_results
                }

            except Exception as e:
                logger.error(f"Erreur: {str(e)}", exc_info=True)
                return {"response": "Une erreur est survenue lors du traitement de la requête."}
    def generate_auto_graph(self, df, graph_type=None):
            if df.empty or len(df) < 2:
                return None
                
            try:
                # Nettoyage des données
                df = df.dropna()
                
                # Détection automatique si aucun type spécifié
                if not graph_type:
                    numeric_cols = df.select_dtypes(include='number').columns
                    categorical_cols = df.select_dtypes(exclude='number').columns
                    
                    if len(numeric_cols) == 1 and len(categorical_cols) >= 1:
                        if len(df) <= 7:
                            graph_type = "pie"
                        elif len(df) > 7 and any(col in categorical_cols[0].lower() for col in ["date", "année", "mois"]):
                            graph_type = "line"
                        else:
                            graph_type = "bar"
                
                # Génération du graphique
                plt.figure(figsize=(10, 6))
                
                if graph_type == "pie":
                    x_col = df.columns[0]
                    y_col = df.columns[1]
                    df.plot.pie(y=y_col, labels=df[x_col], autopct='%1.1f%%', legend=False)
                    plt.title(f"Répartition par {x_col}")
                    
                elif graph_type == "line":
                    x_col = df.columns[0]
                    y_col = df.columns[1]
                    plt.plot(df[x_col], df[y_col], marker='o')
                    plt.title(f"Évolution de {y_col} par {x_col}")
                    plt.xlabel(x_col)
                    plt.ylabel(y_col)
                    plt.xticks(rotation=45)
                    
                elif graph_type == "bar":
                    x_col = df.columns[0]
                    y_cols = df.columns[1:]
                    df.plot.bar(x=x_col, y=y_cols)
                    plt.title(f"Comparaison de {', '.join(y_cols)} par {x_col}")
                    plt.xticks(rotation=45)
                    
                plt.tight_layout()
                
                # Conversion en base64
                img = io.BytesIO()
                plt.savefig(img, format='png', bbox_inches='tight')
                img.seek(0)
                encoded = base64.b64encode(img.getvalue()).decode('utf-8')
                plt.close()
                
                return f"data:image/png;base64,{encoded}"
                
            except Exception as e:
                logger.error(f"Erreur génération graphique: {str(e)}")
                return None
    def _format_results(self, data, user_query):
            if not data:
                return {"response": "Aucun résultat trouvé."}
            
            try:
                df = pd.DataFrame(data)
                response = {
                    "sql_query": self.last_generated_sql,
                    "data": df.to_dict('records'),
                    "response": f"{len(df)} résultats trouvés"
                }
                
                # Générer un graphique si possible
                graph_type = self.detect_graph_type(user_query, df.columns)
                if len(df) > 1:  # Uniquement si assez de données
                    graph = self.generate_auto_graph(df, graph_type)
                    if graph:
                        response["graph"] = graph
                        
                return response
                
            except Exception as e:
                logger.error(f"Erreur formatage résultats: {str(e)}")
                return {
                    "response": "Erreur de formatage des résultats",
                    "error": str(e)
                }