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
from config.database import get_db_connection
from tabulate import tabulate
import matplotlib.pyplot as plt
import pandas as pd
import matplotlib
import io
import base64
import matplotlib.pyplot as plt

matplotlib.use('Agg')  # Important pour les environnements sans affichage
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
            sql = """
            SELECT 
                ei.NomPrenomFr AS nom,
                e.DateNaissance AS date_naissance,
                IFNULL(e.LieuNaissance, e.AutreLieuNaissance) AS lieu_de_naissance,
                ei.nomclassefr AS classe,
                e.IdPersonne AS matricule
            FROM 
                eleveinscri ei
            JOIN 
                eleve e ON ei.NomPrenomFr = %s
            WHERE 
                ei.NomPrenomFr = %s
            LIMIT 1;
            """
            result = self.db.execute_query(sql, (full_name, full_name))
            if not result['success'] or not result['data']:
                return None

            row = result['data'][0]
            keys = ['nom', 'date_naissance', 'lieu_de_naissance', 'classe', 'matricule']
            return dict(zip(keys, row)) if isinstance(row, (list, tuple)) else row

        except Exception as e:
            logger.error(f"Erreur get_student_info_by_name: {str(e)}")
            return None





    @staticmethod
    def create_clean_graph(data_dict):
        import matplotlib.pyplot as plt
        import io
        import base64

        labels = list(data_dict.keys())
        values = list(data_dict.values())

        plt.figure(figsize=(10, max(6, len(labels) * 0.4)))
        bars = plt.barh(labels, values, color='skyblue')

        min_val = min(values)
        max_val = max(values)
        plt.xlim(max(0, min_val - 5), max_val + 5)

        for bar, val in zip(bars, values):
            plt.text(val + 1, bar.get_y() + bar.get_height() / 2,
                    str(val), va='center', ha='left')

        plt.title("Valeurs par catégorie")
        plt.xlabel("Valeur")
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close()
        buf.seek(0)

        img_bytes = buf.read()
        print(base64.b64encode(img_bytes).decode('utf-8'))

        return base64.b64encode(img_bytes).decode('utf-8')



    def generate_auto_graph(self, df, graph_type=None):
        if df.empty or len(df.columns) < 2:
            return None

        plt.style.use('ggplot' if 'ggplot' in plt.style.available else 'default')
        plt.rcParams['font.family'] = 'DejaVu Sans'
        plt.rcParams['axes.unicode_minus'] = False

        try:
            # Colonnes à exclure (techniques ou non pertinentes)
            exclude_cols = ['id', 'ids', 'anneescolaire', 'année scolaire', 'annee_scolaire']

            # Colonnes numériques et catégorielles utiles
            numeric_cols = [col for col in df.select_dtypes(include='number').columns if col.lower() not in exclude_cols]
            categorical_cols = [col for col in df.select_dtypes(exclude='number').columns if col.lower() not in exclude_cols]

            if not numeric_cols or not categorical_cols:
                return None  # Besoin d'au moins une de chaque

            # Choix des colonnes à afficher
            y_col = numeric_cols[0]
            x_col = categorical_cols[0]

            df = df[[x_col, y_col]].dropna()
            df = df.sort_values(by=y_col, ascending=False)

            x = df[x_col].astype(str)
            y = df[y_col].astype(float)

            # Création du graphique (barres verticales)
            fig, ax = plt.subplots(figsize=(max(8, len(df)*0.6), 6))

            bars = ax.bar(x, y, color='skyblue')

            # Affichage des valeurs au-dessus des barres
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2,
                        height + max(y)*0.01,
                        f'{int(height)}',
                        ha='center', va='bottom', fontsize=9)

            ax.set_xlabel(x_col)
            ax.set_ylabel(y_col)
            ax.set_title(f"{y_col} par {x_col}")
            ax.grid(axis='y', linestyle='--', alpha=0.6)
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout(pad=2)

            # Encodage en base64
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
            plt.close(fig)
            buf.seek(0)
            encoded = base64.b64encode(buf.read()).decode('utf-8')
            buf.close()

            return f"data:image/png;base64,{encoded}"

        except Exception as e:
            print(f"Erreur lors de la génération du graphique : {str(e)}")
            return None


    def _format_results(self, data, user_query=None):
        serialized_data = self._serialize_data(data)
        if not serialized_data:
            return "Aucun résultat trouvé."

        df = pd.DataFrame(serialized_data)

        # Détection du type de graphique demandé dans la requête utilisateur
        graph_type = None
        if user_query:
            graph_type = self.detect_graph_type(user_query)

        # Logique existante avec passage de graph_type
        if (len(df.columns) >= 2 and 
            any('niveau' in col.lower() for col in df.columns) and 
            any('inscription' in col.lower() for col in df.columns)):
            return self.generate_auto_graph(df, graph_type=graph_type)
        
        if df.empty:
            return "Aucun résultat trouvé."

        if len(df) > 10 or len(df.select_dtypes(include='number').columns) > 1:
            return self.generate_auto_graph(df, graph_type=graph_type)

        return tabulate(df, headers='keys', tablefmt='github')


    def get_response(self, user_query):
        if "attestation de présence" in user_query.lower():
            from pdf_utils.attestation import export_attestation_pdf
            donnees_etudiant = {
                "nom": "Rania Zahraoui",
                "date_naissance": "15/03/2005",
                "matricule": "2023A0512",
                "etablissement": "Lycée Pilote de Sfax",
                "classe": "3ème Sciences",
                "annee_scolaire": "2024/2025",
                "lieu": "Sfax"
            }
            pdf_path = export_attestation_pdf(donnees_etudiant)
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