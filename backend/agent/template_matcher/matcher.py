from typing import Dict, List, Optional, Tuple, Any
import re

class SemanticTemplateMatcher:
    def __init__(self):
        self.templates = []
    
    def load_templates(self, templates: List[Dict]):
        """Charge les templates"""
        self.templates = templates
        print(f"✅ {len(templates)} templates chargés dans le matcher")
    
    def find_similar_template(self, question: str, threshold: float = 0.6) -> Tuple[Optional[Dict], float]:
        """Trouve un template similaire en utilisant une comparaison simple"""
        if not self.templates:
            return None, 0.0
        
        question_normalized = self._normalize_text(question)
        best_match = None
        best_score = 0.0
        
        for template in self.templates:
            template_text = template.get("template_question", "")
            template_normalized = self._normalize_text(template_text)
            
            # Calcul de similarité basé sur les mots communs
            similarity = self._calculate_similarity(question_normalized, template_normalized)
            
            if similarity > best_score and similarity >= threshold:
                best_score = similarity
                best_match = template
        
        return best_match, best_score
    
    def _normalize_text(self, text: str) -> str:
        """Normalise le texte pour la comparaison"""
        # Supprime les placeholders
        text = re.sub(r'\{[^}]+\}', '', text)
        # Normalise les espaces et la casse
        text = re.sub(r'\s+', ' ', text.lower().strip())
        return text
    
    def _extract_variables(self, question: str, template: Dict) -> Dict[str, Any]:
        """Extrait les variables d'une question basée sur un template"""
        template_text = template["template_question"]
        variables = {}

        # Extraction des années scolaires (format 2023-2024 ou 2023/2024)
        annee_pattern = r"(20\d{2}[-\/]20\d{2})"
        annee_match = re.search(annee_pattern, question)
        if annee_match:
            variables["AnneeScolaire"] = annee_match.group(1).replace("-", "/")
        
        # Extraction des autres variables
        var_names = re.findall(r'\{(.+?)\}', template_text)
        for var_name in var_names:
            if var_name not in variables:  
                keyword_pattern = re.escape(template_text.split(f"{{{var_name}}}")[0].split()[-1])
                pattern = fr"{keyword_pattern}\s+([^\s]+)"
                match = re.search(pattern, question, re.IGNORECASE)
                if match:
                    variables[var_name] = match.group(1).strip(",.?!")
        
        return variables
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calcule la similarité entre deux textes"""
        if not text1 or not text2:
            return 0.0
        
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0