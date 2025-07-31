import os
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_community.chat_models import ChatOpenAI
import mysql.connector
import re

load_dotenv()

# Initialiser le modèle
llm = ChatOpenAI(
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    model="gpt-3.5-turbo",
    temperature=0
)

# Connexion à la base de données
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
        use_pure=True
    )

# Fonction pour exécuter une requête SQL
def run_sql(query):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result
    except Exception as e:
        return f"Erreur SQL : {e}"

# Prompt complet pour les parents (structure réelle depuis le dump)
parent_prompt_template = PromptTemplate(
    input_variables=["question"],
    template="""
Tu es un assistant IA scolaire spécialisé dans l'aide aux parents.
Tu as accès aux tables suivantes dans la base de données scolaire :

- eleve(id, DateNaissance, LieuNaissance, IdPersonne, Solde, photo, IdEdusrv, AutreLieuNaissance)
- inscriptioneleve(id, Eleve, Classe, Date, AnneeScolaire, Personne, Modalite, TTC_Scolaire, Restant_Scolaire, Solde, TypeInscri, PreinscriptionId, Annuler, DateAnnulation, groupe)
- paiement(id, MotifPaiement, date, Tranche, TotalHt, TauxRemise, TotalRemise, NetHt, TauxTVA, TotalTVA, TotalTTC, Inscription, MontantRestant, Annuler, TotalNet)
- parent(id, Personne, Profession, Etablissement, AddresseEtr, PaysEtr, VilleEtr, CodePostalEtr, ResideEtr, Etranger, codepostal)
- parenteleve(id, Parent, Eleve, Type)
- personne(id, NomFr, PrenomFr, NomAr, PrenomAr, Cin, CinLiv, AdresseFr, AdresseAr, Tel1, Tel2, Tel3, Email, Login, Pwd, Nationalite, Localite, Civilite, codepostal, SoldeCantineParJour, type, natinaliteAutre, localiteAutre)
- edusrv(id, nom, prenom, type, fonction, id_personne, id_matiere, date_debut, date_fin, is_active)
- classe(id, libelle, annee, niveau, groupe, enseignant, cycle, section, capacite)
- emploi_temps(id, id_classe, id_jour, heure_debut, heure_fin, id_matiere)
- matiere(id, nom, coefficient, niveau, cycle)
- absence(id, eleve_id, date, type, justifiee, motif)
- retard(id, eleve_id, date, heure, justifiee, motif)
- sanction(id, eleve_id, date, description, type, niveau)
- note(id, eleve_id, id_matiere, note, periode, id_classe)
- devoir(id, classe_id, matiere_id, date_devoir, description)
- cantine(id, eleve_id, date, repas, solde_jour, present)

Pour la question suivante, génère uniquement la requête SQL correspondante, adaptée aux parents, sans rien ajouter d'autre :

Question : {question}

Attention !!!!: 
Attention !!!!:
- Si l'ID de l'élève n'est pas donné, vérifie si son prénom et nom sont donnés. 
-Une fois obtenus, récupère son ID en joignant 'eleve' et 'personne' via 'eleve.IdPersonne = personne.id',
  puis génère la requête SQL nécessaire à partir de son nom et prénom (NomFr, PrenomFr).

"""
)

# Prompt fictif pour administration (tu peux l’adapter aussi à la structure réelle)
admin_prompt_template = PromptTemplate(
    input_variables=["question"],
    template="""
Tu es un assistant IA scolaire spécialisé dans l'aide à l'administration.
Tu as accès aux tables suivantes :
- eleve(id, DateNaissance, LieuNaissance, IdPersonne, Solde, photo, IdEdusrv, AutreLieuNaissance)
- inscriptioneleve(id, Eleve, Classe, Date, AnneeScolaire, Personne, Modalite, TTC_Scolaire, Restant_Scolaire, Solde, TypeInscri, PreinscriptionId, Annuler, DateAnnulation, groupe)
- paiement(id, MotifPaiement, date, Tranche, TotalHt, TauxRemise, TotalRemise, NetHt, TauxTVA, TotalTVA, TotalTTC, Inscription, MontantRestant, Annuler, TotalNet)
- classe(id, libelle, annee, niveau, groupe, enseignant, cycle, section, capacite)
- note(id, eleve_id, id_matiere, note, periode, id_classe)
- absence(id, eleve_id, date, type, justifiee, motif)
- sanction(id, eleve_id, date, description, type, niveau)
- personne(...)
- edusrv(...)
- matiere(...)
- emploi_temps(...)
(complète avec les autres tables si besoin)

Pour la question suivante, génère uniquement la requête SQL correspondante, adaptée à l'administration, sans rien ajouter d'autre :

Question : {question}
"""
)

# Choix du bon prompt
def get_prompt_template(role: str):
    role = role.lower()
    if role == "parent":
        return parent_prompt_template
    elif role == "administration":
        return admin_prompt_template
    else:
        raise ValueError("Rôle inconnu. Choisir 'parent' ou 'administration'.")

# Générer la requête SQL
def generate_sql(question: str, role: str):
    prompt = get_prompt_template(role)
    chain: RunnableSequence = prompt | llm
    response = chain.invoke({"question": question})
    return response.content.strip()


def nom_prenom_dans_question(question: str) -> bool:
    question = question.lower()

    # Cas 1 : le parent donne explicitement "nom = ..." ou "prénom = ..."
    if re.search(r"\b(nom|prénom)\s*[:=]\s*\w+", question):
        return True

    # Cas 2 : il dit "appelé X", "appelée Y"
    if re.search(r"\bappelé[e]?\s+\w+(?:\s+\w+)?", question):
        return True

    # Cas 3 : il dit "mon fils Ali", "ma fille Lina"
    if re.search(r"\b(mon fils|ma fille)\s+\w+(?:\s+\w+)?", question):
        return True

    # Cas 4 : "concernant Mehdi", "pour Lina", "à propos de Rayan"
    if re.search(r"\b(concernant|pour|à propos de)\s+\w+(?:\s+\w+)?", question):
        return True

    # Cas 5 : "j’ai inscrit Sarah", "inscription de Walid"
    if re.search(r"(inscrit|inscription).*?\b\w+(?:\s+\w+)?", question):
        return True

    return False

def demande_nom_prenom():
    nom = input("🧒 Entrez le nom de votre enfant : ").strip()
    prenom = input("🧒 Entrez le prénom de votre enfant : ").strip()
    return nom, prenom


# Main
def main():
    print("🎓 Bienvenue à l'Agent IA Scolaire !")
    role = input("Quel est votre rôle ? (parent / administration) : ").strip().lower()

    if role not in ["parent", "administration"]:
        print("❌ Rôle invalide. Veuillez choisir 'parent' ou 'administration'.")
        return

    while True:
        question = input("\n❓ Posez votre question (ou tapez 'quit' pour quitter) : ").strip()
        if question.lower() == "quit":
            print("👋 Merci d'avoir utilisé l'Agent IA Scolaire. À bientôt !")
            break

        if role == "parent" and not nom_prenom_dans_question(question):
            print("👀 Vous n'avez pas précisé le prénom et nom de votre enfant.")
            nom, prenom = demande_nom_prenom()
            question += f" L'enfant s'appelle {prenom} {nom}."

        print("\n🧠 Génération de la requête SQL...")
        sql_query = generate_sql(question, role)

        print("\n✅ Requête SQL générée :")
        print(sql_query)

        print("\n🔎 Exécution de la requête en base de données...")
        result = run_sql(sql_query)

        print("\n📊 Résultat :")
        if isinstance(result, str):
            print(result)  # Affiche erreur SQL
        elif not result:
            print("Aucun résultat trouvé.")
        else:
            for row in result:
                print(row)
