# from typing import List

# def is_super_admin(self, roles: List[str]) -> bool:
#         """Vérifie si l'utilisateur est super admin"""
#         admin_roles = ['ROLE_SUPER_ADMIN']
#         return any(role.upper() in admin_roles for role in roles)

# def is_parent(self, roles: List[str]) -> bool:
#         """Vérifie si l'utilisateur est un parent"""
#         return 'ROLE_PARENT' in [role.upper() for role in roles]
    
# def validate_parent_access(self, sql_query: str, children_ids: List[int]) -> bool:
#         # Validation des inputs
#         if not isinstance(children_ids, list):
#             raise TypeError("children_ids doit être une liste")
            
#         if not children_ids:
#             return False
            
#         try:
#             children_ids_str = [str(int(id)) for id in children_ids]
#         except (ValueError, TypeError):
#             raise ValueError("Tous les IDs enfants doivent être numériques")
        
#         # Normalisation plus douce de la requête (garder un espace pour séparer les mots)
#         sql_lower = sql_query.lower().replace("\n", " ").replace("\t", " ")
#         # Normaliser les espaces multiples en un seul
#         import re
#         sql_lower = re.sub(r'\s+', ' ', sql_lower).strip()
        
#         print(f"🔍 SQL normalisé: {sql_lower}")  # Debug
#         print(f"👶 IDs enfants: {children_ids_str}")  # Debug
        
#         # Préparation des motifs de sécurité
#         security_patterns = set()
        
#         # 1. Filtres directs avec plus de variantes
#         if len(children_ids_str) == 1:
#             child_id = children_ids_str[0]
#             security_patterns.update({
#                 f"idpersonne = {child_id}",
#                 f"idpersonne={child_id}",
#                 f"e.idpersonne = {child_id}",
#                 f"e.idpersonne={child_id}",
#                 f"eleve.idpersonne = {child_id}",
#                 f"eleve.idpersonne={child_id}",
#                 f"idpersonne in ({child_id})"
#             })
#         else:
#             ids_joined = ",".join(children_ids_str)
#             ids_joined_spaced = ", ".join(children_ids_str)
#             security_patterns.update({
#                 f"idpersonne in ({ids_joined})",
#                 f"idpersonne in({ids_joined})",
#                 f"idpersonne in ({ids_joined_spaced})",
#                 f"e.idpersonne in ({ids_joined})",
#                 f"e.idpersonne in({ids_joined})",
#                 f"e.idpersonne in ({ids_joined_spaced})",
#                 f"eleve.idpersonne in ({ids_joined})",
#                 f"eleve.idpersonne in({ids_joined})",
#                 f"eleve.idpersonne in ({ids_joined_spaced})",
#                 f"id_personne in ({ids_joined})",
#                 f"id_personne in({ids_joined})",
#                 f"id_personne in ({ids_joined_spaced})"
#             })
        
#         # 2. Sous-requêtes de sécurité (patterns plus complets)
#         for child_id in children_ids_str:
#             security_patterns.update({
#                 f"eleve in (select id from eleve where idpersonne = {child_id}",
#                 f"eleve in (select id from eleve where idpersonne={child_id}",
#                 f"exists (select 1 from eleve where idpersonne = {child_id}",
#                 f"exists (select 1 from eleve where idpersonne={child_id}",
#                 f"exists(select 1 from eleve where idpersonne = {child_id}",
#                 f"exists(select 1 from eleve where idpersonne={child_id}",
#                 f"ed.idenelev IN (SELECT id FROM eleve WHERE IdPersonne IN {child_id})",
#                 f"e.idpersonne in ({child_id})"
#             })
        
#         # Pour les listes d'IDs
#         if len(children_ids_str) > 1:
#             ids_joined = ",".join(children_ids_str)
#             ids_joined_spaced = ", ".join(children_ids_str)
#             security_patterns.update({
#                 f"eleve in (select id from eleve where idpersonne in ({ids_joined})",
#                 f"eleve in (select id from eleve where idpersonne in({ids_joined})",
#                 f"eleve in (select id from eleve where idpersonne in ({ids_joined_spaced})",
#                 f"exists (select 1 from eleve where idpersonne in ({ids_joined})",
#                 f"exists (select 1 from eleve where idpersonne in({ids_joined})",
#                 f"exists (select 1 from eleve where idpersonne in ({ids_joined_spaced})",
#                 f"exists(select 1 from eleve where idpersonne in ({ids_joined})",
#                 f"exists(select 1 from eleve where idpersonne in({ids_joined})",
#                 f"exists(select 1 from eleve where idpersonne in ({ids_joined_spaced})"
#             })
        
#         print(f"🔒 Patterns de sécurité recherchés:")
#         for pattern in sorted(security_patterns):
#             print(f"   - '{pattern}'")
        
#         # 3. Vérification des motifs
#         found_patterns = []
#         for pattern in security_patterns:
#             if pattern in sql_lower:
#                 found_patterns.append(pattern)
        
#         print(f"✅ Patterns trouvés: {found_patterns}")
        
#         if not found_patterns:
#             logger.warning(f"Requête parent non sécurisée - Filtre enfants manquant: {sql_query}")
#             print(f"❌ Aucun pattern de sécurité trouvé dans la requête")
#             return False
        
#         # 4. Vérification des injections potentielles
#         forbidden_patterns = {
#              "--", "/*", "*/", " drop ", " truncate ", " insert ", " update ", " delete "
#         }
#         found_forbidden = [pattern for pattern in forbidden_patterns if pattern in sql_lower]
        
#         if found_forbidden:
#             logger.error(f"Tentative de requête non autorisée détectée: {found_forbidden}")
#             print(f"❌ Patterns interdits trouvés: {found_forbidden}")
#             return False
        
#         print(f"✅ Validation parent réussie")
#         return True




from typing import List
import logging


logger = logging.getLogger(__name__)

def is_super_admin(roles: List[str]) -> bool:
    """Vérifie si l'utilisateur est super admin"""
    return any(role.upper() == 'ROLE_SUPER_ADMIN' for role in roles)

def is_parent(roles: List[str]) -> bool:
    """Vérifie si l'utilisateur est un parent"""
    return 'ROLE_PARENT' in [role.upper() for role in roles]

def validate_parent_access(sql_query: str, children_ids: List[int]) -> bool:
    if not isinstance(children_ids, list):
        raise TypeError("children_ids doit être une liste")
    if not children_ids:
        return False

    try:
        children_ids_str = [str(int(id)) for id in children_ids]
    except (ValueError, TypeError):
        raise ValueError("Tous les IDs enfants doivent être numériques")

    sql_lower = sql_query.lower().replace("\n", " ").replace("\t", " ")
    import re
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