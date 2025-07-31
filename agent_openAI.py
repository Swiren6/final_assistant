from langchain_community.utilities import SQLDatabase
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
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
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

mysql_config = {
    'host': os.getenv("MYSQL_HOST"),
    'port': int(os.getenv("MYSQL_PORT", "3306")),
    'user': os.getenv("MYSQL_USER"),
    'password': os.getenv("MYSQL_PASSWORD"),
    'database': os.getenv("MYSQL_DATABASE")
}

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
    # Gardez les accents et caractères spéciaux importants
    text = unicodedata.normalize('NFKC', text.casefold())
    text = re.sub(r'[^\w\s\-@\.]', '', text)  # Conserve . @ -
    return text.strip()

def chunk_text(text: str, max_length: int = 500) -> List[str]:
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

def load_documents():
    docs = []

    # schema_description.json
    try:
        with open("schema_description.json", encoding="utf-8") as f:
            for entry in json.load(f):
                table = entry["table"]
                for col in entry.get("columns", []):
                    col_name = col["name"]
                    col_type = col["type"]
                    col_desc = col["description"]
                    chunk = f"Table `{table}` → Colonne `{col_name}` ({col_type}) : {col_desc}"
                    docs.append(Document(
                        page_content=normalize(chunk),
                        metadata={
                            "type": "column_schema",
                            "table": table,
                            "column": col_name
                        }
                    ))
    except Exception as e:
        print("⚠️ Erreur schema_description.json :", e)


    # etat_sql.json
    """try:
        with open("etat_sql.json", encoding="utf-8") as f:
            raw = json.load(f)

            # Si c’est une liste de dictionnaires [{ "question": "...", "sql": "..." }, ...]
            if isinstance(raw, list):
                for entry in raw:
                    question = entry.get("question", "")
                    sql_clean = entry.get("sql", "")
                    metadata = filter_complex_metadata({
                        "type": "etat_sql",
                        "sql": sql_clean
                    })
                    for chunk in chunk_text(question):
                        docs.append(Document(page_content=normalize(chunk), metadata=metadata))

            # Si c’est un dictionnaire { "question1": "sql1", "question2": "sql2" }
            elif isinstance(raw, dict):
                for question, sql in raw.items():
                    sql_clean = sql[0] if isinstance(sql, list) else sql
                    metadata = filter_complex_metadata({
                        "type": "etat_sql",
                        "sql": sql_clean
                    })
                    for chunk in chunk_text(question):
                        docs.append(Document(page_content=normalize(chunk), metadata=metadata))

            else:
                print("⚠️ Format inattendu dans etat_sql.json")
    except Exception as e:
        print("⚠️ Erreur etat_sql.json :", e)"""


    # domain_to_tables_mapping.json
    try:
        with open("domain_to_tables_mapping.json", encoding="utf-8") as f:
            for entry in json.load(f):
                if "domaine" in entry and "description" in entry:
                    metadata = filter_complex_metadata({
                        "type": "domain_description",
                        "domain": entry["domaine"]
                    })
                    for chunk in chunk_text(entry["description"]):
                        docs.append(Document(page_content=normalize(chunk), metadata=metadata))
    except Exception as e:
        print("⚠️ Erreur domain_to_tables_mapping.json :", e)

    # rag_table_relationships.json
    try:
        with open("rag_table_relationships.json", encoding="utf-8") as f:
            for rel in json.load(f):
                for chunk in chunk_text(rel):
                    docs.append(Document(page_content=normalize(chunk), metadata={"type": "relation"}))
    except Exception as e:
        print("⚠️ Erreur rag_table_relationships.json :", e)

    # column_values_explained.json
    try:
        with open("column_values_explained.json", encoding="utf-8") as f:
            column_data = json.load(f)

            if isinstance(column_data, dict):
                items = column_data.items()
            elif isinstance(column_data, list):
                # transformer la liste en paires (clé, entrée)
                items = [(entry["column"], entry) for entry in column_data if "column" in entry]
            else:
                raise ValueError("Format inattendu dans column_values_explained.json")

            for column, entry in items:
                base_desc = entry.get("description", "")
                values_desc = entry.get("values", {})
                full_text = base_desc + " " + " ".join(f"{k}: {v}" for k, v in values_desc.items())
                for chunk in chunk_text(full_text):
                    docs.append(Document(
                        page_content=normalize(chunk),
                        metadata={"type": "column_values", "column": column}
                    ))

    except Exception as e:
        print("⚠️ Erreur column_values_explained.json :", e)

        # reglementeleve_chunks.json
    try:
        with open("reglementeleve_chunks.json", encoding="utf-8") as f:
            for entry in json.load(f):
                chunk = entry.get("text", "")
                if chunk:
                    docs.append(Document(
                        page_content=normalize(chunk),
                        metadata={"type": "table_row_example", "table": "Reglementeleve"}
                    ))
    except Exception as e:
        print("⚠️ Erreur reglementeleve_chunks.json :", e)
 

    print(f"📄 {len(docs)} documents à indexer.")
    return docs


def build_rag_index():
    docs = load_documents()
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    Chroma.from_documents(docs, embedding=embeddings, persist_directory=RAG_DB_PATH)
    print("✅ Index RAG reconstruit.")

def auto_rebuild_if_needed():
    source_files = ["schema_description.json","reglementeleve_chunks.json", "domain_to_tables_mapping.json", "rag_table_relationships.json","column_values_explained.json"]
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

shared_embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
shared_vectordb = Chroma(persist_directory=RAG_DB_PATH, embedding_function=shared_embeddings)

class SQLAssistant:
    def __init__(self):
        self.llm_client = ChatOpenAI(
            model="gpt-3.5-turbo",
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

    def retrieve_context(self, question: str, k=10) -> List[str]:
        results = self.vectordb.similarity_search_with_score("query: " + question, k)
        results = [(doc, score) for doc, score in results if score >= 0.2]  # augmente le seuil

        if not results:
            print("⚠️ Aucun chunk pertinent trouvé (score < 0.4)")
            return []

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
        Voici du contexte utile extrait des documents (schéma, relations, colonnes, exemples, etc) :

        {context}

        Règles STRICTES :
        - Utilise uniquement les tables/colonnes présentes dans le contexte ci-dessus
        - Si une table n’est pas dans cette liste, réponds : 'Données non disponibles'
        - Entoure toujours les noms de tables/colonnes avec `backticks`
        - Donne une requête SQL VALIDE (sans commentaires)

        Question : {question}
        Requête SQL :"""

        print("🧾 CONTEXTE FINAL UTILISÉ POUR LE PROMPT :")
        print(context)
        sql_query_raw = self.ask_llm(full_prompt)
        print("🧠 Réponse brute du LLM :\n" + sql_query_raw)
        match = re.search(r"(SELECT|INSERT|UPDATE|DELETE).*?;", sql_query_raw, re.IGNORECASE | re.DOTALL)

        if match:
            sql_query = match.group(0).strip()
            print("✅ Requête SQL extraite :\n" + sql_query)
        else:
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
