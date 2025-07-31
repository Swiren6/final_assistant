from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

EMBEDDING_MODEL = "intfloat/multilingual-e5-base"
RAG_DB_PATH = "chroma_db"

# Chargement de la base vectorielle
embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
vectordb = Chroma(persist_directory=RAG_DB_PATH, embedding_function=embeddings)

# Récupération des documents
retrieved_docs = vectordb.get()['documents']

print(f"🔢 Nombre total de chunks indexés : {len(retrieved_docs)}\n")
for i, doc in enumerate(retrieved_docs, 1):
    print(f"[{i}] {doc}\n{'-' * 60}")
