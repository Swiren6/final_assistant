import json
import re

# Liste brute des relations que tu as copiée
relations_text = [
  "La colonne `Inscription` de la table `absence` est une clé étrangère qui fait référence à la colonne `id` de la table `inscriptioneleve`.",
  "La colonne `idFonctionalite` de la table `actionfonctionalitepriv` est une clé étrangère qui fait référence à la colonne `id` de la table `fonctionaliteprivelge`.",
  "La colonne `Inscription` de la table `avertissement` est une clé étrangère qui fait référence à la colonne `id` de la table `inscriptioneleve`.",
  "La colonne `idLocalite` de la table `banque` est une clé étrangère qui fait référence à la colonne `IDLOCALITE` de la table `localite`.",
  "La colonne `idPersonne` de la table `banque` est une clé étrangère qui fait référence à la colonne `id` de la table `personne`.",
  "La colonne `BanqueBordereau` de la table `banquebordereaudetails` est une clé étrangère qui fait référence à la colonne `id` de la table `banquebordereau`.",
  "La colonne `Reglement` de la table `banquebordereaudetails` est une clé étrangère qui fait référence à la colonne `id` de la table `reglementeleve`.",
  "La colonne `Bordereau` de la table `banqueversement` est une clé étrangère qui fait référence à la colonne `id` de la table `banquebordereau`.",
  "La colonne `Inscription` de la table `blame` est une clé étrangère qui fait référence à la colonne `id` de la table `inscriptioneleve`.",
  "La colonne `Utilisateur` de la table `caisse` est une clé étrangère qui fait référence à la colonne `id` de la table `utilisateur`.",
  "La colonne `Personne` de la table `caisse_log` est une clé étrangère qui fait référence à la colonne `id` de la table `personne`.",
  "La colonne `Utilisateur` de la table `caisse_log` est une clé étrangère qui fait référence à la colonne `id` de la table `utilisateur`.",
  "La colonne `Caisse` de la table `caissedetails` est une clé étrangère qui fait référence à la colonne `id` de la table `caisse`.",
  "La colonne `Utilisateur` de la table `caissedetails` est une clé étrangère qui fait référence à la colonne `id` de la table `utilisateur`.",
  "La colonne `Personne` de la table `caissedetails` est une clé étrangère qui fait référence à la colonne `id` de la table `personne`.",
  "La colonne `IdVersement` de la table `caissedetails` est une clé étrangère qui fait référence à la colonne `id` de la table `banqueversement`.",
  "La colonne `Reglement` de la table `caissedetails` est une clé étrangère qui fait référence à la colonne `id` de la table `reglementeleve`.",
  "La colonne `CantineParJour` de la table `caissedetails` est une clé étrangère qui fait référence à la colonne `id` de la table `cantineparjour`.",
  "La colonne `CourEteId` de la table `caissedetails` est une clé étrangère qui fait référence à la colonne `id` de la table `paiementdetailscourete`.",
  "La colonne `Utilisateur` de la table `cantineparjour` est une clé étrangère qui fait référence à la colonne `id` de la table `utilisateur`.",
  "La colonne `Utilisateur` de la table `cantineparjourenseignant` est une clé étrangère qui fait référence à la colonne `id` de la table `utilisateur`.",
  "La colonne `CODEETAB` de la table `classe` est une clé étrangère qui fait référence à la colonne `id` de la table `etablissement`.",
  "La colonne `IDNIV` de la table `classe` est une clé étrangère qui fait référence à la colonne `id` de la table `niveau`.",
  "La colonne `CODEGOUV` de la table `delegation` est une clé étrangère qui fait référence à la colonne `id` de la table `gouvernorat`.",
  "La colonne `idEnseignant` de la table `disponibiliteenseignant` est une clé étrangère qui fait référence à la colonne `id` de la table `enseingant`.",
  "La colonne `idJour` de la table `disponibiliteenseignant` est une clé étrangère qui fait référence à la colonne `id` de la table `jour`.",
  "La colonne `CODEGOUV` de la table `dre` est une clé étrangère qui fait référence à la colonne `id` de la table `gouvernorat`.",
  "La colonne `IdPersonne` de la table `eleve` est une clé étrangère qui fait référence à la colonne `id` de la table `personne`.",
  "La colonne `idPersonne` de la table `enseigantmatiere` est une clé étrangère qui fait référence à la colonne `id` de la table `personne`.",
  "La colonne `idMatiere` de la table `enseigantmatiere` est une clé étrangère qui fait référence à la colonne `id` de la table `matiere`.",
  "La colonne `anneeSco` de la table `enseigantmatiere` est une clé étrangère qui fait référence à la colonne `id` de la table `anneescolaire`.",
  "La colonne `IdDip` de la table `enseingant` est une clé étrangère qui fait référence à la colonne `id` de la table `diplome`.",
  "La colonne `IdModPaiement` de la table `enseingant` est une clé étrangère qui fait référence à la colonne `id` de la table `modalitepaiement`.",
  "La colonne `idPersonne` de la table `enseingant` est une clé étrangère qui fait référence à la colonne `id` de la table `personne`.",
  "La colonne `IdQualite` de la table `enseingant` est une clé étrangère qui fait référence à la colonne `id` de la table `qualite`.",
  "La colonne `IdSituation` de la table `enseingant` est une clé étrangère qui fait référence à la colonne `id` de la table `situationfamilliale`.",
  "La colonne `CODEGOUV` de la table `etablissement` est une clé étrangère qui fait référence à la colonne `id` de la table `gouvernorat`.",
  "La colonne `CODEDRE` de la table `etablissement` est une clé étrangère qui fait référence à la colonne `id` de la table `dre`.",
  "La colonne `CODETYPEETAB` de la table `etablissement` est une clé étrangère qui fait référence à la colonne `id` de la table `typeetablissement`.",
  "La colonne `preinscription` de la table `fichierpreinscriptionpreinscription` est une clé étrangère qui fait référence à la colonne `id` de la table `preinscriptionpreinscription`.",
  "La colonne `idRubrique` de la table `fonctionaliteprivelge` est une clé étrangère qui fait référence à la colonne `id` de la table `rubrique`.",
  "La colonne `AnneeScolaire` de la table `inscriptioneleve` est une clé étrangère qui fait référence à la colonne `id` de la table `anneescolaire`.",
  "La colonne `Personne` de la table `inscriptioneleve` est une clé étrangère qui fait référence à la colonne `id` de la table `personne`.",
  "La colonne `idannee` de la table `jourfr` est une clé étrangère qui fait référence à la colonne `id` de la table `anneescolaire`.",
  "La colonne `Modalite` de la table `modalitetranche` est une clé étrangère qui fait référence à la colonne `id` de la table `modalite`.",
  "La colonne `AnneeScolaire` de la table `modalitetranche` est une clé étrangère qui fait référence à la colonne `id` de la table `anneescolaire`.",
  "La colonne `MotifPaiement` de la table `paiement` est une clé étrangère qui fait référence à la colonne `id` de la table `paiementmotif`.",
  "La colonne `Inscription` de la table `paiement` est une clé étrangère qui fait référence à la colonne `id` de la table `inscriptioneleve`.",
  "La colonne `IdPaiement` de la table `paiementdetailscourete` est une clé étrangère qui fait référence à la colonne `id` de la table `paiementcourete`.",
  "La colonne `Inscription` de la table `paiementextra` est une clé étrangère qui fait référence à la colonne `id` de la table `inscriptioneleve`.",
  "La colonne `paiementmotif` de la table `paiementextra` est une clé étrangère qui fait référence à la colonne `id` de la table `paiementmotif`.",
  "La colonne `Personne` de la table `paiementextra` est une clé étrangère qui fait référence à la colonne `id` de la table `personne`.",
  "La colonne `AnneeScolaire` de la table `paiementextra` est une clé étrangère qui fait référence à la colonne `id` de la table `anneescolaire`.",
  "La colonne `Classe` de la table `paiementextra` est une clé étrangère qui fait référence à la colonne `id` de la table `classe`.",
  "La colonne `Modalite` de la table `paiementextra` est une clé étrangère qui fait référence à la colonne `id` de la table `modalite`.",
  "La colonne `PaiementExtras` de la table `paiementextradetails` est une clé étrangère qui fait référence à la colonne `id` de la table `paiementextra`.",
  "La colonne `Personne` de la table `parent` est une clé étrangère qui fait référence à la colonne `id` de la table `personne`.",
  "La colonne `Eleve` de la table `parenteleve` est une clé étrangère qui fait référence à la colonne `id` de la table `eleve`.",
  "La colonne `Parent` de la table `parenteleve` est une clé étrangère qui fait référence à la colonne `id` de la table `parent`.",
  "La colonne `Nationalite` de la table `personne` est une clé étrangère qui fait référence à la colonne `id` de la table `nationalite`.",
  "La colonne `Localite` de la table `personne` est une clé étrangère qui fait référence à la colonne `IDLOCALITE` de la table `localite`.",
  "La colonne `Civilite` de la table `personne` est une clé étrangère qui fait référence à la colonne `idCivilite` de la table `civilite`.",
  "La colonne `Localite` de la table `personnepreinscription` est une clé étrangère qui fait référence à la colonne `IDLOCALITE` de la table `localite`.",
  "La colonne `Civilite` de la table `personnepreinscription` est une clé étrangère qui fait référence à la colonne `idCivilite` de la table `civilite`.",
  "La colonne `Niveau` de la table `preinscription` est une clé étrangère qui fait référence à la colonne `id` de la table `niveau`.",
  "La colonne `NiveauPrecedent` de la table `preinscription` est une clé étrangère qui fait référence à la colonne `id` de la table `niveau`.",
  "La colonne `Section` de la table `preinscription` est une clé étrangère qui fait référence à la colonne `id` de la table `section`.",
  "La colonne `SectionPrecedent` de la table `preinscription` est une clé étrangère qui fait référence à la colonne `id` de la table `section`.",
  "La colonne `Personne` de la table `preinscription` est une clé étrangère qui fait référence à la colonne `id` de la table `personne`.",
  "La colonne `Eleve` de la table `preinscription` est une clé étrangère qui fait référence à la colonne `id` de la table `eleve`.",
  "La colonne `Niveau` de la table `preinscriptionpreinscription` est une clé étrangère qui fait référence à la colonne `id` de la table `niveau`.",
  "La colonne `NiveauPrecedent` de la table `preinscriptionpreinscription` est une clé étrangère qui fait référence à la colonne `id` de la table `niveau`.",
  "La colonne `Section` de la table `preinscriptionpreinscription` est une clé étrangère qui fait référence à la colonne `id` de la table `section`.",
  "La colonne `SectionPrecedent` de la table `preinscriptionpreinscription` est une clé étrangère qui fait référence à la colonne `id` de la table `section`.",
  "La colonne `Personne` de la table `preinscriptionpreinscription` est une clé étrangère qui fait référence à la colonne `id` de la table `personnepreinscription`.",
  "La colonne `Eleve` de la table `preinscriptionpreinscription` est une clé étrangère qui fait référence à la colonne `id` de la table `elevepreinscription`.",
  "La colonne `ModeReglement` de la table `reglementeleve` est une clé étrangère qui fait référence à la colonne `id` de la table `modereglement`.",
  "La colonne `IdExtra` de la table `reglementeleve` est une clé étrangère qui fait référence à la colonne `id` de la table `paiementextradetails`.",
  "La colonne `Personne` de la table `reglementeleve` est une clé étrangère qui fait référence à la colonne `id` de la table `personne`.",
  "La colonne `IdInscription` de la table `reglementeleve` est une clé étrangère qui fait référence à la colonne `id` de la table `paiement`.",
  "La colonne `Utilisateur` de la table `reglementeleve` est une clé étrangère qui fait référence à la colonne `id` de la table `utilisateur`.",
  "La colonne `IdUniformCommande` de la table `reglementeleve` est une clé étrangère qui fait référence à la colonne `id` de la table `uniformcommande`.",
  "La colonne `IdUniformCommande` de la table `reglementeleve_echeancier` est une clé étrangère qui fait référence à la colonne `id` de la table `uniformcommande`.",
  "La colonne `ModeReglement` de la table `reglementeleve_echeancier` est une clé étrangère qui fait référence à la colonne `id` de la table `modereglement`.",
  "La colonne `IdExtra` de la table `reglementeleve_echeancier` est une clé étrangère qui fait référence à la colonne `id` de la table `paiementextradetails`.",
  "La colonne `Personne` de la table `reglementeleve_echeancier` est une clé étrangère qui fait référence à la colonne `id` de la table `personne`.",
  "La colonne `Utilisateur` de la table `reglementeleve_echeancier` est une clé étrangère qui fait référence à la colonne `id` de la table `utilisateur`.",
  "La colonne `idPersonne` de la table `renseignementmedicaux` est une clé étrangère qui fait référence à la colonne `id` de la table `personne`.",
  "La colonne `idEleve` de la table `renseignementmedicaux` est une clé étrangère qui fait référence à la colonne `id` de la table `eleve`.",
  "La colonne `IdNiv` de la table `section` est une clé étrangère qui fait référence à la colonne `id` de la table `niveau`.",
  "La colonne `idPersonne` de la table `surveillant` est une clé étrangère qui fait référence à la colonne `id` de la table `personne`.",
  "La colonne `idSituation` de la table `surveillant` est une clé étrangère qui fait référence à la colonne `id` de la table `situationfamilliale`.",
  "La colonne `idDip` de la table `surveillant` est une clé étrangère qui fait référence à la colonne `id` de la table `diplome`.",
  "La colonne `idModPaiement` de la table `surveillant` est une clé étrangère qui fait référence à la colonne `id` de la table `modalitepaiement`.",
  "La colonne `idQualite` de la table `surveillant` est une clé étrangère qui fait référence à la colonne `id` de la table `qualite`.",
  "La colonne `UniformCommande` de la table `uniformcommandedetails` est une clé étrangère qui fait référence à la colonne `id` de la table `uniformcommande`.",
  "La colonne `Model` de la table `uniformcommandedetails` est une clé étrangère qui fait référence à la colonne `id` de la table `uniformmodel`.",
  "La colonne `Taille` de la table `uniformcommandedetails` est une clé étrangère qui fait référence à la colonne `id` de la table `uniformtaille`.",
  "La colonne `Couleur` de la table `uniformcommandedetails` est une clé étrangère qui fait référence à la colonne `id` de la table `uniformcouleur`.",
  "La colonne `Genre` de la table `uniformmodel` est une clé étrangère qui fait référence à la colonne `id` de la table `uniformgenre`.",
  "La colonne `grade` de la table `utilisateur` est une clé étrangère qui fait référence à la colonne `id` de la table `grade`.",
  "La colonne `idenelev` de la table `edumoymati` est une clé étrangère qui fait référence à la colonne `id` de la table `edueleve`."
]

relations_structured = []

for line in relations_text:
    match = re.match(
        r"La colonne `(.*?)` de la table `(.*?)` est une clé étrangère qui fait référence à la colonne `(.*?)` de la table `(.*?)`\.",
        line
    )
    if match:
        source_col, source_table, target_col, target_table = match.groups()
        relation_entry = {
            "relation": f"{source_table}.{source_col} = {target_table}.{target_col}",
            "tables": [source_table, target_table],
            "join_column": target_col,
            "description": line
        }
        relations_structured.append(relation_entry)
    else:
        print(f"❌ Non reconnu : {line}")

# Sauvegarde dans un fichier JSON
with open("rag_table_relationships.json", "w", encoding="utf-8") as f:
    json.dump(relations_structured, f, ensure_ascii=False, indent=2)

print(f"✅ {len(relations_structured)} relations exportées dans rag_table_relationships.json")
