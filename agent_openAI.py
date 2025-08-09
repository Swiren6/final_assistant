from langchain_community.utilities import SQLDatabase
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_community.vectorstores.utils import filter_complex_metadata
from dotenv import load_dotenv
import os
import mysql.connector
import json
import unicodedata
import time
from datetime import datetime
from typing import List
import re

load_dotenv()
print("\U0001F4C1 Fichiers présents :", os.listdir("."))

RAG_DB_PATH = "chroma_db"
CACHE_FILE_PATH = "question_cache.json"
HISTORY_FILE_PATH = "query_history.json"

mysql_config = {
    'host': os.getenv("MYSQL_HOST"),
    'port': int(os.getenv("MYSQL_PORT", "3306")),
    'user': os.getenv("MYSQL_USER"),
    'password': os.getenv("MYSQL_PASSWORD"),
    'database': os.getenv("MYSQL_DATABASE")
}

def clean_sql(sql: str) -> str:
    """Supprime les balises Markdown (```sql ... ```) autour d'une requête SQL."""
    return re.sub(r"```(?:sql)?\s*(.*?)\s*```", r"\1", sql, flags=re.DOTALL).strip()

def extract_sql(text: str) -> str | None:
    # Supprime tous les blocs ``` (même mal fermés)
    text = text.replace("```sql", "").replace("```", "").strip()

    # Essaie de détecter un SELECT/INSERT/etc. proprement
    match = re.search(r"\b(SELECT|INSERT|UPDATE|DELETE)\b.+", text, re.IGNORECASE | re.DOTALL)
    if match:
        # Nettoie les lignes vides et espaces
        sql = match.group(0)
        lines = [line.strip() for line in sql.splitlines() if line.strip()]
        return " ".join(lines)

    return None

def get_schema_description(db: SQLDatabase) -> str:
    return db.get_table_info()

try:
    conn = mysql.connector.connect(**mysql_config)
    print("✅ Connexion MySQL réussie.")
    conn.close()
except Exception as e:
    print(f"❌ ERREUR connexion MySQL : {e}")
    exit(1)

def normalize(text: str) -> str:
    # Conserve la casse (Pas de casefold ni lower)
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'[^\w\s\-@\.]', '', text)
    return text.strip()

def chunk_text(text: str, max_length: int = 300) -> List[str]:
    sentences = re.split(r'(?<=[.?!])\s+', text)
    chunks, current = [], ""
    for sentence in sentences:
        if len(current) + len(sentence) < max_length:
            current += sentence + " "
        else:
            chunks.append(current.strip())
            current = sentence + " "
    if current:
        chunks.append(current.strip())
    return chunks

def clean_metadata(metadata: dict) -> dict:
    cleaned = {}
    for k, v in metadata.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            cleaned[k] = v
        elif isinstance(v, list):
            cleaned[k] = ", ".join(map(str, v))  # transforme liste -> str
    return cleaned

def load_documents():
    docs = []

    # Chargement des chunks supplémentaires (auto_chunks.json ou autre)
    try:
        with open("chunks.json", encoding="utf-8") as f:
            for entry in json.load(f):
                docs.append(Document(
                    page_content=normalize(entry["page_content"]),
                    metadata=clean_metadata(entry.get("metadata", {}))
                ))
        print("✅ chunks.json chargé avec succès.")
    except Exception as e:
        print("⚠️ Erreur chunks.json :", e)

    # Chargement de schema_description.json
    try:
        with open("schema_description.json", encoding="utf-8") as f:
            data = json.load(f)
            for entry in data.get("tables", []):
                table = entry.get("name")

                # Colonnes
                for col in entry.get("columns", []):
                    col_name = col["name"]
                    col_type = col["type"]
                    col_desc = col["description"]

                    # Découper proprement les descriptions longues
                    chunks = chunk_text(col_desc, max_length=500)
                    for chunk in chunks:
                        docs.append(Document(
                            page_content=normalize(f"Table {table}  Colonne {col_name} {col_type}  {chunk}"),
                            metadata={
                                "type": "column_schema",
                                "table": table,
                                "column": col_name
                            }
                        ))

                # Valeurs explicites
                for val in entry.get("values", []):
                    lignes = [f"{k} = {v}" for k, v in val.items()]
                    chunk = f"Table `{table}` → Valeur possible : {', '.join(lignes)}"
                    docs.append(Document(
                        page_content=normalize(
                            f"Table `{table}`  Colonne `{col_name}` {col_type}  {chunk}"
                        ),
                        metadata={"type": "column_schema", "table": table, "column": col_name}
                        ))


    except Exception as e:
        print("⚠️ Erreur schema_description.json :", e)

    # Chargement des relations depuis rag_table_relationships.json
    try:
        with open("rag_table_relationships.json", encoding="utf-8") as f:
            data = json.load(f)
            for rel in data:
                relation = rel.get("relation", "")
                description = rel.get("description", "")
                block = f"{relation} — {description}".strip()

                text = normalize(block)

                # Si c’est court, un seul doc. Sinon découpe proprement.
                if len(text) <= 900:
                    docs.append(Document(page_content=text, metadata={"type": "relation"}))
                else:
                    for chunk in chunk_text(text, max_length=900):
                        docs.append(Document(page_content=chunk, metadata={"type": "relation"}))

    except Exception as e:
        print("⚠️ Erreur rag_table_relationships.json :", e)

    print(f"📄 {len(docs)} documents à indexer.")
    return docs


def build_rag_index():
    docs = load_documents()
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=os.getenv("OPENAI_API_KEY"))
    Chroma.from_documents(docs, embedding=embeddings, persist_directory=RAG_DB_PATH)
    print("✅ Index RAG reconstruit.")

def auto_rebuild_if_needed():
    source_files = ["schema_description.json","chunks.json","rag_table_relationships.json"]
    if not os.path.exists(RAG_DB_PATH):
        build_rag_index()
        return
    try:
        index_ts = os.path.getmtime(RAG_DB_PATH)
        latest_source = max(os.path.getmtime(f) for f in source_files if os.path.exists(f))
        if latest_source > index_ts:
            build_rag_index()
        else:
            print("\U0001F7E2 Index RAG déjà à jour.")
    except Exception as e:
        print("⚠️ Problème de reconstruction auto :", e)
        build_rag_index()

shared_embeddings = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=os.getenv("OPENAI_API_KEY"))
shared_vectordb = Chroma(persist_directory=RAG_DB_PATH, embedding_function=shared_embeddings,collection_metadata={"hnsw:space": "cosine"})

class SQLAssistant:
    def __init__(self):
        self.llm_client = ChatOpenAI(
            model="gpt-4o-mini",
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.1,
            max_tokens=2048
        )
        self.db = SQLDatabase.from_uri(
            f"mysql+mysqlconnector://{mysql_config['user']}:{mysql_config['password']}@{mysql_config['host']}:{mysql_config['port']}/{mysql_config['database']}",
            sample_rows_in_table_info=0
        )
        self.cache = self.load_cache()
        self.vectordb = shared_vectordb

    def retrieve_context(self, question: str, k=6) -> List[str]:
        query = f"query: {question}"
        results = self.vectordb.similarity_search_with_score(query, k)
        results = [(doc, score) for doc, score in results if score <= 1.5]  # augmente le seuil

        if not results:
            print("⚠️ Aucun chunk pertinent trouvé (score > 1.5)")
            return []
        
        """tables = [doc.metadata.get("table") for doc, _ in results if "table" in doc.metadata]
        if tables:
            from collections import Counter
            most_common_table = Counter(tables).most_common(1)[0][0]

            print(f"🔍 Table dominante détectée : {most_common_table}")

            # Filtrage : ne garde que les chunks de cette table
            results = [(doc, score) for doc, score in results if doc.metadata.get("table") == most_common_table]"""

        print("🔎 Résultats de la recherche RAG :")
        for i, (doc, score) in enumerate(results):
            print(f"[{i+1}] Score: {score:.4f}\n{doc.page_content}\n{'-' * 40}")
        return [doc.page_content for doc, _ in results]

    def ask_llm(self, prompt: str) -> str:
        response = self.llm_client.invoke(prompt)
        return response.content.strip()

    def load_cache(self) -> dict:
        if os.path.exists(CACHE_FILE_PATH):
            with open(CACHE_FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_cache(self):
        with open(CACHE_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, indent=2)

    def save_history(self, question, sql, response):
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

    def ask(self, question: str) -> str:
        normalized = normalize(question)
        if normalized in map(normalize, self.cache.keys()):
            print("✅ Réponse trouvée dans le cache.")
            return self.cache[question]["response"]

        context_list = self.retrieve_context(question)
        context = "\n".join(context_list)
        schema = get_schema_description(self.db)
        full_prompt = f"""Tu es un expert SQL.
        Voici du contexte utile extrait des documents (schéma, relations, etc.) :

        {context}

        !!!! Règles STRICTES :
        - Si un nom contient des caractères arabes (ء-ي), utilise `NomAr` et `PrenomAr`.
        - Sinon, utilise `NomFr` et `PrenomFr`.
        - Utilise uniquement les tables et colonnes présentes dans le contexte ci-dessus.
        - Si une table n’est pas dans cette liste, réponds : 'Données non disponibles'.
        - Entoure toujours les noms de tables et de colonnes avec des `backticks`.
        - Génère une requête SQL VALIDE (sans commentaire ni balise Markdown).
        - ⚠️ Si aucune donnée n’est trouvée, RÉESSAYE en inversant le prénom et le nom.
        - Quand la question concerne un contact (comment JOINDRE ou contacter une personne), retourne les colonnes `Tel1`, `Tel2`, `Tel3` et `Email` si elles sont disponibles.
        - Si ces colonnes existent dans plusieurs tables, privilégie la table `personne`. Si elle ne contient pas la personne, utilise `personnepreinscription`.
        - ❌ N’utilise jamais une colonne provenant d’une autre table que celle du `FROM`, même si elle semble pertinente (ex: `mailpere` ne va PAS dans `personne`).
        - Ne réponds jamais 'Données non disponibles' sans avoir essayé aussi l’inversion du prénom et du nom.
        - Ne jamais utiliser un alias déjà employé pour une autre table dans la même requête SQL.

        Question : {question}
        Requête SQL :
        """

        print("🧾 CONTEXTE FINAL UTILISÉ POUR LE PROMPT :")
        print(context)
        sql_query_raw = self.ask_llm(full_prompt)
        print("🧠 Réponse brute du LLM :\n" + sql_query_raw)
        sql_query = extract_sql(sql_query_raw)

        if sql_query:
            sql_query = clean_sql(sql_query)
            print("✅ Requête SQL extraite :\n" + sql_query)
        else:
            sql_query = clean_sql(sql_query_raw)
            print("❌ Aucune requête SQL valide détectée dans la réponse :\n" + sql_query_raw)
            return "❌ La réponse du modèle ne contient pas de requête SQL exécutable."
        
        try:
            result = self.db.run(sql_query)
            if not result:
                result = "ℹ️ Aucune donnée trouvée."
        except Exception as e:
            result = f"❌ Erreur SQL : {e}"

        self.cache[question] = {"sql": sql_query, "response": result}
        self.save_cache()
        self.save_history(question, sql_query, result)

        return result

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
        print(answer)
        print("-" * 60)

if __name__ == "__main__":
    main()
