# agent_openAI.py
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from dotenv import load_dotenv

import os
import mysql.connector
import json
import unicodedata
import time
from datetime import datetime
from typing import List, Optional, Tuple
import re

# =========================
# Configuration & Boot
# =========================
DEBUG = False  # logs techniques détaillés
SHOW_CONTEXT_IN_CLI = True     # toujours afficher le contexte extrait
SHOW_SQL_IN_CLI = True         # toujours afficher la SQL générée
MAX_CONTEXT_CHARS = 0          # 0 = pas de troncature en affichage

load_dotenv()
RAG_DB_PATH = "chroma_db"
COLLECTION_NAME = "rag_index"
CACHE_FILE_PATH = "question_cache.json"
HISTORY_FILE_PATH = "query_history.json"

CONTEXT_FILES = [
    "schema_description.json",
    "rag_table_relationships.json",
    "table_domains.json",
    "query_patterns.json",
]

mysql_config = {
    'host': os.getenv("MYSQL_HOST"),
    'port': int(os.getenv("MYSQL_PORT", "3306")),
    'user': os.getenv("MYSQL_USER"),
    'password': os.getenv("MYSQL_PASSWORD"),
    'database': os.getenv("MYSQL_DATABASE")
}

# Test MySQL au démarrage (échec = exit)
try:
    conn = mysql.connector.connect(**mysql_config)
    if DEBUG:
        print("✅ Connexion MySQL réussie.")
    conn.close()
except Exception as e:
    print(f"❌ ERREUR connexion MySQL : {e}")
    raise SystemExit(1)

# =========================
# Utilitaires généraux
# =========================
def normalize(text: str) -> str:
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'[^\w\s\-@\.]', '', text)
    return text.strip()

def chunk_text(text: str, max_length: int = 300) -> List[str]:
    sentences = re.split(r'(?<=[.?!])\s+', text)
    chunks, current = [], ""
    for s in sentences:
        if len(current) + len(s) < max_length:
            current += s + " "
        else:
            chunks.append(current.strip())
            current = s + " "
    if current:
        chunks.append(current.strip())
    return chunks

# --- helpers quoting & extraction (100% génériques) ---

def _normalize_smart_quotes(s: str) -> str:
    # guillemets typographiques -> standard
    return (s.replace("’", "'").replace("‘", "'")
             .replace("“", '"').replace("”", '"'))

def clean_sql(sql: str) -> str:
    # retire fences et espaces parasites, normalise guillemets
    sql = sql.replace("```sql", "").replace("```", "").strip()
    sql = _normalize_smart_quotes(sql)
    # retire un ; final optionnel
    sql = re.sub(r";\s*$", "", sql).strip()
    return sql

def extract_sql(text: str) -> Optional[str]:
    """
    Extrait la première requête SQL (SELECT/INSERT/UPDATE/DELETE) jusqu'au premier ';' ou fin de texte.
    Purement générique (pas de cas par cas).
    """
    txt = text.replace("```sql", "").replace("```", "")
    txt = _normalize_smart_quotes(txt).strip()
    m = re.search(r"(?is)\b(SELECT|INSERT|UPDATE|DELETE)\b.*?(?:;|$)", txt)
    if not m:
        return None
    sql = m.group(0)
    sql = sql.split(";", 1)[0]
    return clean_sql(sql)

def sanitize_sql_literals(sql: str) -> str:
    """
    Sanitize générique :
    - supprime tout backtick rencontré à l'intérieur d'une chaîne '...'
    - ferme une chaîne restée ouverte (quote manquante)
    - ne dépend d’aucun domaine métier
    """
    out = []
    in_str = False
    i = 0
    while i < len(sql):
        ch = sql[i]
        if ch == "'":
            out.append(ch)
            if in_str:
                # '' (quote échappée) -> garder et rester dans la chaîne
                if i + 1 < len(sql) and sql[i+1] == "'":
                    out.append("'")
                    i += 1
                else:
                    in_str = False
            else:
                in_str = True
        elif in_str and ch == "`":
            # supprime le backtick dans une chaîne
            pass
        else:
            out.append(ch)
        i += 1
    if in_str:
        out.append("'")
    return "".join(out)

def _make_embeddings():
    return OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=os.getenv("OPENAI_API_KEY"))

def _context_last_mtime() -> float:
    mts = [os.path.getmtime(f) for f in CONTEXT_FILES if os.path.exists(f)]
    return max(mts) if mts else 0.0

def _index_last_mtime() -> float:
    if not os.path.exists(RAG_DB_PATH):
        return 0.0
    try:
        return os.path.getmtime(RAG_DB_PATH)
    except Exception:
        return time.time()

def load_documents() -> List[Document]:
    docs: List[Document] = []

    # schema_description.json
    try:
        with open("schema_description.json", encoding="utf-8") as f:
            data = json.load(f)
            for entry in data.get("tables", []):
                table = entry.get("name")
                for col in entry.get("columns", []):
                    col_name = col.get("name", "")
                    col_type = col.get("type", "")
                    col_desc = col.get("description", "")
                    for chunk in chunk_text(col_desc or "", max_length=500):
                        docs.append(Document(
                            page_content=normalize(f"Table {table}  Colonne {col_name} {col_type}  {chunk}"),
                            metadata={"type": "column_schema", "table": table, "column": col_name, "source_file": "schema_description.json"}
                        ))
    except Exception as e:
        if DEBUG:
            print("⚠️ Erreur schema_description.json :", e)

    # rag_table_relationships.json
    try:
        with open("rag_table_relationships.json", encoding="utf-8") as f:
            data = json.load(f)
            for rel in data:
                relation = rel.get("relation", "")
                description = rel.get("description", "")
                block = f"{relation} — {description}".strip()
                text = normalize(block)
                if len(text) <= 900:
                    docs.append(Document(page_content=text, metadata={"type": "relation", "source_file": "rag_table_relationships.json"}))
                else:
                    for chunk in chunk_text(text, max_length=900):
                        docs.append(Document(page_content=chunk, metadata={"type": "relation", "source_file": "rag_table_relationships.json"}))
    except Exception as e:
        if DEBUG:
            print("⚠️ Erreur rag_table_relationships.json :", e)

    # table_domains.json
    try:
        with open("table_domains.json", encoding="utf-8") as f:
            data = json.load(f)
            for entry in data:
                domain_id = entry.get("id")
                content = entry.get("content", "")
                keywords = ", ".join(entry.get("keywords", []))
                tables = ", ".join(entry.get("tables", []))
                text = f"Domaine {domain_id} : {content}\nTables : {tables}\nMots-clés : {keywords}"
                for chunk in chunk_text(normalize(text), max_length=900):
                    docs.append(Document(page_content=chunk, metadata={"type": "domain", "id": domain_id, "source_file": "table_domains.json"}))
    except Exception as e:
        if DEBUG:
            print("⚠️ Erreur table_domains.json :", e)

    # query_patterns.json
    try:
        with open("query_patterns.json", encoding="utf-8") as f:
            data = json.load(f)
            for entry in data:
                pattern_id = entry.get("pattern_id")
                desc = entry.get("description", "")
                patterns = ", ".join(entry.get("patterns", "")) if entry.get("patterns") else ""
                joins = entry.get("essential_joins", "")
                resp_fields = entry.get("response_fields", "")
                text = f"Pattern {pattern_id} : {desc}\nExemples : {patterns}\nJoins essentiels : {joins}\nChamps réponse : {resp_fields}"
                for chunk in chunk_text(normalize(text), max_length=900):
                    docs.append(Document(page_content=chunk, metadata={"type": "query_pattern", "id": pattern_id, "source_file": "query_patterns.json"}))
    except Exception as e:
        if DEBUG:
            print("⚠️ Erreur query_patterns.json :", e)

    return docs

def build_rag_index():
    """Reconstruit l'index en réinitialisant la COLLECTION (pas le dossier)."""
    docs = load_documents()
    embeddings = _make_embeddings()

    vs = Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=RAG_DB_PATH,
        embedding_function=embeddings,
        collection_metadata={"hnsw:space": "cosine"},
    )

    # réinit collection
    try:
        vs.delete_collection()
        vs = Chroma(
            collection_name=COLLECTION_NAME,
            persist_directory=RAG_DB_PATH,
            embedding_function=embeddings,
            collection_metadata={"hnsw:space": "cosine"},
        )
    except Exception:
        try:
            vs._client.reset()
            vs = Chroma(
                collection_name=COLLECTION_NAME,
                persist_directory=RAG_DB_PATH,
                embedding_function=embeddings,
                collection_metadata={"hnsw:space": "cosine"},
            )
        except Exception as e2:
            if DEBUG:
                print(f"⚠️ Impossible de réinitialiser la collection proprement: {e2}")

    if docs:
        vs.add_documents(docs)
    vs.persist()

def auto_rebuild_if_needed():
    ctx_ts = _context_last_mtime()
    idx_ts = _index_last_mtime()
    if not os.path.exists(RAG_DB_PATH) or ctx_ts > idx_ts:
        build_rag_index()

# =========================
# Assistant SQL (générique)
# =========================
class SQLAssistant:
    def __init__(self):
        self.embeddings = _make_embeddings()
        self.vectordb = Chroma(
            collection_name=COLLECTION_NAME,
            persist_directory=RAG_DB_PATH,
            embedding_function=self.embeddings,
            collection_metadata={"hnsw:space": "cosine"},
        )

        self.llm_client = ChatOpenAI(
            model="gpt-4o",
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.2,
            max_tokens=2048
        )

        self.db = SQLDatabase.from_uri(
            f"mysql+mysqlconnector://{mysql_config['user']}:{mysql_config['password']}@{mysql_config['host']}:{mysql_config['port']}/{mysql_config['database']}",
            sample_rows_in_table_info=0
        )

        self.cache = self._load_cache()

    def _load_cache(self) -> dict:
        if os.path.exists(CACHE_FILE_PATH):
            with open(CACHE_FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_cache(self):
        with open(CACHE_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, indent=2, ensure_ascii=False)

    def _save_history(self, question, sql, response):
        history = []
        if os.path.exists(HISTORY_FILE_PATH):
            with open(HISTORY_FILE_PATH, "r", encoding="utf-8") as f:
                history = json.load(f)
        history.append({
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "sql": sql,
            "response": response
        })
        with open(HISTORY_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)

    # ---------- RAG ----------
    def retrieve_context(self, question: str, k=6) -> List[str]:
        query = f"query: {question}"
        results = self.vectordb.similarity_search_with_score(query, k)
        # on garde seulement les résultats suffisamment pertinents
        results = [(doc, score) for doc, score in results if score <= 1.5]
        return [doc.page_content for doc, _ in results]

    def ask_llm(self, prompt: str) -> str:
        response = self.llm_client.invoke(prompt)
        return response.content.strip()

    # ---------- SQL Exec ----------
    def execute_sql(self, sql: str) -> Tuple[Optional[List[dict]], Optional[str]]:
        """
        Exécution générique : SELECT -> rows (list[dict]), sinon -> rows_affected.
        Pas de branche métier.
        """
        cnx = None
        cur = None
        try:
            cnx = mysql.connector.connect(**mysql_config)
            cur = cnx.cursor(dictionary=True)
            cur.execute(sql)
            if cur.with_rows:  # SELECT
                rows = cur.fetchall()
                return rows, None
            else:  # INSERT/UPDATE/DELETE
                cnx.commit()
                return [{"rows_affected": cur.rowcount}], None
        except Exception as e:
            return None, str(e)
        finally:
            try:
                if cur:
                    cur.close()
            except Exception:
                pass
            try:
                if cnx:
                    cnx.close()
            except Exception:
                pass

    # ---------- NLG générique ----------
    def to_natural_language(self, question: str, rows: Optional[List[dict]], error: Optional[str]) -> str:
        """
        Conversion uniforme -> langage naturel FR.
        """
        if error:
            return f"❌ Erreur lors de l’exécution de la demande.\nDétail : {error}"

        count = len(rows) if rows else 0
        sample_rows = rows[:30] if rows else []
        cols = sorted(set(k for r in sample_rows for k in r.keys())) if sample_rows else []
        ground = {"row_count": count, "columns": cols}

        payload = json.dumps(sample_rows, ensure_ascii=False, default=str)
        ground_json = json.dumps(ground, ensure_ascii=False)

        nlg_prompt = f"""Tu es un assistant qui RÉPOND EN FRANÇAIS en langage naturel à partir de résultats SQL.
            Règles OBLIGATOIRES :
            - Respecte la vérité terrain suivante : {ground_json}
            - Si row_count > 0 : présente des éléments concrets (sans SQL/JSON). Si > 30 lignes : résume et donne au plus 10 exemples.
            - Si row_count = 0 : indique clairement qu'il n'y a pas de données.
            - Reste concis, clair, sans code ni balises.

            Question : {question}
            row_count : {count}
            Échantillon (≤ 30 lignes) :
            {payload}
            """
        try:
            out = self.llm_client.invoke(nlg_prompt).content.strip()
            if out:
                return out
        except Exception:
            pass

        # Fallback déterministe (toujours générique)
        if count == 0:
            return "Aucune donnée trouvée pour cette demande."
        lines = []
        # simple rendu clé:valeur générique, sans logique métier
        header_cols = cols
        for r in sample_rows[:10]:
            parts = [f"{k}: {r.get(k)}" for k in header_cols]
            lines.append("• " + "; ".join(parts))
        if count > 10:
            lines.append(f"… et {count - 10} autre(s) ligne(s).")
        return "\n".join(lines)

    # ---------- Pipeline principal ----------
    def ask(self, question: str) -> str:
        key = normalize(question)

        # Cache
        if key in self.cache:
            return self.cache[key]["response"]

        # Contexte RAG
        context_list = self.retrieve_context(question)
        context = "\n".join(context_list)

        # Affichage contexte
        if SHOW_CONTEXT_IN_CLI:
            ctx_to_print = context
            if MAX_CONTEXT_CHARS and len(ctx_to_print) > MAX_CONTEXT_CHARS:
                ctx_to_print = ctx_to_print[:MAX_CONTEXT_CHARS] + "\n… (contexte tronqué)"
            print("\n🧾 CONTEXTE FINAL UTILISÉ POUR LE PROMPT :\n" + (ctx_to_print or "(vide)"))

        # Prompt SQL (compact, générique)
        full_prompt = f"""Tu es un expert SQL (MySQL).
            Contexte utile (schéma/relations/patterns) :
            {context}

            ⚠️ Règle stricte pour la génération SQL :
                - Utiliser des backticks uniquement pour les noms de colonnes et tables.
                - Utiliser uniquement des quotes simples '...' pour les valeurs texte.
                - Ne jamais mettre de parenthèses ou de backticks dans les littéraux texte.
                - Toujours fermer correctement les quotes.

            ATTENTION !!:
            - N’utilise QUE les tables/colonnes/relations présentes dans le contexte (RAG). N’invente rien.
            - Jointures : uniquement celles explicites dans le contexte.
            - Noms arabes (ء-ي) → `NomAr`/`PrenomAr`, sinon `NomFr`/`PrenomFr` de la table `personne`. Si aucune donnée : essaie aussi avec le prénom et le nom inversés.
            - Alias DISTINCTS par table. Une SEULE requête SQL valide, sans commentaire ni explication.

            Si année scolaire mentionnée :
            - Si une table utilisée contient une FK d’année pointant vers `anneescolaire`.`id` (ex. `...`.`AnneeScolaire`/`IdAnneeSco`/`AnneeSco`), filtre l’année en cours avec :
            `table.FK_Annee IN (SELECT id FROM anneescolaire WHERE Actif = 1)` (remplace `table.FK_Annee` par la vraie colonne).
            - Sinon, JOIN `anneescolaire` via la FK d’année existante.
            - 'YYYY/YYYY+1' → `anneescolaire`.`AnneeScolaire` = 'YYYY/YYYY+1'
            - 'YYYY' → `anneescolaire`.`AnneeScolaire` LIKE 'YYYY%'
            - 'année en cours' → `anneescolaire`.`Actif` = 1
            - 'année précédente' → l'id immédiatement antérieur à celui où `Actif` = 1

            Question : {question}
            Requête SQL :
            """

        # Génération SQL
        sql_query_raw = self.ask_llm(full_prompt)
        sql_query = extract_sql(sql_query_raw) or clean_sql(sql_query_raw)
        sql_query = sanitize_sql_literals(sql_query)

        if not sql_query or not re.search(r"^\s*(SELECT|INSERT|UPDATE|DELETE)\b", sql_query, re.IGNORECASE):
            natural = "❌ Je n’ai pas réussi à générer une requête SQL valide pour cette demande."
            self.cache[key] = {"sql": None, "response": natural}
            self._save_cache()
            self._save_history(question, None, natural)
            return natural

        if SHOW_SQL_IN_CLI:
            print("\n🛠️ REQUÊTE SQL GÉNÉRÉE :\n" + sql_query)

        # Exécution SQL
        rows, error = self.execute_sql(sql_query)

        # NLG générique
        natural = self.to_natural_language(question, rows, error)

        # Cache & historique
        self.cache[key] = {"sql": sql_query, "response": natural}
        self._save_cache()
        self._save_history(question, sql_query, natural)

        return natural

# =========================
# Main
# =========================
def main():
    print("🧠 Initialisation de l’assistant SQL...")
    auto_rebuild_if_needed()
    assistant = SQLAssistant()
    print("✅ Assistant prêt. Posez votre question :")

    while True:
        q = input("❓ Question (ou 'exit') : ").strip()
        if q.lower() in ("exit", "quit"):
            print("👋 À bientôt !")
            break
        answer = assistant.ask(q)
        print("\n🗣️ RÉPONSE :")
        print(answer)
        print("-" * 60)

if __name__ == "__main__":
    main()
