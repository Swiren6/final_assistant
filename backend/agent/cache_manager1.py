import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import hashlib
import re
from collections import defaultdict
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import logging
from config.database import get_db
import traceback

logger = logging.getLogger(__name__)
class CacheManager1:
    def __init__(self, cache_file: str = "sql_query_cache1.json"):
        self.cache_file = Path(cache_file)
        self.cache = self._load_cache()
        
        # Patterns de base pour les valeurs structurées
        self.auto_patterns = {
            r'\b([A-Z]{3,})\s+([A-Z]{3,})\b': 'NomPrenom',
            r'\b\d+[A-Z]\d+\b': 'CODECLASSEFR', 
            r'\b(20\d{2}[/-]20\d{2})\b': 'AnneeScolaire'
        }
        self.trimestre_mapping = {
            '1er trimestre': 31,
            '1ère trimestre': 31,
            'premier trimestre': 31,
            '2ème trimestre': 32,
            'deuxième trimestre': 32,
            '3ème trimestre': 33,
            '3éme trimestre': 33,
            'troisième trimestre': 33,
            'trimestre 1': 31,
            'trimestre 2': 32,
            'trimestre 3': 33
        }
        self.matiere_patterns = [
            r'\b(mathématiques?|maths?)\b',
            r'\b(français|francais)\b',
            r'\b(anglais)\b',
            r'\b(espagnol)\b',
            r'\b(allemand)\b',
            r'\b(italien)\b',
            r'\b(histoire|hist)\b',
            r'\b(géographie|geographie|géo|geo)\b',
            r'\b(sciences?)\b',
            r'\b(physique|pysique)\b',
            r'\b(chimie)\b',
            r'\b(biologie|bio)\b',
            r'\b(svt)\b',
            r'\b(eps|sport)\b',
            r'\b(technologie|techno)\b',
            r'\b(informatique|info)\b',
            r'\b(philosophie|philo)\b',
            r'\b(arts?\s+plastiques?)\b',
            r'\b(musique)\b',
            r'\b(éducation\s+musicale)\b',
            r'\b(économie)\b'
        ]
        
        # Patterns pour les types d'évaluations
        self.evaluation_patterns = [
            r'\b(devoir\s+(?:de\s+)?contrôle?\s*\d*)\b',
            r'\b(devoir\s+(?:de\s+)?controle?\s*\d*)\b',
            r'\b(devoir\s+(?:du\s+)?controle?\s*\d*)\b',
            r'\b(contrôle?\s*\d*)\b', 
            r'\b(devoir\s+surveillé\s*\d*)\b',
            r'\b(ds\s*\d*)\b',
            r'\b(dc1\s*\d*)\b',
            r'\b(dc2\s*\d*)\b',
            r'\b(DC1\s*\d*)\b',
            r'\b(DC2\s*\d*)\b',
            r'\b(dc\s*\d*)\b',
            r'\b(devoir\s+maison\s*\d*)\b',
            r'\b(dm\s*\d*)\b',
            r'\b(examen\s*\d*)\b',
            r'\b(bac\s+blanc)\b',
            r'\b(brevet\s+blanc)\b',
            r'\b(composition\s*\d*)\b',
            r'\b(évaluation\s*\d*)\b',
            r'\b(evaluation\s*\d*)\b'
        ]

        self.jour_mapping = {
            'lundi': 1,
            'mardi': 2,
            'mercredi': 3,
            'jeudi': 4,
            'vendredi': 5,
            'samedi': 6,
            'dimanche': 7,
            'aujourd\'hui': 'CURRENT_DATE',  # Cas spécial pour aujourd'hui
            'demain': 'DATE_ADD(CURRENT_DATE, INTERVAL 1 DAY)',
            'hier': 'DATE_SUB(CURRENT_DATE, INTERVAL 1 DAY)'
        }
        
        # Patterns pour détecter les jours
        self.jour_patterns = [
            r'\b(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)\b',
            r'\b(aujourd\'hui|aujourdhui)\b',
            r'\b(demain)\b',
            r'\b(hier)\b',
            r'\b(jour)\b'  # Pour les questions génériques sur les jours
        ]
        self.discovered_patterns = defaultdict(list)
            
            # Initialisation du vectorizer TF-IDF
        self.vectorizer = TfidfVectorizer()
        self.template_vectors = None
        self._init_similarity_search()

    def _init_similarity_search(self):
        """Initialise le système de recherche de similarité"""
        if self.cache:
            templates = [self._normalize_template(item['question_template']) 
                        for item in self.cache.values()]
            self.vectorizer.fit(templates)
            self.template_vectors = self.vectorizer.transform(templates)

    def _load_cache(self) -> Dict[str, Any]:
        if not self.cache_file.exists():
            return {}
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_cache(self):
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, indent=2, ensure_ascii=False)
        self._init_similarity_search()  # Recharge les vecteurs après sauvegarde

    def _extract_family_references(self, question: str) -> Dict[str, str]:
        """Détecte les références familiales et les normalise"""
        family_patterns = {
            r'\b(?:mon|ma|mes)\s+(enfant|fille|fils|enfants|enfnt|fill|fil|garçon|garcon|file)\b': 'id_personne',
            r'\b(?:de|du|d\')\s*(?:mon|ma|mes)\s+(enfant|fille|fils|enfants)\b': 'id_personne',
            r'\bmon\s+enfant\b': 'id_personne',
            r'\bma\s+fille\b': 'id_personne', 
            r'\bmon\s+fils\b': 'id_personne',
            r'\bmes\s+enfants\b': 'id_personne'
        }
        
        family_refs = {}
        normalized_question = question.lower()
        
        for pattern, placeholder in family_patterns.items():
            if re.search(pattern, normalized_question, re.IGNORECASE):
                family_refs['family_relation'] = placeholder
                break
        
        return family_refs
    
    def _is_context_sensitive_number(self, text: str, match_pos: int, number: str) -> bool:
        """
        Détermine si un nombre doit être considéré comme un paramètre ou laissé tel quel
        en fonction du contexte
        """
        # Récupérer le contexte autour du nombre (20 caractères avant et après)
        start = max(0, match_pos - 20)
        end = min(len(text), match_pos + len(number) + 20)
        context = text[start:end].lower()
        
        # Mots qui indiquent que le nombre ne doit PAS être paramétrisé
        non_param_contexts = [
            'chapitre', 'leçon', 'lecon', 'cours', 'exercice', 'activité', 'activite',
            'séance', 'seance', 'session', 'partie', 'niveau', 'étape', 'etape',
            'numéro', 'numero', 'n°', 'no', '#'
        ]
        
        # Vérifier si le contexte contient des mots qui suggèrent que le nombre 
        # fait partie d'une désignation (devoir 1, controle 2, etc.)
        for keyword in non_param_contexts:
            if keyword in context:
                # Vérifier la proximité du mot-clé avec le nombre
                keyword_pos = context.find(keyword)
                number_pos_in_context = context.find(number.lower())
                
                # Si le mot-clé est proche du nombre (moins de 10 caractères)
                if abs(keyword_pos - number_pos_in_context) < 10:
                    return False
        
        # Si le nombre est isolé ou dans un contexte qui suggère un ID
        # (ex: "pour l'élève 12345", "ID 123")
        id_contexts = ['élève', 'eleve', 'étudiant', 'etudiant', 'id', 'identifiant']
        for keyword in id_contexts:
            if keyword in context:
                return True
                
        # Les nombres de 3 chiffres ou plus sont probablement des IDs
        if len(number) >= 3 and number.isdigit():
            return True
            
        # Par défaut, ne pas paramétrer les petits nombres (1-2 chiffres)
        return False

    def _normalize_evaluation_type(self, evaluation_text: str) -> str:
        """Normalise les types d'évaluations pour une meilleure correspondance"""
        evaluation_lower = evaluation_text.lower().strip()
        
        # Mapping des variantes vers des formes standardisées
        normalization_map = {
            # Contrôles
            'controle': 'contrôle',
            'contrôle': 'contrôle',
            'devoir de controle': 'devoir de contrôle',
            'devoir de contrôle': 'devoir de contrôle',
            
            # Devoirs surveillés
            'devoir surveille': 'devoir surveillé',
            'devoir surveillé': 'devoir surveillé',
            'ds': 'devoir surveillé',
            
            # Devoirs maison
            'devoir maison': 'devoir maison',
            'dm': 'devoir maison',
            
            # Interrogations
            'interrogation': 'interrogation',
            'interro': 'interrogation',
            
            # Évaluations
            'evaluation': 'évaluation',
            'évaluation': 'évaluation',
            
            # Tests et quiz
            'test': 'test',
            'quiz': 'quiz',
            
            # Examens
            'examen': 'examen',
            'bac blanc': 'bac blanc',
            'brevet blanc': 'brevet blanc',
            
            # Compositions
            'composition': 'composition'
        }
        
        # Essayer de trouver une correspondance exacte d'abord
        if evaluation_lower in normalization_map:
            return normalization_map[evaluation_lower]
        
        # Essayer de trouver une correspondance partielle
        for key, normalized in normalization_map.items():
            if key in evaluation_lower or evaluation_lower in key:
                return normalized
        
        # Si aucune correspondance trouvée, retourner tel quel
        return evaluation_text.lower()
    def _normalize_sql_for_family(self, sql_query: str, children_ids: List[int]) -> str:
        """Normalise le SQL en remplaçant les IDs enfants par des placeholders"""
        normalized_sql = sql_query
        
        if not children_ids:
            return normalized_sql
        
        # Convertir les IDs en strings pour les remplacements
        children_ids_str = [str(id) for id in children_ids]
        
        # Patterns pour remplacer les IDs spécifiques par des variables
        patterns_to_replace = [
            # WHERE clauses avec IdPersonne (un seul ID)
            (rf"\b(IdPersonne|e\.IdPersonne|eleve\.IdPersonne)\s*=\s*({'|'.join(children_ids_str)})\b", 
            r'\1 = {id_personne}'),
            
            # WHERE clauses avec IN (un seul ID)
            (rf"\b(IdPersonne|e\.IdPersonne|eleve\.IdPersonne)\s+IN\s*\(\s*({'|'.join(children_ids_str)})\s*\)", 
            r'\1 IN ({id_personne})'),
            
            # WHERE clauses avec IN (plusieurs IDs)
            (rf"\b(IdPersonne|e\.IdPersonne|eleve\.IdPersonne)\s+IN\s*\(\s*({',\s*'.join(children_ids_str)})\s*\)", 
            r'\1 IN ({id_personne})'),
        ]
        
        for pattern, replacement in patterns_to_replace:
            normalized_sql = re.sub(pattern, replacement, normalized_sql, flags=re.IGNORECASE)
        
        return normalized_sql
    
    def _extract_parameters(self, text: str) -> Tuple[str, Dict[str, str]]:
        """Détection intelligente des paramètres - VERSION CORRIGÉE"""
        variables = {}
        normalized = text

        # 1. Gérer d'abord les références familiales
        family_refs = self._extract_family_references(text)
        if family_refs:
            # Remplacer toutes les références familiales par un placeholder uniforme
            family_patterns = [
                r'\b(?:mon|ma|mes)\s+(?:enfant|fille|fils|enfants)\b',
                r'\b(?:de|du|d\')\s*(?:mon|ma|mes)\s+(?:enfant|fille|fils|enfants)\b'
            ]
            
            for pattern in family_patterns:
                normalized = re.sub(pattern, '{family_relation}', normalized, flags=re.IGNORECASE)
            
            variables['id_personne'] = family_refs['family_relation']

        # 2. Gérer les matières scolaires
        for pattern in self.matiere_patterns:
            match = re.search(pattern, normalized, re.IGNORECASE)
            if match:
                matiere_found = match.group(0)
                normalized = re.sub(pattern, '{matiere}', normalized, flags=re.IGNORECASE)
                variables['matiere'] = matiere_found.lower()
                break  

        # 3. Gérer les types d'évaluations
        for pattern in self.evaluation_patterns:
            match = re.search(pattern, normalized, re.IGNORECASE)
            if match:
                evaluation_found = match.group(0)
                # Normaliser les variantes (controle -> contrôle, etc.)
                evaluation_normalized = self._normalize_evaluation_type(evaluation_found)
                normalized = re.sub(pattern, '{type_evaluation}', normalized, flags=re.IGNORECASE)
                variables['type_evaluation'] = evaluation_normalized
                break  

        # 4. Gérer les trimestres
        for term, code in self.trimestre_mapping.items():
            if term in normalized.lower():
                normalized = normalized.replace(term, "{codeperiexam}")
                variables["codeperiexam"] = str(code)
                break

        # 5. Détecter les motifs connus (sans le pattern IDPersonne générique)
        for pattern, param_type in self.auto_patterns.items():
            matches = list(re.finditer(pattern, normalized))
            for match in reversed(matches):  # Traiter de droite à gauche
                full_match = match.group(0)
                
                if param_type == 'NomPrenom':
                    nom, prenom = match.groups()
                    normalized = normalized.replace(full_match, "{NomFr} {PrenomFr}")
                    variables.update({"NomFr": nom, "PrenomFr": prenom})
                else:
                    value = match.group(1) if len(match.groups()) > 0 else full_match
                    normalized = normalized.replace(full_match, f"{{{param_type}}}")
                    variables[param_type] = value

        for pattern in self.jour_patterns:
            match = re.search(pattern, normalized, re.IGNORECASE)
            if match:
                jour_found = match.group(1).lower()
                if jour_found in self.jour_mapping:
                    normalized = re.sub(pattern, '{jour}', normalized, flags=re.IGNORECASE)
                    #variables['jour'] = str(self.jour_mapping[jour_found])
                    variables['jour'] = jour_found.capitalize()
                    break

        # 6. Gestion intelligente des nombres isolés 
        number_pattern = r'\b(\d{4,})\b'  
        matches = list(re.finditer(number_pattern, normalized))
        
        for match in reversed(matches):
            number = match.group(1)
            match_pos = match.start()
            
            # Utiliser la fonction de contexte pour décider
            if self._is_context_sensitive_number(normalized, match_pos, number):
                # C'est probablement un ID, le paramétrer
                normalized = normalized.replace(number, '{IDPersonne}')
                variables['IDPersonne'] = number

        # 7. Détection des valeurs entre quotes
        quoted_values = re.findall(r"['\"]([^'\"]+)['\"]", normalized)
        for val in quoted_values:
            if val not in variables.values():  
                if val.isupper() and len(val.split()) == 1:
                    param_name = "NomFr" if "nom" in normalized.lower() else "Valeur"
                    normalized = normalized.replace(f"'{val}'", f"'{{{param_name}}}'")
                    variables[param_name] = val

        return normalized, variables

    def _normalize_template(self, text: str) -> str:
        """Normalise le texte pour la comparaison de similarité"""
        normalized, _ = self._extract_parameters(text)
        # Supprime les espaces multiples et les caractères spéciaux
        normalized = re.sub(r'\s+', ' ', normalized).lower().strip()
        return normalized

    def find_similar_template(self, question: str, threshold: float = 0.85) -> Tuple[Optional[Dict], float]:
        """Trouve un template similaire en utilisant TF-IDF et cosine similarity"""
        if not self.cache:
            return None, 0.0
            
        norm_question = self._normalize_template(question)
        
        try:
            question_vec = self.vectorizer.transform([norm_question])
            similarities = cosine_similarity(question_vec, self.template_vectors)[0]
            best_idx = np.argmax(similarities)
            best_score = similarities[best_idx]
            
            if best_score >= threshold:
                cache_key = list(self.cache.keys())[best_idx]
                return self.cache[cache_key], best_score
        except Exception as e:
            print(f"⚠️ Erreur lors de la recherche de template similaire: {str(e)}")
        
        return None, 0.0

    def _generate_cache_key(self, question: str) -> str:
        """Génère une clé basée sur la question normalisée"""
        normalized_question, _ = self._extract_parameters(question)
        return hashlib.md5(normalized_question.encode('utf-8')).hexdigest()

    def _normalize_question(self, question: str) -> Tuple[str, Dict[str, str]]:
        """Alternative à extract_parameters pour compatibilité"""
        return self._extract_parameters(question)


    def _normalize_sql(self, sql: str, variables: Dict[str, str]) -> str:
        """Normalisation SQL avancée avec gestion des matières et évaluations"""
        normalized_sql = sql
        
        # 1. Remplacer les IDs fixes par des placeholders
        normalized_sql = re.sub(
            r'(IdPersonne|e\.IdPersonne|eleve\.IdPersonne)\s+IN\s*\(\s*\d+\s*\)',
            r'\1 IN ({id_personne})',
            normalized_sql,
            flags=re.IGNORECASE
        )
        
        # 2. Gérer les années scolaires
        if "AnneeScolaire" in variables:
            value = variables["AnneeScolaire"]
            for fmt in [value, f"'{value}'", f'"{value}"']:
                normalized_sql = normalized_sql.replace(fmt, "{AnneeScolaire}")
        
        # 3. Gérer les codes période d'examen
        if "codeperiexam" in variables:
            code = variables["codeperiexam"]
            normalized_sql = re.sub(r'codeperiexam\s*=\s*\d+', f'codeperiexam = {{codeperiexam}}', normalized_sql)
            normalized_sql = re.sub(r"'?\d+'?\s*=\s*codeperiexam", f'{{codeperiexam}} = codeperiexam', normalized_sql)
            # Remplacer aussi les valeurs directes
            normalized_sql = normalized_sql.replace(f'= {code}', '= {codeperiexam}')
            normalized_sql = normalized_sql.replace(f"= '{code}'", "= '{codeperiexam}'")
        
        # 4. Gérer les matières dans les requêtes SQL
        if "matiere" in variables:
            matiere_value = variables["matiere"]
            
            # Patterns pour détecter les matières dans les requêtes SQL
            matiere_patterns = [
                # Pattern pour NomMatiereFr = 'Matiere'
                rf"NomMatiereFr\s*=\s*'([^']*{re.escape(matiere_value)}[^']*)'",
                rf"NomMatiereFr\s*=\s*\"([^\"]*{re.escape(matiere_value)}[^\"]*)\""
            ]
            
            for pattern in matiere_patterns:
                matches = re.finditer(pattern, normalized_sql, re.IGNORECASE)
                for match in matches:
                    full_match = match.group(0)
                    # Remplacer par le placeholder
                    replacement = re.sub(r"'[^']*'", "'{matiere}'", full_match)
                    replacement = re.sub(r'"[^"]*"', '"{matiere}"', replacement)
                    normalized_sql = normalized_sql.replace(full_match, replacement)
        
        if "type_evaluation" in variables:
            evaluation_value = variables["type_evaluation"]
            
            # Détecter les colonnes qui correspondent aux types d'évaluation
            column_patterns = [
                r'SELECT\s+`([a-zA-Z]+\d*)`\s+FROM',
                r'SELECT\s+([a-zA-Z]+\d*)\s+FROM',
                r'`([a-zA-Z]+\d*)`\s*,',
                r'([a-zA-Z]+\d*)\s*,'
            ]
            
            for pattern in column_patterns:
                matches = re.finditer(pattern, normalized_sql, re.IGNORECASE)
                for match in matches:
                    column_name = match.group(1)
                    # Vérifier si la colonne semble correspondre au type d'évaluation
                    is_eval_col, real_col_name = self._is_evaluation_column(column_name, evaluation_value)
                    if is_eval_col:
                        # Stocker le nom réel de la colonne dans les variables
                        variables['type_evaluation'] = real_col_name
                        # Ne pas remplacer dans le SQL, garder le nom réel
            if "jour" in variables:
                jour_value = variables["jour"]
                
                # Cas spéciaux (aujourd'hui, demain, hier)
                if jour_value.lower() in ['aujourd\'hui', 'aujourdhui', 'demain', 'hier']:
                    normalized_sql = re.sub(
                        r'(WHERE|AND|OR)\s+.*jour.*=.*',
                        r'\1 jour = {jour}',
                        normalized_sql,
                        flags=re.IGNORECASE
                    )
                else:
                    # Remplace les cas avec quotes manquantes
                    normalized_sql = re.sub(
                        r"libelleJourFr\s*=\s*([A-Za-zéèêëàâîïôöûüç]+)",
                        "libelleJourFr = '{jour}'",
                        normalized_sql,
                        flags=re.IGNORECASE
                    )
                    # Remplace les cas avec quotes existantes
                    normalized_sql = re.sub(
                        r"libelleJourFr\s*=\s*'[^']+'",
                        "libelleJourFr = '{jour}'",
                        normalized_sql,
                        flags=re.IGNORECASE
                    )
        # 6. Protection des mots-clés SQL pendant le remplacement général
        keywords = ['SELECT', 'FROM', 'WHERE', 'JOIN', 'AND', 'OR', 'IN', 'ON']
        protected = []
        
        def protect(match):
            protected.append(match.group(0))
            return f"__PROTECTED_{len(protected)-1}__"
        
        # Protéger les mots-clés
        for keyword in keywords:
            normalized_sql = re.sub(rf'\b{keyword}\b', protect, normalized_sql, flags=re.IGNORECASE)
        
        # 7. Remplacement général des valeurs par des placeholders
        for param, value in variables.items():
            if param not in ['matiere', 'type_evaluation']:  # Déjà traités ci-dessus
                for fmt in [f"'{value}'", f'"{value}"', str(value)]:
                    if fmt in normalized_sql and len(fmt) > 2:  # Éviter les remplacements trop courts
                        normalized_sql = normalized_sql.replace(fmt, f"{{{param}}}")
        
        # 8. Restaurer les mots-clés protégés
        for i, kw in enumerate(protected):
            normalized_sql = normalized_sql.replace(f'__PROTECTED_{i}__', kw)
            
        return normalized_sql

    def _is_evaluation_column(self, column_name: str, evaluation_type: str) -> bool:
        column_lower = column_name.lower()
        eval_lower = evaluation_type.lower()
        
        evaluation_column_map = {
            'devoir de contrôle': ['dc1', 'controle', 'control'],
            'devoir de controle': ['dc1', 'controle', 'control'],
            'devoir de controle 1': ['dc1','DC1'],
            'devoir de controle 2': ['dc2','DC2'],
            'contrôle': ['dc', 'controle', 'control'],
            'controle': ['dc', 'controle', 'control'],
            'devoir surveillé': ['ds', 'devoir_surveille'],
            'devoir surveille': ['ds', 'devoir_surveille'],
            'devoir maison': ['dm', 'devoir_maison'],
            'examen': ['exam', 'examen'],
            'composition': ['compo', 'composition']
        }
        
        for eval_type, prefixes in evaluation_column_map.items():
            if eval_type in eval_lower:
                for prefix in prefixes:
                    if column_lower.startswith(prefix):
                        return True, column_name  # Retourne le nom réel de la colonne
        
        return False, ""

    def _has_family_reference(self, question: str) -> bool:
        """Vérifie si la question contient des références familiales"""
        family_keywords = [
            'mon fils', 'ma fille', 'mon enfant', 'mes enfants',
            'de mon fils', 'de ma fille', 'de mon enfant', 'de mes enfants',
            'fils', 'fille', 'enfant', 'enfants'
        ]
        
        question_lower = question.lower()
        return any(keyword in question_lower for keyword in family_keywords)

    def get_user_children_ids(self, user_id: int) -> List[int]:
        """Récupère les IDs des enfants d'un parent avec gestion robuste des connexions"""
        connection = None
        cursor = None
        children_ids = []

        try:
            query = """
            SELECT DISTINCT pe.id AS id_enfant
            FROM personne p
            JOIN parent pa ON p.id = pa.Personne
            JOIN parenteleve pev ON pa.id = pev.Parent
            JOIN eleve e ON pev.Eleve = e.id
            JOIN personne pe ON e.IdPersonne = pe.id
            WHERE p.id = %s
            """
            
            # Get connection
            connection = get_db()
            cursor = connection.cursor()
            
            # Execute query
            cursor.execute(query, (user_id,))
            users = cursor.fetchall()
            
            # Process results
            if users:
                children_ids = [user['id_enfant'] for user in users]
                logger.info(f"✅ Found {len(children_ids)} children for parent {user_id}")
            
            return children_ids
        except Exception as e:
            logger.error(f"❌ Error getting children for parent {user_id}: {str(e)}")
            logger.error(traceback.format_exc())
            return []
        finally:
            # Only close if we created a direct connection
            try:
                if cursor:
                    cursor.close()
                
                # Check if this is a Flask-managed connection
                from flask import current_app
                is_flask_connection = current_app and hasattr(current_app, 'extensions') and 'mysql' in current_app.extensions and connection == current_app.extensions['mysql'].connection
                
                if connection and not is_flask_connection:
                    connection.close()
                    logger.debug("🔌 Closed direct MySQL connection")
            except Exception as close_error:
                logger.warning(f"⚠️ Error during cleanup: {str(close_error)}")


    def cache_query(self, question: str, sql_query: str):
        """Version finale de mise en cache avec vérification des références familiales"""
        if not self._has_family_reference(question):
            print("⚠️ Question non mise en cache car elle ne contient pas de référence familiale")
            return
            
        norm_question, vars_question = self._extract_parameters(question)
        norm_sql = self._normalize_sql(sql_query, vars_question)
        
        key = hashlib.md5(norm_question.encode()).hexdigest()
        self.cache[key] = {
            'question_template': norm_question,
            'sql_template': norm_sql
        }
        self._save_cache()

    def get_cached_query(self, question: str, current_user_id: int) -> Optional[Tuple[str, Dict[str, str]]]:
        """Version modifiée qui gère le remplacement direct de l'ID enfant dans le SQL"""
        
        normalized_question, variables = self._extract_parameters(question)
        key = self._generate_cache_key(normalized_question)
        
        if key in self.cache:
            cached = self.cache[key]
            sql_template = cached['sql_template']
            
            # Remplacer directement {id_personne} ou {{id_personne}} dans le SQL par les vrais IDs
            if '{id_personne}' in sql_template or '{{id_personne}}' in sql_template:
                children_ids = self.get_user_children_ids(current_user_id)
                if children_ids:
                    # Construire la valeur de remplacement selon le contexte
                    if len(children_ids) == 1:
                        id_replacement = str(children_ids[0])
                    else:
                        id_replacement = ','.join(str(id) for id in children_ids)
                    
                    # Remplacer les deux formats possibles
                    sql_template = sql_template.replace('{{id_personne}}', id_replacement)
                    sql_template = sql_template.replace('{id_personne}', id_replacement)
            # Dans get_cached_query, après avoir géré id_personne
            if '{type_evaluation_column}' in sql_template:
                sql_template = sql_template.replace('{type_evaluation_column}', variables['type_evaluation_column'])
            # Gérer les autres variables normalement
            current_vars = {}
            for param in re.findall(r'\{(\w+)\}', sql_template):
                if param in variables:
                    current_vars[param] = variables[param]
            if 'jour' in current_vars:
                if current_vars['jour'].lower() in ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']:
                    current_vars['jour'] = f"'{current_vars['jour']}'"
            return sql_template, current_vars
        
        # Si pas de correspondance exacte, chercher un template similaire
        similar_template, score = self.find_similar_template(question)
        if similar_template:
            print(f"🔍 Template similaire trouvé (score: {score:.2f})")
            sql_template = similar_template['sql_template']
            
            # Remplacer directement {id_personne} ou {{id_personne}} dans le SQL par les vrais IDs
            if '{id_personne}' in sql_template or '{{id_personne}}' in sql_template:
                children_ids = self.get_user_children_ids(current_user_id)
                if children_ids:
                    # Construire la valeur de remplacement selon le contexte
                    if len(children_ids) == 1:
                        id_replacement = str(children_ids[0])
                    else:
                        id_replacement = ','.join(str(id) for id in children_ids)
                    
                    # Remplacer les deux formats possibles
                    sql_template = sql_template.replace('{{id_personne}}', id_replacement)
                    sql_template = sql_template.replace('{id_personne}', id_replacement)
            
            if '{type_evaluation_column}' in sql_template:
                sql_template = sql_template.replace('{type_evaluation_column}', variables['type_evaluation_column'])
            # Gérer les autres variables
            current_vars = {}
            for param in re.findall(r'\{(\w+)\}', sql_template):
                if param in variables:
                    current_vars[param] = variables[param]
                else:
                    # Essaye de trouver une valeur correspondante dans la question
                    for pattern in self.auto_patterns:
                        match = re.search(pattern, question)
                        if match:
                            value = match.group(1) if len(match.groups()) > 0 else match.group(0)
                            current_vars[param] = value
                            break
            if 'jour' in current_vars:
                if current_vars['jour'].lower() in ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']:
                    current_vars['jour'] = f"'{current_vars['jour']}'"
            return sql_template, current_vars
        
        return None
        
    def clean_double_braces_in_cache(self):

        """Nettoie le cache en remplaçant {{id_personne}} par {id_personne}"""
        updated = False
        
        for key, item in self.cache.items():
            sql_template = item.get("sql_template", "")
            if "{{id_personne}}" in sql_template:
                # Remplacer les doubles accolades par des simples
                item["sql_template"] = sql_template.replace("{{id_personne}}", "{id_personne}")
                updated = True
                logger.info(f"✅ Nettoyé les doubles accolades dans le template: {key}")
        
        if updated:
            self._save_cache()
            logger.info("✅ Cache nettoyé et sauvegardé")
        else:
            logger.info("ℹ️ Aucune double accolade trouvée dans le cache")


