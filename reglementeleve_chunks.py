import mysql.connector
import json
from datetime import datetime

# Connexion à ta base MySQL
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Mardoud190767!",
    database="bd_eduise"
)
cursor = conn.cursor(dictionary=True)

# Dictionnaire des modes de règlement
modereglement_map = {
    1: "espèces",
    2: "chèque",
}

# Récupération des lignes
cursor.execute("SELECT * FROM reglementeleve LIMIT 100")  # Limite pour le test
rows = cursor.fetchall()

chunks = []
for row in rows:
    id_inscription = row["IdInscription"]
    montant = row["Montant"]
    date = datetime.strptime(str(row["Date"]), "%Y-%m-%d %H:%M:%S").strftime("%d %B %Y")
    mode_id = row["ModeReglement"]
    mode_txt = modereglement_map.get(mode_id, "inconnu")
    numcheque = row.get("numcheque")

    phrase = f"L'élève avec l'inscription ID {id_inscription} a payé {montant:.2f} MAD"
    if mode_txt == "chèque" and numcheque:
        phrase += f" par chèque (numéro de chèque : {numcheque})"
    else:
        phrase += f" en {mode_txt}"
    phrase += f" le {date}."

    chunks.append({
        "content": phrase,
        "metadata": {
            "table": "reglementeleve",
            "modereglement": mode_txt,
            "type": "paiement"
        }
    })

# Écriture dans un fichier
with open("reglementeleve_chunks.json", "w", encoding="utf-8") as f:
    json.dump(chunks, f, ensure_ascii=False, indent=2)

cursor.close()
conn.close()
