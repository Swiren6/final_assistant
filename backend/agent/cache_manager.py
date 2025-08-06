import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import hashlib
import re
from collections import defaultdict

class CacheManager:
    def __init__(self, cache_file: str = "sql_query_cache.json"):
        self.cache_file = Path(cache_file)
        self.cache = self._load_cache()
        
        # Patterns de base pour les valeurs structurées
        self.auto_patterns = {
            r'\b([A-Z]{3,})\s+([A-Z]{3,})\b': 'NomPrenom',
            r'\b\d+[A-Z]\d+\b': 'CODECLASSEFR', 
            r'\b(20\d{2}[/-]20\d{2})\b': 'AnneeScolaire',
            r'\b\d{1,5}\b': 'IDPersonne' 
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
        self.discovered_patterns = defaultdict(list)

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
    def _extract_parameters(self, text: str) -> Tuple[str, Dict[str, str]]:
        """Détection intelligente des paramètres avec normalisation dynamique"""
        variables = {}
        normalized = text.lower()  # Normaliser en minuscules
        
        # 1. Détection des trimestres
        for term, code in self.trimestre_mapping.items():
            if term in normalized:
                normalized = normalized.replace(term, "{codeperiexam}")
                variables["codeperiexam"] = str(code)
                break
        
        # 2. Détection des noms/prénoms (patterns plus flexibles)
        # Pattern pour "nom prénom" ou "prénom nom"
        name_patterns = [
            r'\b([A-Z][a-zA-Zàâäéèêëïîôöùûüÿç]+)\s+([A-Z][a-zA-Zàâäéèêëïîôöùûüÿç]+)\b',  # Nom Prénom
            r"élève\s+([A-Z][a-zA-Zàâäéèêëïîôöùûüÿç]+)\s+([A-Z][a-zA-Zàâäéèêëïîôöùûüÿç]+)",
            r"de\s+l'élève\s+([A-Z][a-zA-Zàâäéèêëïîôöùûüÿç]+)\s+([A-Z][a-zA-Zàâäéèêëïîôöùûüÿç]+)",
            r"de\s+([A-Z][a-zA-Zàâäéèêëïîôöùûüÿç]+)\s+([A-Z][a-zA-Zàâäéèêëïîôöùûüÿç]+)"
        ]
        
        for pattern in name_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            if matches:
                for match in reversed(matches):
                    nom, prenom = match.groups()
                    full_match = match.group(0)
                    # Remplacer dans le texte original (pas normalisé)
                    normalized = normalized.replace(full_match.lower(), "{nomfr} {prenomfr}")
                    variables.update({
                        "NomFr": nom.capitalize(),
                        "PrenomFr": prenom.capitalize()
                    })
                break
        
        # 3. Détection des codes de classe
        classe_match = re.search(r'\b(\d+[A-Z]\d*)\b', text)
        if classe_match:
            code_classe = classe_match.group(1)
            normalized = normalized.replace(code_classe.lower(), "{codeclassefr}")
            variables["CODECLASSEFR"] = code_classe
        
        # 4. Détection des années scolaires
        annee_match = re.search(r'\b(20\d{2}[/-]20\d{2})\b', text)
        if annee_match:
            annee = annee_match.group(1).replace("-", "/")
            normalized = normalized.replace(annee_match.group(0).lower(), "{anneescolaire}")
            variables["AnneeScolaire"] = annee
        
        # 5. Nettoyage final
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized, variables
    def _normalize_template(self, text: str) -> str:
        """Normalise le texte pour la comparaison"""
        normalized, _ = self._extract_parameters(text)
        # Supprime les espaces multiples et les caractères spéciaux
        normalized = re.sub(r'\s+', ' ', normalized).lower().strip()
        return normalized

    def find_similar_template(self, question: str, threshold: float = 0.8) -> Tuple[Optional[Dict], float]:
        """Trouve un template similaire en utilisant une comparaison simple"""
        """Trouve un template similaire en utilisant TF-IDF et cosine similarity"""
        if not self.cache:
            return None, 0.0
            
        norm_question = self._normalize_template(question)
        best_match = None
        best_score = 0.0
        
        for cache_key, cached_item in self.cache.items():
            norm_template = self._normalize_template(cached_item['question_template'])
            
            # Calcul de similarité simple basé sur les mots communs
            question_words = set(norm_question.split())
            template_words = set(norm_template.split())
            
            if not question_words or not template_words:
                continue
                
            intersection = question_words.intersection(template_words)
            union = question_words.union(template_words)
            
            similarity = len(intersection) / len(union) if union else 0.0
            
            if similarity > best_score and similarity >= threshold:
                best_score = similarity
                best_match = cached_item
        
        return best_match, best_score

    def _generate_cache_key(self, question: str) -> str:
        """Génère une clé basée sur la question normalisée"""
        normalized_question, _ = self._extract_parameters(question)
        return hashlib.md5(normalized_question.encode('utf-8')).hexdigest()

    def _normalize_question(self, question: str) -> Tuple[str, Dict[str, str]]:
        """Alternative à extract_parameters pour compatibilité"""
        return self._extract_parameters(question)

    def _normalize_sql(self, sql: str, variables: Dict[str, str]) -> str:
        """Normalisation SQL avec remplacement dynamique des valeurs"""
        normalized_sql = sql
        
        # Remplacer chaque variable par son placeholder
        for param, value in variables.items():
            # Différents formats possibles de la valeur dans le SQL
            value_variations = [
                f"'{value}'",           # 'Benabda'
                f'"{value}"',           # "Benabda"  
                value,                  # Benabda
                value.upper(),          # BENABDA
                value.lower(),          # benabda
                value.capitalize()      # Benabda
            ]
            
            for variation in value_variations:
                if variation in normalized_sql:
                    normalized_sql = normalized_sql.replace(variation, f"{{{param}}}")
        
        return normalized_sql
    
    def get_cached_query(self, question: str) -> Optional[Tuple[str, Dict[str, str]]]:
        """Récupération depuis le cache avec correspondance flexible"""
        try:
            # 1. Extraire les paramètres de la question actuelle
            normalized_question, current_variables = self._extract_parameters(question)
            
            # 2. Générer la clé et chercher une correspondance exacte
            key = hashlib.md5(normalized_question.encode('utf-8')).hexdigest()
            
            if key in self.cache:
                cached = self.cache[key]
                print(f"💡 Cache hit exact pour: {question}")
                return cached['sql_template'], current_variables
            
            # 3. Si pas de correspondance exacte, chercher une similarité
            for cache_key, cached_item in self.cache.items():
                template_question = cached_item['question_template']
                
                # Comparaison de similarité simple
                if self._questions_similar(normalized_question, template_question):
                    print(f"💡 Cache hit similaire pour: {question}")
                    print(f"   Template trouvé: {template_question}")
                    return cached_item['sql_template'], current_variables
            
            return None
            
        except Exception as e:
            print(f"❌ Erreur get_cached_query: {e}")
            return None

    def _questions_similar(self, q1: str, q2: str, threshold: float = 0.8) -> bool:
        """Compare la similarité entre deux questions normalisées"""
        q1_words = set(q1.split())
        q2_words = set(q2.split())
        
        if not q1_words or not q2_words:
            return False
        
        intersection = q1_words.intersection(q2_words)
        union = q1_words.union(q2_words)
        
        similarity = len(intersection) / len(union)
        return similarity >= threshold
    
    def cache_query(self, question: str, sql_query: str):
        """Mise en cache automatique avec extraction dynamique des paramètres"""
        try:
            # 1. Extraire les paramètres de la question
            norm_question, vars_question = self._extract_parameters(question)
            
            # 2. Normaliser le SQL en remplaçant les valeurs par des placeholders
            norm_sql = self._normalize_sql(sql_query, vars_question)
            
            # 3. Générer la clé de cache
            key = hashlib.md5(norm_question.encode('utf-8')).hexdigest()
            
            # 4. Sauvegarder dans le cache
            self.cache[key] = {
                'question_template': norm_question,
                'sql_template': norm_sql
            }
            
            print(f"💾 Cache ajouté:")
            print(f"   Question: {question}")
            print(f"   Template: {norm_question}")
            print(f"   Variables: {vars_question}")
            print(f"   SQL: {norm_sql}")
            
            self._save_cache()
            
        except Exception as e:
            print(f"❌ Erreur cache_query: {e}")