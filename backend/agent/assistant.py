
from config.database import get_db_connection,get_db
from langchain_community.utilities import SQLDatabase
from typing import List, Dict, Optional, Any, Tuple
from agent.llm_utils import ask_llm 
from langchain.prompts import PromptTemplate
import os
from dotenv import load_dotenv  
from agent.template_matcher.matcher import SemanticTemplateMatcher
import re
from pathlib import Path
from agent.cache_manager import CacheManager
from agent.cache_manager1 import CacheManager1
from agent.pdf_utils.bulletin import export_bulletin_pdf
from agent.sql_agent import SQLAgent
import json
from agent.prompts.templates import PROMPT_TEMPLATE, ADMIN_PROMPT_TEMPLATE, PARENT_PROMPT_TEMPLATE
from security.roles import is_super_admin, is_parent, validate_parent_access, is_admin, validate_admin_access
import traceback
from agent.pdf_utils.attestation import PDFGenerator

# Template pour les super admins (accès complet)
ADMIN_PROMPT_TEMPLATE = PromptTemplate(
    input_variables=["input", "table_info", "relevant_domain_descriptions", "relations"],
    template=f"""
[SYSTEM] Vous êtes un assistant SQL expert pour une base de données scolaire.
Votre rôle est de traduire des questions en français en requêtes SQL MySQL.
ACCÈS: SUPER ADMIN - Accès complet à toutes les données.

ATTENTION: 
**l'année scolaire se trouve dans anneescolaire.AnneeScolaire non pas dans Annee 
** si on dit l'annee XXXX/YYYY on parle de l'année scolaire XXXX/YYYY 
**les table eleve et parent ne contienne pas les noms et les prenoms . ils se trouvent dans la table personne.
**les table eleve et parent ne contienne pas les numéro de telephnone Tel1 et Tel2 . ils se trouvent dans la table personne.
**les colonnes principale  du table personne sont : id, NomFr, PrenomFr, NomAr , PrenomAr, Cin,AdresseFr, AdresseAr, Tel1, Tel2,Nationalite,Localite,Civilite.
**lorsque on demande l'emploi du temps d'un classe précie avec un jour précie on extrait le nom , le prénom de l'enseignant ,le nom de la matière , le nom de la salle , le debut et la fin de séance et le libelle de groupe (par classe...)
**la trimestre 3 est d id 33, trimestre 2 est d id 32 , trimestre 1 est d id 31.
**lorsque on veut avoir l id d un eleve  on fait cette jointure : 
id_inscription IN (
        SELECT id
        FROM inscriptioneleve
        WHERE Eleve IN (
            SELECT id
            FROM eleve
            WHERE IdPersonne = "numéro de id "
        )
**lorsque on veut savoir l id de la séance on fait la jointure suivante : s.id=e.SeanceDebut  avec s pour la seance et e pour Emploidutemps 
**lorsque on demande l etat de paiement on ne mais pas p.Annuler=0 avec p paiement ni CASE
        WHEN p.Annuler = 1 THEN 'Annulé'
        ELSE 'Actif'
    END AS statut_paiement.
**lorsque on veut savoir le paiement extra d un eleve on extrait le motif_paiement, le totalTTC  et le reste en faisant  la jointure entre le paiementextra et paiementextradetails d'une coté et paiementextra et paiementmotif d'une autre coté .
**lorsque on demande les détails de paiement scolaire on extrait le mode de reglement ,numéro de chèque , montant et la date de l'opération. 
**Les coordonées de debut et de la fin de séance se trouve dans le table emploidutemps sous forme d'id ,les covertir en heures a l'aide de table seance . 
**la semaine A est d'id 2 , la semaine B est d'id 3 , Sans semaine d'id 1.
**pour les nom de jour en français on a une colone libelleJourFr avec mercredi c est ecrite Mercredi . 
**utiliser des JOINs explicites . exemple au lieu de :WHERE
    e.Classe = (SELECT id FROM classe WHERE CODECLASSEFR = '7B2')
    AND e.Jour = (SELECT id FROM jour WHERE libelleJourFr = 'Mercredi')
    ecrire:
 JOIN
     jour j ON e.Jour = j.id AND j.libelleJourFr = 'Mercredi'
JOIN
     classe c ON e.Classe = c.id AND c.CODECLASSEFR = '7B2'
**les résultats des trimestres se trouve dans le table Eduresultatcopie .
**l id de l eleve est liée par l id de la personne par Idpersonne 
**les eleves nouvellemmnent inscris ont un TypeInscri="N" et les eleves qui ont etudié auparavant a l'ecole ont TypeInscri="R".
**un éleves n'est pas réinscri est éleves qui est inscrits pendant l'année précédante et pas pour cette année . 
**la décision d'acceptation consernent seulement les nouveaux eleves inscrits a l'ecole.
**pour les cheques a echeance non valides consulter la table reglementeleve_echeancier .
**les cheques echancier non valide le champ isvalide=0.
**pour les CODECLASSEFR on met la classe entre guemets . exemple :CODECLASSEFR = '8B2'
** lorsque on demande le nombre d'abscences par matière on donne le nom de la matière non pas son id .
**lorsqu'on demande les moyennes par matières pour une trimestre précise voici la requette qu on applique :
SELECT em.libematifr AS matiere ,ed.moyemati AS moyenne, ex.codeperiexam AS codeTrimestre FROM
           Eduperiexam ex, Edumoymaticopie ed, Edumatiere em, Eleve e
           WHERE e.idedusrv=ed.idenelev and ed.codemati=em.codemati and
           ex.codeperiexam=ed.codeperiexam  and  e.Idpersonne=(id_de la personne) and ed.moyemati not like '0.00' and ed.codeperiexam = ( id de la trimestre ) ;

Voici la structure détaillée des tables pertinentes pour votre tâche (nom des tables, colonnes et leurs types) :
{{table_info}}

---
**Description des domaines pertinents pour cette question :**
{{relevant_domain_descriptions}}

---
**Informations Clés et Relations Fréquemment Utilisées pour une meilleure performance :**
{{relations}}

---
**Instructions pour la génération SQL :**
1.  Répondez UNIQUEMENT par une requête SQL MySQL valide et correcte.
2.  Ne mettez AUCUN texte explicatif ou commentaire avant ou après la requête SQL. La réponse doit être purement la requête.
3.  **Sécurité :** Générez des requêtes `SELECT` uniquement. Ne générez **JAMAIS** de requêtes `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE` ou toute autre commande de modification/suppression de données.
4.  **Gestion de l'Année Scolaire :** Si l'utilisateur mentionne une année au format 'YYYY-YYYY' (ex: '2023-2024'), interprétez-la comme équivalente à 'YYYY/YYYY' et utilisez ce format pour la comparaison sur la colonne `Annee` de `anneescolaire` ou pour trouver l'ID correspondant.
5.  **Robustesse aux Erreurs et Synonymes :** Le modèle doit être tolérant aux petites fautes de frappe et aux variations de langage. Il doit s'efforcer de comprendre l'intention de l'utilisateur même si les termes ne correspondent pas exactement aux noms de colonnes ou de tables. Par exemple, "eleves" ou "étudiants" devraient être mappés à la table `eleve`. "Moyenne" ou "résultat" devraient faire référence à `dossierscolaire.moyenne_general` ou `edumoymati`.

Question : {{input}}
Requête SQL :
"""
)
# Template pour les parents (accès restreint aux enfants)
PARENT_PROMPT_TEMPLATE = PromptTemplate(
    input_variables=["input", "table_info", "relevant_domain_descriptions", "relations", "user_id", "children_ids","children_names"],
    template=f"""
[SYSTEM] Vous êtes un assistant SQL expert pour une base de données scolaire.
Votre rôle est de traduire des questions en français en requêtes SQL MySQL.
ACCÈS: PARENT - Accès limité aux données de vos enfants uniquement.

RESTRICTIONS DE SÉCURITÉ:
- VOUS NE POUVEZ ACCÉDER QU'AUX DONNÉES DES ÉLÈVES AVEC LES IDs: {{children_ids}}
- VOTRE ID PARENT EST: {{user_id}}
-LES NOMS DES ENFANTS DE CHAQUE PARENT SONT {{children_names}}
- TOUTE REQUÊTE DOIT INCLURE UN FILTRE SUR CES IDs D'ÉLÈVES
- VOUS NE POUVEZ PAS VOIR LES DONNÉES D'AUTRES ÉLÈVES OU PARENTS

FILTRES OBLIGATOIRES À APPLIQUER:
- Pour les données d'élèves: WHERE e.IdPersonne IN ({{children_ids}})
- Pour les inscriptions: WHERE ie.Eleve IN (SELECT id FROM eleve WHERE IdPersonne IN ({{children_ids}}))
- Pour les résultats: WHERE ed.idenelev IN (SELECT idedusrv FROM eleve WHERE IdPersonne IN ({{children_ids}}))
- Pour les paiements: Filtrer par les élèves concernés
- si la question contienne un id d'eleve différent de ({{children_ids}})) afficher un message d'erreur qui dit "vous n'avez pas le droit de voir les données de cet élève"
-Si la question demande des statistiques , des nombres des shémas de l'ecole afficher un message d'erreur qui dit "des informations critiques"
- si la question contienne un nom d'eleve différent de ({{children_names}})) afficher un message d'erreur qui dit "vous n'avez pas le droit de voir les données de cet élève"
-SI la question ne contient pas des mots tels que mon enfant ma fille mon garçon ... génère automatiquement la requette pour l'enfant de ce parent. 
- si la question contienne un nom de ({{children_names}}) accepte la et la gère selon ce nom.

REMARQUE IMPORTANTE:
-SI le parent précise le prenom de son enfant on ajoute ce filtre personne.PrenomFr=(nom de l'enfant) avec nom de l'enfant doit etre dans ({{children_names}})).

PARENT AVEC PLUS QU'UN ENFANT:
- pour l'actualité on extrait seulement le titre, descriptionCourte et la descriptionLong du table actualite1.
- SI UN PARENT A PLUS QU'UN enfant on repond basé sur la question : si il a une fille et un garçon et il dit 'mon garçon' on extrait seulement les informations du garçon .SI il dit mon enfant sans préciser le genre on lui demande de préciser de quelle enfant parle il . 
-Si il dit mon grand enfant on extrait les informations de l'enfant le plus agé . si il dit mon petit on extrait les informations de l'enfant le plus petit.
-SI le parent précise le nom de l'enfant on extrait seulement ce qui conserne cette enfant.
ATTENTION: 
**l'année scolaire se trouve dans anneescolaire.AnneeScolaire non pas dans Annee.
** si on dit l'annee XXXX/YYYY on parle de l'année scolaire XXXX/YYYY. 
**les table eleve et parent et enseingant ne contienne pas les noms et les prenoms . ils se trouvent dans la table personne.
**les table eleve et parent et enseingant ne contienne pas les numéro de telephnone Tel1 et Tel2 . ils se trouvent dans la table personne.
**les colonnes principale du table personne sont : id, NomFr, PrenomFr, NomAr , PrenomAr, Cin,AdresseFr, AdresseAr, Tel1, Tel2,Nationalite,Localite,Civilite.
**la trimestre 3 est d id 33, trimestre 2 est d id 32 , trimestre 1 est d id 31.
** le table des enseignants s'appelle enseingant non pas enseignant. 
**l id de l eleve est liée par l id de la personne par Idpersonne.  
**pour les CODECLASSEFR on met la classe entre guemets . exemple :CODECLASSEFR = '8B2'.
** le parametre du nom de la salle c'est nomSalleFr non NomSalle . 
** le nom de matière se trouve dans la table Matiere dans la colonne Nommatierefr.
**pour les nom de jour en français on a une colone libelleJourFr avec mercredi c'est ecrite Mercredi . 
**utiliser des JOINs explicites . exemple au lieu de :WHERE
    e.Classe = (SELECT id FROM classe WHERE CODECLASSEFR = '7B2')
    AND e.Jour = (SELECT id FROM jour WHERE libelleJourFr = 'Mercredi')
    ecrire:
 JOIN
     jour j ON e.Jour = j.id AND j.libelleJourFr = 'Mercredi'
JOIN
     classe c ON e.Classe = c.id AND c.CODECLASSEFR = '7B2'
** lorsque on veut savoir l id de l'eleve :  eleve.Idpersonne IN ({{children_ids}})
** lorsque on veut chercher la classe de l'eleve on fait : idClasse IN (SELECT id FROM classe WHERE id IN (SELECT Classe FROM inscriptioneleve WHERE Eleve IN (SELECT id FROM eleve WHERE IdPersonne IN ({{children_ids}}))))
** le nom de matière dans la table edumatiere est libematifr non pas NomMatiereFr .
** la matière mathématique s'appelle Maths dans la table matiere. 

POUR L'EMPLOI DU TEMPS :la semaine A est d'id 2 , la semaine B est d'id 3 , Sans semaine d'id 1.
** lorsque on ne précie pas la semaine faire la semaine d'id 1 sinon la semaine précisé.
SELECT 
    p.NomFr AS nom_enseignant,
    p.PrenomFr AS prenom_enseignant,
    m.NomMatiereFr AS nom_matiere,
    s.nomSalleFr AS nom_salle,
    sc1.debut AS debut_seance,
    sc2.fin AS fin_seance,
FROM
    emploidutemps e
JOIN
    jour j ON e.Jour = j.id AND j.libelleJourFr = (jour)
JOIN
    semaine sm ON e.Semaine = sm.id AND sm.id = (id_semaine)
JOIN
    salle s ON e.Salle = s.id
JOIN
    enseingant en ON e.Enseignant = en.id
JOIN
    personne p ON en.idPersonne = p.id
JOIN
    matiere m ON e.Matiere = m.id
JOIN
    seance sc1 ON e.SeanceDebut = sc1.id
JOIN
    seance sc2 ON e.SeanceFin = sc2.id
WHERE
    e.Classe IN (SELECT id FROM classe WHERE id IN (SELECT Classe FROM inscriptioneleve WHERE Eleve IN (SELECT id FROM eleve WHERE IdPersonne IN ({{children_ids}}))));

PAIEMENT:
** pour l'etat de paiement on n'a pas une colone qui s'appelle MontatTTC dans le table paiement et on donne seulement la tranche , le TotalTTC, le MontantRestant du tableau paiement . pas de MotifPaiement
** Pour les paiements extra ont extrait seulement : la Libelle du table paiementmotif et TotalTTC, MontantRestant du table paiementextra. NI TauxRemise,TotalRemise,NetHT,TauxTVA,TotalTVA,id.

NOTE DES DEVOIRS:
lorsque on demande une note on fait : 
        SELECT DISTINCT n.(code de devoir) AS note_devoir_controle
        FROM noteeleveparmatiere n
        JOIN inscriptioneleve ie ON n.id_inscription = ie.id
        WHERE ie.Eleve IN (SELECT id FROM eleve WHERE IdPersonne IN ({{children_ids}}))
        AND n.id_matiere = (SELECT id FROM matiere WHERE NomMatiereFr = (nom_de_matière))
        AND n.id_trimestre = (id_trimestre);
lorsque on demande une note d'un enfant précie:
        SELECT DISTINCT n.dc1 AS note_devoir_controle
        FROM noteeleveparmatiere n, inscriptioneleve ie, personne p, eleve e
        WHERE n.id_inscription = ie.id 
        AND ie.Eleve = e.id
        AND e.IdPersonne = p.id
        AND e.IdPersonne IN ({{children_ids}})
        AND p.PrenomFr = '(nom de l'enfant)'
        AND n.id_matiere = (SELECT id FROM matiere WHERE NomMatiereFr = '(nom de matière)')
        AND n.id_trimestre = 33;
** si on demande les notes d'une matière sont précision on fait  SELECT DISTINCT n.Orale, n.dc1, n.ds.
**Pour le maths SELECT DISTINCT n.dc1, n.dc2, n.ds .
** le devoir de controle s'appelle dc1 dans la table Noteeleveparmatiere .
** le devoir de controle ne s'appelle pas orale ni Orale dans la table Noteeleveparmatiere .
** le devoir de controle 2 s'appelle dc2.
** la note d'orale s'appelle orale.
** le devoir de synthese s'applle ds dans la table Noteeleveparmatiere.
** lorsque on veut avoir l'id de l'eleve du tableau eduresultatcopie on doit faire cette condition: WHERE eleve.idedusrv=Eduresultatcopie.idenelev. 
** pour avoir l id de l'eleve du table noteeleveparmatiere on fait: WHERE noteeleveparmatiere.id_inscription IN (SELECT id FROM inscriptioneleve WHERE Eleve IN (SELECT id FROM eleve WHERE IdPersonne IN ({{children_ids}})));
** lorsque on demande la moyenne d'une matière en fait ça :
SELECT ed.moyemati AS moyenne FROM
           Eduperiexam ex, Edumoymaticopie ed, Edumatiere em, Eleve e
           WHERE e.idedusrv=ed.idenelev and ed.codemati=em.codemati and
           ex.codeperiexam=ed.codeperiexam  and  e.Idpersonne IN ({{children_ids}})) and ed.moyemati not like '0.00' and ed.codeperiexam = (id_trimestre) and libematifr=(nom de matière);
REPARTITION D'EXAMEN
** lorsque on veut savoir la repartion des examens on l'extrait par nom de matiere , data , heure de debeut , heure de fin et la salle .
** l'examen est de TypeExamen = 2 dans la table repartitionexamen.
** les devoirs de controle est de TypeExamen = 1 dans la table repartitionexamen.
ABSENCE:
** lorsque on demande le nombre d'abscences par matière on donne le nom de la matière non pas son id .
MOYENNE TRIMESTRIELLES ET ANNUELLE:
**les résultats des trimestres se trouve dans le table Eduresultatcopie.
**Pour extraire la moyenne trimestrielle d une trimestre précise on fait cette requette:
SELECT er.moyeperiexam AS moyenneTrimestrielle
        FROM Eleve e, Eduresultatcopie er
        WHERE e.idedusrv=er.idenelev and e.Idpersonne IN ({{children_ids}})) and er.codeperiexam = (id_trimestre) ;


Voici la structure détaillée des tables pertinentes pour votre tâche (nom des tables, colonnes et leurs types) :
{{table_info}}

---
**Description des domaines pertinents pour cette question :**
{{relevant_domain_descriptions}}

---
**Informations Clés et Relations Fréquemment Utilisées pour une meilleure performance :**
{{relations}}

---
**Instructions pour la génération SQL :**
1.  Répondez UNIQUEMENT par une requête SQL MySQL valide et correcte.
2.  Ne mettez AUCUN texte explicatif ou commentaire avant ou après la requête SQL. La réponse doit être purement la requête.
3.  **Sécurité :** Générez des requêtes `SELECT` uniquement. Ne générez **JAMAIS** de requêtes `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE` ou toute autre commande de modification/suppression de données.
4.  **SÉCURITÉ PARENT:** TOUTE REQUÊTE DOIT INCLURE UN FILTRE LIMITANT AUX ENFANTS AUTORISÉS ({{children_ids}})
5.  **Gestion de l'Année Scolaire :** Si l'utilisateur mentionne une année au format 'YYYY-YYYY' (ex: '2023-2024'), interprétez-la comme équivalente à 'YYYY/YYYY' et utilisez ce format pour la comparaison sur la colonne `Annee` de `anneescolaire` ou pour trouver l'ID correspondant.
6.  **Robustesse aux Erreurs et Synonymes :** Le modèle doit être tolérant aux petites fautes de frappe et aux variations de langage.

Question : {{input}}
Requête SQL :
"""
)

import logging
logger = logging.getLogger(__name__)
load_dotenv()
class SQLAssistant:
    def __init__(self, db=None):
        self.db = db if db is not None else get_db_connection()
        self.relations_description = self._safe_load_relations()
        self.domain_descriptions = self._safe_load_domain_descriptions()
        self.domain_to_tables_mapping = self._safe_load_domain_to_tables_mapping()
        self.ask_llm = ask_llm
        self.cache = CacheManager()
        self.cache1 = CacheManager1()
        self.template_matcher = SemanticTemplateMatcher()
        self.sql_agent = SQLAgent(db=self.db)

        
        try:
            self.templates_questions = self.load_question_templates()
            if self.templates_questions:
                print(f"✅ {len(self.templates_questions)} templates chargés")
                self.template_matcher.load_templates(self.templates_questions)
            else:
                print("⚠️ Aucun template valide - fonctionnement en mode LLM seul")
                
        except ValueError as e:
            print(f"❌ Erreur de chargement des templates: {str(e)}")
            self.templates_questions = []
    def get_user_children_data(self, user_id: int) -> Tuple[List[int], List[str]]:
    
        connection = None
        cursor = None
        children_ids = []
        children_prenoms = []

        try:
            query = """
            SELECT DISTINCT pe.id AS id_enfant, pe.PrenomFr AS prenom
            FROM personne p
            JOIN parent pa ON p.id = pa.Personne
            JOIN parenteleve pev ON pa.id = pev.Parent
            JOIN eleve e ON pev.Eleve = e.id
            JOIN personne pe ON e.IdPersonne = pe.id
            WHERE p.id = %s
            """
            
            connection = get_db()
            cursor = connection.cursor()
            
            cursor.execute(query, (user_id,))
            children = cursor.fetchall()
            
            if children:
                children_ids = [child['id_enfant'] for child in children]
                children_prenoms = [child['prenom'] for child in children]
                logger.info(f"✅ Found {len(children_ids)} children for parent {user_id}")
                logger.info(f"les prenoms sont {[children_prenoms]}")
            
            return (children_ids, children_prenoms)
            
        except Exception as e:
            logger.error(f"❌ Error getting children data for parent {user_id}: {str(e)}")
            logger.error(traceback.format_exc())
            return ([], [])
            
        finally:
            try:
                if cursor:
                    cursor.close()
                    
                if connection:
                    from flask import current_app
                    is_flask_managed = (
                        current_app and 
                        hasattr(current_app, 'extensions') and 
                        'mysql' in current_app.extensions and 
                        connection == current_app.extensions['mysql'].connection
                    )
                    
                    if not is_flask_managed:
                        connection.close()
                        logger.debug("🔌 Closed direct MySQL connection")
            except Exception as close_error:
                logger.warning(f"⚠️ Error during cleanup: {str(close_error)}")
    def detect_names_in_question(self, question: str, authorized_names: List[str]) -> Dict[str, List[str]]:
        # Normaliser les prénoms autorisés (enlever accents, mettre en minuscules)
        def normalize_name(name):
            import unicodedata
            name = unicodedata.normalize('NFD', name.lower())
            return ''.join(char for char in name if unicodedata.category(char) != 'Mn')
        
        normalized_authorized = [normalize_name(name) for name in authorized_names]
        
        # Mots à exclure (ne sont pas des prénoms)
        excluded_words = {
            'mon', 'ma', 'mes', 'le', 'la', 'les', 'de', 'du', 'des', 'et', 'ou', 'si', 'ce', 
            'cette', 'ces', 'son', 'sa', 'ses', 'notre', 'nos', 'votre', 'vos', 'leur', 'leurs',
            'enfant', 'enfants', 'fils', 'fille', 'garçon', 'petit', 'petite', 'grand', 'grande',
            'eleve', 'élève', 'eleves', 'élèves', 'classe', 'école', 'ecole', 'moyenne', 'note', 
            'notes', 'résultat', 'resultats', 'trimestre', 'année', 'annee', 'matière', 'matiere',
            'emploi', 'temps', 'horaire', 'professeur', 'enseignant', 'directeur', 'principal'
        }
        
        # Extraire tous les mots qui pourraient être des prénoms (commence par une majuscule)
        potential_names = re.findall(r'\b[A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞŸ][a-zàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ]+', question)
        
        # Filtrer les mots exclus
        potential_names = [name for name in potential_names if normalize_name(name) not in excluded_words]
        
        authorized_found = []
        unauthorized_found = []
        
        for name in potential_names:
            normalized_name = normalize_name(name)
            if normalized_name in normalized_authorized:
                authorized_found.append(name)
            else:
                # Vérifier si ce n'est pas juste un mot français commun
                # (cette liste pourrait être étendue selon les besoins)
                common_words = {'Merci', 'Bonjour', 'Salut', 'Cordialement', 'Madame', 'Monsieur', 
                              'Mademoiselle', 'Docteur', 'Professeur', 'Janvier', 'Février', 'Mars', 
                              'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 
                              'Novembre', 'Décembre', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 
                              'Vendredi', 'Samedi', 'Dimanche', 'France', 'Tunisie', 'Français'}
                
                if name not in common_words:
                    unauthorized_found.append(name)
        
        print(f"🔍 Prénoms détectés - Autorisés: {authorized_found}, Non autorisés: {unauthorized_found}")
        
        return {
            "authorized_names": authorized_found,
            "unauthorized_names": unauthorized_found
        }
    def validate_parent_access(self, sql_query: str, children_ids: List[int]) -> bool:
        # Validation des inputs
        if not isinstance(children_ids, list):
            raise TypeError("children_ids doit être une liste")
            
        if not children_ids:
            return False
            
        try:
            children_ids_str = [str(int(id)) for id in children_ids]
        except (ValueError, TypeError):
            raise ValueError("Tous les IDs enfants doivent être numériques")
        
        # Normalisation plus douce de la requête (garder un espace pour séparer les mots)
        sql_lower = sql_query.lower().replace("\n", " ").replace("\t", " ")
        # Normaliser les espaces multiples en un seul
        import re
        sql_lower = re.sub(r'\s+', ' ', sql_lower).strip()
        
        print(f"🔍 SQL normalisé: {sql_lower}")  # Debug
        print(f"👶 IDs enfants: {children_ids_str}")  # Debug
        
        # Préparation des motifs de sécurité
        security_patterns = set()
        
        # 1. Filtres directs avec plus de variantes
        if len(children_ids_str) == 1:
            child_id = children_ids_str[0]
            security_patterns.update({
                f"idpersonne = {child_id}",
                f"idpersonne={child_id}",
                f"e.idpersonne = {child_id}",
                f"e.idpersonne={child_id}",
                f"eleve.idpersonne = {child_id}",
                f"eleve.idpersonne={child_id}",
                f"idpersonne in ({child_id})",
                f"eleve = ({child_id})",
                f"Eleve = ({child_id})",
                f"eleve = {child_id}",
                f"Eleve = {child_id}"
            })
        else:
            ids_joined = ",".join(children_ids_str)
            ids_joined_spaced = ", ".join(children_ids_str)
            security_patterns.update({
                f"idpersonne in ({ids_joined})",
                f"idpersonne in({ids_joined})",
                f"idpersonne in ({ids_joined_spaced})",
                f"e.idpersonne in ({ids_joined})",
                f"e.idpersonne in({ids_joined})",
                f"e.idpersonne in ({ids_joined_spaced})",
                f"eleve.idpersonne in ({ids_joined})",
                f"eleve.idpersonne in({ids_joined})",
                f"eleve.idpersonne in ({ids_joined_spaced})",
                f"id_personne in ({ids_joined})",
                f"id_personne in({ids_joined})",
                f"id_personne in ({ids_joined_spaced})"
            })
        
        # 2. Sous-requêtes de sécurité (patterns plus complets)
        for child_id in children_ids_str:
            security_patterns.update({
                f"eleve in (select id from eleve where idpersonne = {child_id}",
                f"eleve in (select id from eleve where idpersonne={child_id}",
                f"exists (select 1 from eleve where idpersonne = {child_id}",
                f"exists (select 1 from eleve where idpersonne={child_id}",
                f"exists(select 1 from eleve where idpersonne = {child_id}",
                f"exists(select 1 from eleve where idpersonne={child_id}",
                f"ed.idenelev IN (SELECT id FROM eleve WHERE IdPersonne IN {child_id})",
                f"e.idpersonne in ({child_id})",
                f"eleve = ({child_id})",
                f"Eleve = ({child_id})",
                f"eleve = {child_id}",
                f"Eleve = {child_id}"
            })
        
        # Pour les listes d'IDs
        if len(children_ids_str) > 1:
            ids_joined = ",".join(children_ids_str)
            ids_joined_spaced = ", ".join(children_ids_str)
            security_patterns.update({
                f"eleve in (select id from eleve where idpersonne in ({ids_joined})",
                f"eleve in (select id from eleve where idpersonne in({ids_joined})",
                f"eleve in (select id from eleve where idpersonne in ({ids_joined_spaced})",
                f"exists (select 1 from eleve where idpersonne in ({ids_joined})",
                f"exists (select 1 from eleve where idpersonne in({ids_joined})",
                f"exists (select 1 from eleve where idpersonne in ({ids_joined_spaced})",
                f"exists(select 1 from eleve where idpersonne in ({ids_joined})",
                f"exists(select 1 from eleve where idpersonne in({ids_joined})",
                f"exists(select 1 from eleve where idpersonne in ({ids_joined_spaced})"
            })
        
        print(f"🔒 Patterns de sécurité recherchés:")
        for pattern in sorted(security_patterns):
            print(f"   - '{pattern}'")
        
        # 3. Vérification des motifs
        found_patterns = []
        for pattern in security_patterns:
            if pattern in sql_lower:
                found_patterns.append(pattern)
        
        print(f"✅ Patterns trouvés: {found_patterns}")
        
        if not found_patterns:
            logger.warning(f"Requête parent non sécurisée - Filtre enfants manquant: {sql_query}")
            print(f"❌ Aucun pattern de sécurité trouvé dans la requête")
            return False
        
        # 4. Vérification des injections potentielles
        forbidden_patterns = {
             "--", "/*", "*/", " drop ", " truncate ", " insert ", " update ", " delete "
        }
        found_forbidden = [pattern for pattern in forbidden_patterns if pattern in sql_lower]
        
        if found_forbidden:
            logger.error(f"Tentative de requête non autorisée détectée: {found_forbidden}")
            print(f"❌ Patterns interdits trouvés: {found_forbidden}")
            return False
        
        print(f"✅ Validation parent réussie")
        return True
    def ask_question(self, question: str, user_id: Optional[int] = None, roles: Optional[List[str]] = None) -> tuple[str, str]:
        """Version strictement authentifiée"""
        if user_id is None:
            user_id = 0  # Or some default system user
    
        if roles is None:
            roles = []
        # 1. Validation des rôles
        if not roles:
            return "", "❌ Accès refusé : Aucun rôle fourni"
        
        valid_roles = ['ROLE_SUPER_ADMIN', 'ROLE_PARENT']
        has_valid_role = any(role in valid_roles for role in roles)
        
        print(f"DEBUG - has_valid_role: {has_valid_role}")
        
        if not has_valid_role:
            return "", f"❌ Accès refusé : Rôles fournis {roles}, requis {valid_roles}"

        # 2. Traitement par rôle
        try:
            if 'ROLE_SUPER_ADMIN' in roles:
                return self._process_super_admin_question(question)
            elif 'ROLE_PARENT' in roles:
                return self._process_parent_question(question, user_id)
        except Exception as e:
            return "", f"❌ Erreur : {str(e)}"
    def _process_super_admin_question(self, question: str) -> tuple[str, str]:
        """Traite une question avec accès admin complet"""
        
        # 1. Vérifier le cache
        cached = self.cache.get_cached_query(question)
        if cached:
            sql_template, variables = cached
            sql_query = sql_template
            for column, value in variables.items():
                sql_query = sql_query.replace(f"{{{column}}}", value)
            
            print("⚡ Requête admin récupérée depuis le cache")
            try:
                result = self.db.run(sql_query)
                return sql_query, self._format_sql_agent_result(result, question)
            except Exception as db_error:
                return sql_query, f"❌ Erreur d'exécution SQL : {str(db_error)}"
        
        # 2. Vérifier les templates existants
        template_match = self.find_matching_template(question)
        if template_match:
            print("🔍 Template admin trouvé")
            sql_query = self.generate_query_from_template(
                template_match["template"],
                template_match["variables"]
            )
            try:
                result = self.db.run(sql_query)
                formatted_result = self._format_sql_agent_result(result, question)
                return sql_query, formatted_result
            except Exception as db_error:
                return sql_query, f"❌ Erreur d'exécution SQL : {str(db_error)}"
        
        # ✅ 3. NOUVEAU: Essayer SQLAgent avec ses prompts spécialisés
        try:
            print("🤖 Tentative avec SQLAgent et prompts spécialisés")
            sql_agent_result = self.sql_agent.get_response(question)
            
            if sql_agent_result and sql_agent_result.get('status') == 'success':
                sql_query = sql_agent_result.get('sql_query', '')
                formatted_response = self._format_sql_agent_response(sql_agent_result, question)
                self.cache.cache_query(question, sql_query)
                return sql_query, formatted_response
            else:
                print("⚠️ SQLAgent n'a pas réussi, passage au LLM standard")
                
        except Exception as sql_agent_error:
            print(f"❌ Erreur SQLAgent: {sql_agent_error}")
            # Continue vers le LLM standard
        
        # 4. Génération via LLM (template admin) - Fallback
        print("🔍 Génération LLM standard pour admin")
        relevant_domains = self.get_relevant_domains(question, self.domain_descriptions)
        if relevant_domains:
            # 2. Tables associées
            relevant_tables = self.get_tables_from_domains(relevant_domains, self.domain_to_tables_mapping)
            # 3. Structure SQL réduite
            table_info = self.db.get_table_info(relevant_tables)
            # 4. Descriptions réduites
            relevant_domain_descriptions = "\n".join(
                f"{dom}: {self.domain_descriptions[dom]}" for dom in relevant_domains if dom in self.domain_descriptions
            )
        else:
            # fallback : tout injecter si rien trouvé
            table_info = self.db.get_table_info()
            relevant_domain_descriptions = "\n".join(self.domain_descriptions.values())

        prompt = ADMIN_PROMPT_TEMPLATE.format(
            input=question,
            table_info=table_info,
            relevant_domain_descriptions=relevant_domain_descriptions,
            relations=self.relations_description
        )

        llm_response = self.ask_llm(prompt)
        sql_query = llm_response.replace("```sql", "").replace("```", "").strip()
        
        if not sql_query:
            return "", "❌ La requête générée est vide."

        try:
            result = self.db.run(sql_query)
            formatted_result = self._format_sql_agent_result(result, question)
            self.cache.cache_query(question, sql_query)
            return sql_query, formatted_result
        except Exception as db_error:
            return sql_query, f"❌ Erreur d'exécution SQL : {str(db_error)}"
    def _safe_load_relations(self) -> str:
        """Charge les relations avec gestion d'erreurs"""
        try:
            relations_path = Path(__file__).parent / 'prompts' / 'relations.txt'
            if relations_path.exists():
                return relations_path.read_text(encoding='utf-8')
            print("⚠️ Fichier relations.txt non trouvé, utilisation valeur par défaut")
            return "# Aucune relation définie"
        except Exception as e:
            print(f"❌ Erreur chargement relations: {e}")
            return "# Erreur chargement relations"
    def _safe_load_domain_descriptions(self) -> dict:
        """Charge les descriptions de domaine avec gestion d'erreurs"""
        try:
            domain_path = Path(__file__).parent / 'prompts' / 'domain_descriptions.json'
            if domain_path.exists():
                with open(domain_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            print("⚠️ Fichier domain_descriptions.json non trouvé")
            return {}
        except Exception as e:
            print(f"❌ Erreur chargement domain descriptions: {e}")
            return {}
    def find_matching_template(self, question: str) -> Optional[Dict[str, Any]]:
        exact_match = self._find_exact_template_match(question)
        if exact_match:
            return exact_match
        
        semantic_match, score = self.template_matcher.find_similar_template(question)
        if semantic_match:
            print(f"🔍 Template sémantiquement similaire trouvé (score: {score:.2f})")
            return self._extract_variables(question, semantic_match)
        
        return None
    def _safe_load_domain_to_tables_mapping(self) -> dict:
        """Charge le mapping domaine-tables avec gestion d'erreurs"""
        try:
            mapping_path = Path(__file__).parent / 'prompts' / 'domain_tables_mapping.json'
            if mapping_path.exists():
                with open(mapping_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            print("⚠️ Fichier domain_tables_mapping.json non trouvé")
            return {}
        except Exception as e:
            print(f"❌ Erreur chargement domain mapping: {e}")
            return {}
    def load_question_templates(self) -> list:
        try:
            templates_path = Path(__file__).parent / 'templates_questions.json'
            
            if not templates_path.exists():
                print(f"⚠️ Fichier non trouvé, création: {templates_path}")
                templates_path.write_text('{"questions": []}', encoding='utf-8')
                return []

            content = templates_path.read_text(encoding='utf-8').strip()
            if not content:
                print("⚠️ Fichier vide, réinitialisation")
                templates_path.write_text('{"questions": []}', encoding='utf-8')
                return []

            try:
                data = json.loads(content)
                if not isinstance(data.get("questions", []), list):
                    raise ValueError("Format invalide: 'questions' doit être une liste")
                
                valid_templates = []
                for template in data["questions"]:
                    if all(key in template for key in ["template_question", "requete_template"]):
                        valid_templates.append(template)
                    else:
                        print(f"⚠️ Template incomplet ignoré: {template.get('description', 'sans description')}")
                
                return valid_templates

            except json.JSONDecodeError as e:
                print(f"❌ Fichier JSON corrompu, réinitialisation. Erreur: {e}")
                backup_path = templates_path.with_suffix('.bak.json')
                templates_path.rename(backup_path)
                templates_path.write_text('{"questions": []}', encoding='utf-8')
                return []

        except Exception as e:
            print(f"❌ Erreur critique lors du chargement: {e}")
            return []
    def get_relevant_domains(self, query: str, domain_descriptions: Dict[str, str]) -> List[str]:
        """Identifies relevant domains based on a user query using DeepSeek."""
        domain_desc_str = "\n".join([f"- {name}: {desc}" for name, desc in domain_descriptions.items()])
        domain_prompt_content = f"""
        Based on the following user question, identify ALL relevant domains from the list below.
        Return only the names of the relevant domains, separated by commas. If no domain is relevant, return 'None'.

        User Question: {query}

        Available Domains and Descriptions:
        {domain_desc_str}

        Relevant Domains (comma-separated):
        """
        
        try:
            response = self.ask_llm(domain_prompt_content)
            domain_names = response.strip()
            
            if domain_names.lower() == 'none' or not domain_names:
                return []
            print("domain_récupérer")
            return [d.strip() for d in domain_names.split(',')]
        except Exception as e:
            print(f"❌ Erreur lors de l'identification des domaines: {e}")
            return []
    def get_tables_from_domains(self, domains: List[str], domain_to_tables_map: Dict[str, List[str]]) -> List[str]:
        """Retrieves all tables associated with the given domains."""
        tables = []
        for domain in domains:
            tables.extend(domain_to_tables_map.get(domain, []))
        return sorted(list(set(tables)))
    def _safe_load_domain_descriptions(self) -> dict:
        """Charge les descriptions de domaine avec gestion d'erreurs"""
        try:
            domain_path = Path(__file__).parent / 'prompts' / 'domain_descriptions.json'
            if domain_path.exists():
                with open(domain_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            print("⚠️ Fichier domain_descriptions.json non trouvé")
            return {}
        except Exception as e:
            print(f"❌ Erreur chargement domain descriptions: {e}")
            return {}
    def _find_exact_template_match(self, question: str) -> Optional[Dict[str, Any]]:
        cleaned_question = question.rstrip(' ?')
        for template in self.templates_questions:
            pattern = template["template_question"]
            regex_pattern = re.sub(r'\{(.+?)\}', r'(?P<\1>.+?)', pattern)
            match = re.fullmatch(regex_pattern, cleaned_question, re.IGNORECASE)
            if match:
                variables = {k: v.strip() for k, v in match.groupdict().items()}
                return {
                    "template": template,
                    "variables": variables if variables else {}
                }
        return None
    def _process_parent_question(self, question: str, user_id: int) -> tuple[str, str]:
        """Traite une question avec restrictions parent"""
        
        self.cache1.clean_double_braces_in_cache()
        cached = self.cache1.get_cached_query(question, user_id)
        if cached:
            sql_template, variables = cached
            sql_query = sql_template
            for column, value in variables.items():
                sql_query = sql_query.replace(f"{{{column}}}", value)
            
            print("⚡ Requête parent récupérée depuis le cache")
            try:
                result = self.db.run(sql_query)
                return sql_query, self._format_sql_agent_result(result, question)
            except Exception as db_error:
                return sql_query, f"❌ Erreur d'exécution SQL : {str(db_error)}"
            

        children_ids, children_prenoms = self.get_user_children_data(user_id)
        children_ids_str = ", ".join(map(str, children_ids))
        children_names_str = ", ".join(children_prenoms)
        if not children_ids:
            return "", "❌ Aucun enfant trouvé pour ce parent  ou erreur d'accès."
        
        print(f"🔒 Restriction parent - Enfants autorisés: {children_ids}")

        detected_names = self.detect_names_in_question(question, children_prenoms)
        if detected_names["unauthorized_names"]:
            unauthorized_list = ", ".join(detected_names["unauthorized_names"])
            return "", f"❌ Accès interdit: Vous n'avez pas le droit de consulter les données de {unauthorized_list}"
        
        relevant_domains = self.get_relevant_domains(question, self.domain_descriptions)
        if relevant_domains:
            # 2. Tables associées
            relevant_tables = self.get_tables_from_domains(relevant_domains, self.domain_to_tables_mapping)
            # 3. Structure SQL réduite
            table_info = self.db.get_table_info(relevant_tables)
            # 4. Descriptions réduites
            relevant_domain_descriptions = "\n".join(
                f"{dom}: {self.domain_descriptions[dom]}" for dom in relevant_domains if dom in self.domain_descriptions
            )
        else:
            # fallback : tout injecter si rien trouvé
            table_info = self.db.get_table_info()
            relevant_domain_descriptions = "\n".join(self.domain_descriptions.values())

        prompt = PARENT_PROMPT_TEMPLATE.format(
            input=question,
            table_info=self.db.get_table_info(),
            relevant_domain_descriptions=relevant_domain_descriptions,
            relations=self.relations_description,
            user_id=user_id,
            children_ids=children_ids_str,
            children_names=children_names_str 
        )
        
        llm_response = self.ask_llm(prompt)
        sql_query = llm_response.replace("```sql", "").replace("```", "").strip()
        
        if not sql_query:
            return "", "❌ La requête générée est vide."

        def is_public_info_query(question: str, sql_query: str) -> bool:
            """Vérifie si la question concerne des informations publiques (cantine, actualité)"""
            question_lower = question.lower()
            sql_lower = sql_query.lower()
            
            # Mots-clés pour la cantine
            cantine_keywords = ['cantine', 'repas', 'menu', 'déjeuner', 'restauration']
            
            # Mots-clés pour l'actualité
            actualite_keywords = ['actualité', 'actualite', 'actualités', 'actualites', 'nouvelles', 'informations', 'annonces']
            
            # Tables liées à la cantine et l'actualité
            public_tables = ['cantine', 'menu', 'actualite', 'actualite1', 'annonces']
            
            # Vérifier les mots-clés dans la question
            has_cantine_keywords = any(keyword in question_lower for keyword in cantine_keywords)
            has_actualite_keywords = any(keyword in question_lower for keyword in actualite_keywords)
            
            # Vérifier les tables dans la requête SQL
            has_public_tables = any(table in sql_lower for table in public_tables)
            
            return (has_cantine_keywords or has_actualite_keywords or has_public_tables)

        # Validation de sécurité pour les parents (sauf pour cantine/actualité)
        if not is_public_info_query(question, sql_query):
            if not self.validate_parent_access(sql_query, children_ids):
                return "", "❌ Accès refusé: La requête ne respecte pas les restrictions parent."
        else:
            print("ℹ️ Question sur information publique (cantine/actualité) - validation de sécurité bypassée")

        try:
            # CORRECTION: Utilisation cohérente de db.run() et formatage du résultat
            raw_result = self.db.run(sql_query)
            print(f"🔍 Type de résultat brut: {type(raw_result)}")
            print(f"🔍 Contenu résultat brut: {raw_result}")
            
            # Convertir le résultat brut en format liste de dictionnaires
            if isinstance(raw_result, str):
                # Si c'est une chaîne (format tabulaire), utiliser la méthode existante
                formatted_result = self._format_sql_agent_result(raw_result, question)
            else:
                # Si c'est déjà des données structurées, les convertir
                try:
                    # Essayer de parser les données pour SQLAgent
                    if hasattr(raw_result, '__iter__') and not isinstance(raw_result, str):
                        # C'est probablement une liste de tuples ou liste de dictionnaires
                        if raw_result and isinstance(raw_result[0], tuple):
                            # Convertir les tuples en dictionnaires
                            # On a besoin des noms de colonnes, mais on peut les deviner
                            columns = [f'col_{i}' for i in range(len(raw_result[0]))]
                            data_list = [dict(zip(columns, row)) for row in raw_result]
                        elif raw_result and isinstance(raw_result[0], dict):
                            data_list = raw_result
                        else:
                            data_list = []
                        
                        formatted_result = self._format_sql_agent_result(data_list, question)
                    else:
                        formatted_result = self._format_sql_agent_result(raw_result, question)
                except Exception as parse_error:
                    logger.error(f"Erreur parsing résultat: {parse_error}")
                    formatted_result = self._format_sql_agent_result(str(raw_result), question)
            
            self.cache1.cache_query(question, sql_query)
            return sql_query, formatted_result
            
        except Exception as db_error:
            logger.error(f"Erreur DB dans _process_parent_question: {str(db_error)}")
            return sql_query, f"❌ Erreur d'exécution SQL : {str(db_error)}"
    def _format_sql_agent_result(self, data_list, question: str = "") -> str:
        """Formate les résultats pour SQLAgent en format compatible DataFrame"""
        
        if not data_list:
            return "✅ Requête exécutée mais aucun résultat trouvé."
        
        try:
            import pandas as pd
            
            # Handle different data types
            if isinstance(data_list, str):
                return data_list
                
            # Convert data to proper format for DataFrame
            df_data = []
            
            if isinstance(data_list, list) and data_list:
                first_item = data_list[0]
                
                # Case 1: List of tuples (common database result format)
                if isinstance(first_item, tuple):
                    # For single column results like COUNT(*)
                    if len(first_item) == 1:
                        # Extract the column name from SQL query if possible
                        column_name = "resultat"
                        if question and "count" in question.lower():
                            column_name = "nombre"
                        elif "SELECT COUNT(*)" in str(data_list) or any("count" in str(item).lower() for item in data_list):
                            column_name = "nombre"
                        
                        df_data = [{column_name: item[0]} for item in data_list]
                    else:
                        # Multiple columns - generate generic column names
                        num_cols = len(first_item)
                        columns = [f'col_{i+1}' for i in range(num_cols)]
                        df_data = [dict(zip(columns, item)) for item in data_list]
                
                # Case 2: List of dictionaries (already properly formatted)
                elif isinstance(first_item, dict):
                    df_data = data_list
                
                # Case 3: List of single values
                elif not isinstance(first_item, (list, tuple, dict)):
                    column_name = "resultat"
                    if question and "count" in question.lower():
                        column_name = "nombre"
                    df_data = [{column_name: item} for item in data_list]
                
                # Case 4: Other formats - convert to string
                else:
                    return str(data_list)
            else:
                return str(data_list)
            
            # Create DataFrame from properly formatted data
            df = pd.DataFrame(df_data)
            
            # Format the result
            if len(df) == 1 and len(df.columns) == 1:
                # Single result (like COUNT)
                value = df.iloc[0, 0]
                column_name = df.columns[0]
                
                # Special formatting for count queries
                if question and any(word in question.lower() for word in ["nombre", "combien", "count"]):
                    if "absence" in question.lower():
                        return f"Nombre d'absences : {value}"
                    elif "élève" in question.lower() or "eleve" in question.lower():
                        return f"Nombre d'élèves : {value}"
                    else:
                        return f"Résultat : {value}"
                else:
                    return f"{column_name.title()} : {value}"
            
            # Multiple results - use tabulate for better display
            try:
                from tabulate import tabulate
                table = tabulate(df, headers='keys', tablefmt='grid', showindex=False)
                
                if question:
                    return f"Résultats pour: {question}\n\n{table}"
                return table
            except ImportError:
                # Fallback without tabulate
                result_lines = []
                if question:
                    result_lines.append(f"Résultats pour: {question}\n")
                    
                for i, row in df.iterrows():
                    if i == 0:
                        # Headers
                        headers = " | ".join(df.columns)
                        result_lines.append(headers)
                        result_lines.append("-" * len(headers))
                    
                    # Data
                    values = " | ".join(str(v) for v in row.values)
                    result_lines.append(values)
                
                return "\n".join(result_lines)
                
        except ImportError:
            # Fallback without pandas
            if isinstance(data_list, list) and data_list:
                first_item = data_list[0]
                
                if isinstance(first_item, tuple) and len(first_item) == 1:
                    value = first_item[0]
                    if question and any(word in question.lower() for word in ["nombre", "combien", "count"]):
                        if "absence" in question.lower():
                            return f"Nombre d'absences : {value}"
                        elif "élève" in question.lower() or "eleve" in question.lower():
                            return f"Nombre d'élèves : {value}"
                        else:
                            return f"Résultat : {value}"
                    return f"Résultat : {value}"
                
            return str(data_list)
            
        except Exception as e:
            logger.error(f"Erreur formatage SQLAgent: {e}")
            # Emergency fallback - extract the actual value
            try:
                if isinstance(data_list, list) and data_list:
                    first_item = data_list[0]
                    if isinstance(first_item, tuple) and len(first_item) == 1:
                        value = first_item[0]
                        if question and any(word in question.lower() for word in ["nombre", "combien", "count"]):
                            if "absence" in question.lower():
                                return f"Nombre d'absences : {value}"
                            return f"Résultat : {value}"
                        return f"Résultat : {value}"
                return str(data_list)
            except:
                return f"❌ Erreur de formatage: {str(e)}\nDonnées: {data_list}"
    
    def _format_sql_agent_response(self, sql_agent_result, question: str) -> str:
        """Formate les résultats de SQLAgent pour l'affichage"""
        if not sql_agent_result:
            return "❌ Aucun résultat"
        
        response = sql_agent_result.get('response', '')
        if sql_agent_result.get('graph'):
            response += f"\n\n📊 Graphique généré"
        
        return response