from deepseek_openAI import load_documents

docs = load_documents()
unique_chunks = set(d.page_content for d in docs)
print(f"🧩 {len(docs)} documents totaux, {len(unique_chunks)} chunks uniques.")
