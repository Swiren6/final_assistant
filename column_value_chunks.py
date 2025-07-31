from langchain_core.documents import Document

def generate_column_value_chunks(json_data):
    docs = []
    for column, data in json_data.items():
        values = ", ".join(f"{k} = {v}" for k, v in data.get("values", {}).items())
        page = f"Colonne : {column}. Description : {data['description']}. Valeurs possibles : {values}."
        docs.append(Document(page_content=page, metadata={"type": "column_values", "column": column}))
    return docs
