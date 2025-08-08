from typing import List
import logging
import re

logger = logging.getLogger(__name__)

def is_super_admin(roles: List[str]) -> bool:
    """Vérifie si l'utilisateur est super admin"""
    return any(role.upper() == 'ROLE_SUPER_ADMIN' for role in roles)

def is_admin(roles: List[str]) -> bool:
    """Vérifie si l'utilisateur est admin"""
    return any(role.upper() == 'ROLE_ADMIN' for role in roles)

def is_parent(roles: List[str]) -> bool:
    """Vérifie si l'utilisateur est un parent"""
    return 'ROLE_PARENT' in [role.upper() for role in roles]

def validate_admin_access(sql_query: str) -> bool:
    """
    Valide les requêtes pour le rôle admin
    - Autorise la requête spéciale élèves-parents avec paiementmotif variable
    - Vérifie les injections SQL
    - Autorise seulement les SELECT
    """
    sql_lower = sql_query.lower().replace("\n", " ").replace("\t", " ")
    sql_lower = re.sub(r'\s+', ' ', sql_lower).strip()

    # Vérification des commandes interdites
    forbidden_patterns = {
        "--", "/*", "*/", " drop ", " truncate ", " insert ", " update ", 
        " delete ", " alter ", " create ", " grant ", " revoke "
    }
    if any(p in sql_lower for p in forbidden_patterns):
        logger.error("❌ Requête admin invalide : tentative de modification ou injection détectée.")
        return False

    # Vérification que c'est bien une requête SELECT
    if not sql_lower.strip().startswith("select"):
        logger.error("❌ Requête admin invalide : seules les requêtes SELECT sont autorisées.")
        return False

    # Vérification spéciale pour la requête élèves-parents
    if "parenteleve.eleve" in sql_lower and "paiementmotif" in sql_lower:
        # Vérifier que c'est bien la structure attendue
        required_patterns = {
            "from inscriptioneleve,parenteleve,parent,personne pp, personne pe,eleve, classe c, paiementextra pai",
            "where inscriptioneleve.eleve=parenteleve.eleve",
            "and inscriptioneleve.personne=pe.id",
            "and pe.id=eleve.idpersonne",
            "and pai.inscription=inscriptioneleve.id",
            "and parenteleve.eleve=eleve.id",
            "and c.id=inscriptioneleve.classe",
            "and parenteleve.parent=parent.id",
            "and pp.id=parent.personne",
            "and inscriptioneleve.anneescolaire=7"
        }
        
        if not all(p in sql_lower for p in required_patterns):
            logger.error("❌ Requête admin invalide : structure de la requête élèves-parents incorrecte.")
            return False

    return True

def validate_parent_access(sql_query: str, children_ids: List[int]) -> bool:
    """Valide les requêtes pour le rôle parent"""
    if not isinstance(children_ids, list):
        raise TypeError("children_ids doit être une liste")
    if not children_ids:
        return False

    try:
        children_ids_str = [str(int(id)) for id in children_ids]
    except (ValueError, TypeError):
        raise ValueError("Tous les IDs enfants doivent être numériques")

    sql_lower = sql_query.lower().replace("\n", " ").replace("\t", " ")
    sql_lower = re.sub(r'\s+', ' ', sql_lower).strip()

    ids_joined = ",".join(children_ids_str)
    ids_joined_spaced = ", ".join(children_ids_str)

    security_patterns = set([
        f"idpersonne in ({ids_joined})",
        f"idpersonne in({ids_joined})",
        f"idpersonne in ({ids_joined_spaced})",
        f"e.idpersonne in ({ids_joined})",
        f"eleve.idpersonne in ({ids_joined})",
        f"e.idpersonne in({ids_joined})",
        f"eleve.idpersonne in({ids_joined})",
        f"id_personne in ({ids_joined})",
    ])

    # Sous-requêtes
    for child_id in children_ids_str:
        security_patterns.update({
            f"exists(select 1 from eleve where idpersonne = {child_id})",
            f"exists (select 1 from eleve where idpersonne={child_id})",
            f"e.idpersonne in ({child_id})",
        })

    for pattern in security_patterns:
        if pattern in sql_lower:
            break
    else:
        logger.warning("❌ Aucun filtre enfant trouvé dans la requête.")
        return False

    forbidden_patterns = {"--", "/*", "*/", " drop ", " truncate ", " insert ", " update ", " delete "}
    if any(p in sql_lower for p in forbidden_patterns):
        logger.error("❌ Requête parent invalide : tentative de modification ou injection détectée.")
        return False

    return True