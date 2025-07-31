import mysql.connector
import json
import os
from dotenv import load_dotenv

# ========== Chargement des variables d’environnement ==========
load_dotenv()

config = {
    "host": os.getenv("MYSQL_HOST"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE")
}

# ========== Connexion MySQL ==========
try:
    conn = mysql.connector.connect(**config)
    cursor = conn.cursor()
    print("✅ Connexion MySQL réussie.")
except Exception as e:
    print("❌ Erreur de connexion :", e)
    exit(1)

# ========== Fonction d'extraction ==========
chunks = []

def describe_table(table_name):
    cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
    columns = cursor.fetchall()

    # ➤ Description globale de la table
    col_names = [col[0] for col in columns]
    desc = f"La table `{table_name}` contient les colonnes : {', '.join(col_names)}."
    chunks.append({
        "page_content": desc,
        "metadata": {
            "type": "table_description",
            "table": table_name
        }
    })

    # ➤ Description par colonne
    for col in columns:
        col_name = col[0]
        col_type = col[1]
        nullable = "peut être nulle" if col[2] == "YES" else "est obligatoire"
        line = f"La colonne `{col_name}` ({col_type}) de la table `{table_name}` {nullable}."
        chunks.append({
            "page_content": line,
            "metadata": {
                "type": "column",
                "table": table_name,
                "column": col_name
            }
        })

# ========== Récupération de toutes les tables ==========
cursor.execute("SHOW TABLES")
tables = [row[0] for row in cursor.fetchall()]
print(f"📦 {len(tables)} tables trouvées.")

for table in tables:
    describe_table(table)

# ========== Sauvegarde dans un fichier JSON ==========
with open("auto_chunks.json", "w", encoding="utf-8") as f:
    json.dump(chunks, f, indent=2, ensure_ascii=False)

print(f"✅ {len(chunks)} chunks générés et enregistrés dans auto_chunks.json.")

# ========== Fermeture ==========
cursor.close()
conn.close()
