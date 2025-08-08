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
from config.database import get_db_connection,get_db
from tabulate import tabulate
import matplotlib.pyplot as plt
import pandas as pd
import matplotlib
import io
import base64
import matplotlib.pyplot as plt
import MySQLdb


matplotlib.use('Agg')  #
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
        try:
            prompt = self.load_prompt_for_query(natural_query)
            prompt += f"\n### Question:\n{natural_query}\n### Format:\nRetournez UNIQUEMENT la requête SQL valide, SANS commentaires, SANS backticks ```, SANS texte explicatif."

            messages = [{"role": "system", "content": prompt}]

            response = openai.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            raw_sql = response.choices[0].message.content
            clean_sql = self._extract_sql(raw_sql)

            if not clean_sql or "SELECT" not in clean_sql.upper():
                raise ValueError("Réponse OpenAI ne contient pas de SQL valide")

            self.last_generated_sql = clean_sql
            return clean_sql

        except Exception as e:
            logger.error(f"Erreur génération SQL: {str(e)}")
            raise

    def _extract_sql(self, text):
        sql = re.sub(r'```(sql)?|```', '', text)
        sql = re.sub(r'(?i)^\s*(?:--|#).*$', '', sql, flags=re.MULTILINE)
        return sql.strip().rstrip(';')

    def _strip_db_prefix(self, table_name):
        return table_name.split('.')[-1]

    def _validate_sql(self, sql):
        sql_lower = sql.lower()
        forbidden = ['drop', 'delete', 'update', 'insert', ';--', 'exec']
        if any(cmd in sql_lower for cmd in forbidden):
            raise ValueError("Commande SQL dangereuse détectée")

        used_tables = set(re.findall(r'\bfrom\s+([a-zA-Z0-9_.]+)|\bjoin\s+([a-zA-Z0-9_.]+)', sql_lower))
        for table in (t for group in used_tables for t in group if t):
            clean_table = self._strip_db_prefix(table)
            if clean_table not in self.schema:
                raise ValueError(f"Table inconnue: {table}")
        return True

    def execute_natural_query(self, natural_query):
        try:
            sql = self.generate_sql(natural_query)
            result = self.db.execute_query(sql)
            
            if not result['success']:
                # Handle error case
                corrected = self._auto_correct(sql, result['error'])
                if corrected:
                    result = self.db.execute_query(corrected)
                    if result['success']:
                        return self._format_results(result['data'], user_query=natural_query)
                raise ValueError(f"Erreur SQL: {result['error']}")
                
            return self._format_results(result['data'], user_query=natural_query)
        except Exception as e:
            logger.error(f"Erreur exécution: {str(e)}")
            raise
    def _auto_correct(self, bad_sql, error_msg):
        try:
            correction_prompt = f"""
Corrige cette requête SQL :
Requête : {bad_sql}
Erreur : {error_msg}
Schéma disponible :
{json.dumps(self.schema, indent=2)}
"""
            response = openai.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": correction_prompt}],
                temperature=0,
                max_tokens=500
            )
            corrected_sql = self._extract_sql(response.choices[0].message.content)
            if self._validate_sql(corrected_sql):
                return corrected_sql
        except Exception as e:
            logger.error(f"Correction échouée: {str(e)}")
        return None

    def detect_graph_type(self, user_query):
        user_query = user_query.lower()
        if any(k in user_query for k in ["pie", "camembert", "diagramme circulaire"]):
            return "pie"
        elif any(k in user_query for k in ["histogramme", "bar chart", "barres"]):
            return "bar"
        elif any(k in user_query for k in ["ligne", "line chart", "courbe"]):
            return "line"
        else:
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


    def get_response(self, user_query):
        if "attestation de présence" in user_query.lower():
            from pdf_utils.attestation import export_attestation_pdf
            # donnees_etudiant = {
            #     "nom": "Rania Zahraoui",
            #     "date_naissance": "15/03/2005",
            #     "matricule": "2023A0512",
            #     "etablissement": "Lycée Pilote de Sfax",
            #     "classe": "3ème Sciences",
            #     "annee_scolaire": "2024/2025",
            #     "lieu": "Sfax"
            # }
            # pdf_path = export_attestation_pdf(donnees_etudiant)
            return {
                "response": f"L'attestation a été générée : <a href='/{pdf_path.replace(os.sep, '/')}' download>Télécharger le PDF</a>"
            }

        try:
            query_tokens = self.count_tokens(user_query)
            self.conversation_history.append({'role': 'user', 'content': user_query, 'tokens': query_tokens})

            db_results = self.execute_natural_query(user_query)
            if not db_results:
                return {"response": "Aucun résultat."}

            messages = [
                {"role": "system", "content": "Tu es un assistant pédagogique. Reformule les résultats SQL bruts en réponse naturelle, utile et claire."},
                {"role": "user", "content": f"Question: {user_query}\nRequête SQL générée: {self.last_generated_sql}\nRésultats:\n{json.dumps(db_results, ensure_ascii=False)[:800]}\n\nFormule une réponse claire et concise en français avec les données ci-dessus."}
            ]

            response = openai.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=400
            )

            response_text = response.choices[0].message.content.strip()
            response_tokens = self.count_tokens(response_text)
            self.conversation_history.append({'role': 'assistant', 'content': response_text, 'tokens': response_tokens})
            self._trim_history()

            total_tokens = query_tokens + response_tokens
            cost = total_tokens / 1000 * self.cost_per_1k_tokens

            return {
                "response": response_text,
                "sql_query": self.last_generated_sql,
                "results": db_results,
                "tokens_used": total_tokens,
                "cost_estimate": cost
            }

        except Exception as e:
            logger.error(f"Erreur: {str(e)}", exc_info=True)
            return {"response": "Une erreur est survenue lors du traitement de la requête."}
        
        
    def generate_auto_graph(self, df, graph_type):
        if df.empty:
            return "Aucun résultat à afficher."

        exclude_cols = ['id', 'ids', 'anneescolaire', 'année scolaire', 'annee_scolaire']
        numeric_cols = [col for col in df.select_dtypes(include='number').columns if col.lower() not in exclude_cols]
        categorical_cols = [col for col in df.select_dtypes(exclude='number').columns if col.lower() not in exclude_cols]

        if not numeric_cols or not categorical_cols:
            return df.to_markdown()

        x_col = categorical_cols[0]
        y_cols = numeric_cols
        
        if graph_type == "pie":
            df_grouped = df.groupby(x_col)[y_cols[0]].sum()
            plt.figure(figsize=(6, 6))
            df_grouped.plot(kind='pie', autopct='%1.1f%%', ylabel='', legend=False)
            plt.title(f"{y_cols[0]} par {x_col}")
            plt.tight_layout()

        elif graph_type == "line":
            print("Colonnes catégorielles:", categorical_cols)
            print("Colonnes numériques:", numeric_cols)
            print("x_col choisi:", x_col)

            order = ["1ère", "2ème", "3ème", "4ème", "5ème", "6ème", "7ème", "8ème", "9ème"]

            if 'niveau' in x_col.lower():
                df_sorted = df.copy()
                df_sorted[x_col] = df_sorted[x_col].str.strip().str.replace(" ", "").str.lower()
                order_clean = [x.lower() for x in order]
                df_sorted[x_col] = pd.Categorical(df_sorted[x_col], categories=order_clean, ordered=True)
                df_sorted = df_sorted.sort_values(x_col)
            elif 'date' in x_col.lower() or 'année' in x_col.lower():
                df_sorted = df.sort_values(x_col)
            else:
                df_sorted = df

            plt.figure(figsize=(10, 6))
            plt.plot(df_sorted[x_col], df_sorted[y_cols[0]], marker='o')
            plt.title(f"Évolution de {y_cols[0]} selon {x_col}")
            plt.xlabel(x_col)
            plt.ylabel(y_cols[0])
            plt.xticks(rotation=45)
            plt.tight_layout()

        elif graph_type == "bar":
            plt.figure(figsize=(10, 6))
            df.plot(x=x_col, y=y_cols, kind='bar')
            plt.title(f"{', '.join(y_cols)} par {x_col}")
            plt.xticks(rotation=45)
            plt.tight_layout()

        else:
            # Logique par défaut si aucun type précisé
            if len(y_cols) == 1 and df[x_col].nunique() <= 7:
                df_grouped = df.groupby(x_col)[y_cols[0]].sum()
                plt.figure(figsize=(6, 6))
                df_grouped.plot(kind='pie', autopct='%1.1f%%', ylabel='', legend=False)
                plt.title(f"{y_cols[0]} par {x_col}")
            elif 'date' in x_col.lower() or 'année' in x_col.lower() or pd.to_datetime(df[x_col], errors='coerce').notna().all():
                df_sorted = df.sort_values(x_col)
                plt.figure(figsize=(10, 6))
                df_sorted.plot(x=x_col, y=y_cols, kind='line', marker='o')
                plt.title(f"Évolution de {', '.join(y_cols)} selon {x_col}")
            else:
                plt.figure(figsize=(10, 6))
                df.plot(x=x_col, y=y_cols, kind='bar')
                plt.title(f"{', '.join(y_cols)} par {x_col}")

            plt.xticks(rotation=45)
            plt.tight_layout()

        # Générer le graphique en base64
        tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        tmp_path = tmpfile.name
        tmpfile.close()
        plt.savefig(tmp_path)
        plt.close()

        with open(tmp_path, 'rb') as f:
            img_bytes = f.read()
        encoded = base64.b64encode(img_bytes).decode('utf-8')

        return f"data:image/png;base64,{encoded}"




    def _format_results(self, data, user_query):
            serialized_data = self._serialize_data(data)
            print("🧪 Données brutes reçues:", data)
            print("🧪 Données sérialisées:", serialized_data)

            if not serialized_data:
                return {
                    "status": "success",
                    "message": "Requête exécutée mais aucun résultat trouvé.",
                    "data": None,
                    "sql_query": self.last_generated_sql
                }

            df = pd.DataFrame(serialized_data)
            print(f"DEBUG - DataFrame shape: {df.shape}")
            print(f"DEBUG - Columns: {df.columns.tolist()}")
            print(f"DEBUG - Head:\n{df.head()}")

            response = {
                "status": "success",
                "question": user_query,
                "sql_query": self.last_generated_sql,
                "data": df.to_dict('records'),
                "response": f"✅ {len(df)} résultats trouvés"
            }
            user_query = user_query.lower()
            print(f"{user_query}")
            if any(k in user_query for k in ["pie", "camembert", "diagramme circulaire"]):
                graph_type= "pie"
            elif any(k in user_query for k in ["histogramme", "bar chart", "barres"]):
                graph_type= "bar"
            elif any(k in user_query for k in ["ligne", "line chart", "courbe"]):
                graph_type= "line"
            else:
                graph_type= None

            if len(df.columns) >= 2 and not df.empty:
                try:
                    
                    print (f"type de graphique detecté :{graph_type}")
                    
                    
                    graph = self.generate_auto_graph(df, graph_type)
                    if graph:
                        response["graph"] = graph
                except Exception as e:
                    logger.error(f"Erreur génération graphique: {str(e)}")
                    response["graph_error"] = str(e)

            return response