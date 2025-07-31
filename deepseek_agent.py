# ======================== Chargement et setup =============================
from langchain_community.utilities import SQLDatabase
from langchain.prompts import PromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_community.vectorstores.utils import filter_complex_metadata
from dotenv import load_dotenv
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import os
import mysql.connector
import json
import unicodedata
import time
from datetime import datetime
from typing import List
import re

load_dotenv()
print("📁 Fichiers présents :", os.listdir("."))

# ========================= Configuration générale =========================
RAG_DB_PATH = "chroma_db"
CACHE_FILE_PATH = "question_cache.json"
HISTORY_FILE_PATH = "query_history.json"
EMBEDDING_MODEL = "intfloat/multilingual-e5-base"
DEEPSEEK_MODEL_PATH = "./models/deepseek-coder-7b-instruct-v1.5"

mysql_config = {
    'host': os.getenv("MYSQL_HOST"),
    'port': int(os.getenv("MYSQL_PORT", "3306")),
    'user': os.getenv("MYSQL_USER"),
    'password': os.getenv("MYSQL_PASSWORD"),
    'database': os.getenv("MYSQL_DATABASE")
}

def get_schema_description(db: SQLDatabase) -> str:
    return db.get_table_info()

# Test de connexion
try:
    conn = mysql.connector.connect(**mysql_config)
    print("✅ Connexion MySQL réussie.")
    conn.close()
except Exception as e:
    print(f"❌ ERREUR connexion MySQL : {e}")
    exit(1)

# ========================= Données RAG à indexer ==========================
def load_documents():
    docs = []
    
    filenames = [
        ("schema_description.json", "table_schema", lambda e: e["description"], lambda e: {"table": e["table"]}),
        """("etat_sql.json", "etat_sql", lambda q_sql: q_sql[0], lambda q_sql: {"sql": q_sql[1]}),"""
        ("domain_to_tables_mapping.json", "domain_description", lambda e: e["description"], lambda e: {"domain": e["domaine"]}),
        ("rag_table_relationships.json", "relation", lambda r: r, lambda r: {}),
        ("column_values_explained.json", "column_values", lambda e: e["description"], lambda e: {"column": e["column"]})
    ]

    for fname, dtype, content_fn, meta_fn in filenames:
        try:
            with open(fname, encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, dict):
                    for q, sql in content.items():
                        page = content_fn((q, sql))
                        meta = filter_complex_metadata({"type": dtype, **meta_fn((q, sql))})
                        docs.append(Document(page_content=page, metadata=meta))
                else:
                    for e in content:
                        page = content_fn(e)
                        meta = filter_complex_metadata({"type": dtype, **meta_fn(e)})
                        docs.append(Document(page_content=page, metadata=meta))
        except Exception as e:
            print(f"⚠️ Erreur {fname} :", e)

    print(f"📄 {len(docs)} documents à indexer.")
    return docs

def build_rag_index():
    docs = load_documents()
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    Chroma.from_documents(docs, embedding=embeddings, persist_directory=RAG_DB_PATH)
    print("✅ Index RAG reconstruit.")

def auto_rebuild_if_needed():
    source_files = ["etat_sql.json","schema_description.json", "domain_to_tables_mapping.json", "rag_table_relationships.json","column_values_explained.json"]
    if not os.path.exists(RAG_DB_PATH):
        build_rag_index()
        return

    try:
        index_ts = os.path.getmtime(RAG_DB_PATH)
        latest_source = max(os.path.getmtime(f) for f in source_files if os.path.exists(f))
        if latest_source > index_ts:
            build_rag_index()
        else:
            print("🟢 Index RAG déjà à jour.")
    except Exception as e:
        print("⚠️ Problème de reconstruction auto :", e)
        build_rag_index()

# ========================= Utilitaires de texte ===========================
def normalize(text: str) -> str:
    text = unicodedata.normalize('NFD', text.lower())
    return ''.join(c for c in text if unicodedata.category(c) != 'Mn' and (c.isalnum() or c.isspace()))

# ========================= Assistant SQL complet ==========================
shared_embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
shared_vectordb = Chroma(persist_directory=RAG_DB_PATH, embedding_function=shared_embeddings)

class LocalDeepSeekLLM:
    def __init__(self, model_path: str):
        print("🚀 Chargement du modèle DeepSeek...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(model_path, trust_remote_code=True)
        self.pipe = pipeline("text-generation", model=self.model, tokenizer=self.tokenizer, max_new_tokens=64, temperature=0.7)

    def ask(self, prompt: str) -> str:
        print("🔍 Génération en cours...")
        output = self.pipe(prompt)[0]["generated_text"]
        print("✅ Génération terminée.")
        return output.strip()

class SQLAssistant:
    def __init__(self):
        self.llm_client = LocalDeepSeekLLM(model_path=DEEPSEEK_MODEL_PATH)
        self.db = SQLDatabase.from_uri(
            f"mysql+mysqlconnector://{mysql_config['user']}:{mysql_config['password']}@{mysql_config['host']}:{mysql_config['port']}/{mysql_config['database']}",
            sample_rows_in_table_info=0
        )
        self.cache = self.load_cache()
        self.vectordb = shared_vectordb

    def retrieve_context(self, question: str, k=3) -> List[str]:
        docs = self.vectordb.similarity_search(question, k=k)
        return [doc.page_content for doc in docs]

    def ask_llm(self, prompt: str) -> str:
        return self.llm_client.ask(prompt)

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

        context = self.retrieve_context(question)
        schema = get_schema_description(self.db)
        full_prompt = f"""Tu es un assistant SQL. Tu dois répondre uniquement avec une requête SQL correcte.
        ⚠️ Utilise uniquement les noms de colonnes et tables présents dans le CONTEXTE ci-dessous.
        ❌ Ne crée jamais de table ou colonne non mentionnée.
        ❌ Ne suppose rien.

        🔍 Question :
        {question}

        📚 CONTEXTE :
        {context}

        ==> Donne UNIQUEMENT la requête SQL :

        """

        sql_query_raw = self.ask_llm(full_prompt).strip()
        print("🧠 Réponse brute du LLM :")
        print(sql_query_raw)

        match = re.search(r"(SELECT|INSERT|UPDATE|DELETE).*?;", sql_query_raw, re.IGNORECASE | re.DOTALL)

        if match:
            sql_query = match.group(0).strip()
            print("✅ Requête SQL extraite :")
            print(sql_query)
        else:
            print("❌ Aucune requête SQL valide détectée dans la réponse :")
            print(sql_query_raw)
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

# ============================== Exécution ================================
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
