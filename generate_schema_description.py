import mysql.connector
import json
import os
from dotenv import load_dotenv

load_dotenv()

mysql_config = {
    'host': os.getenv("MYSQL_HOST"),
    'port': int(os.getenv("MYSQL_PORT", "3306")),
    'user': os.getenv("MYSQL_USER"),
    'password': os.getenv("MYSQL_PASSWORD"),
    'database': os.getenv("MYSQL_DATABASE")
}

def generate_schema_description():
    conn = mysql.connector.connect(**mysql_config)
    cursor = conn.cursor()

    cursor.execute("SHOW TABLES")
    tables = [row[0] for row in cursor.fetchall()]
    result = []

    for table in tables:
        cursor.execute(f"SHOW COLUMNS FROM {table}")
        columns = cursor.fetchall()
        col_names = [f"{col[0]} ({col[1]})" for col in columns]
        col_list = ", ".join(col_names)
        description = f"La table '{table}' contient les colonnes suivantes : {col_list}."
        result.append({
            "table": table,
            "description": description
        })

    with open("schema_description.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("✅ Fichier schema_description.json généré avec succès.")

if __name__ == "__main__":
    generate_schema_description()
