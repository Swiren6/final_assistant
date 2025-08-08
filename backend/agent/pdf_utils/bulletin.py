from fpdf import FPDF
from datetime import datetime
from pathlib import Path
import arabic_reshaper
from bidi.algorithm import get_display
import logging
from typing import Dict, List, Any, Optional
from config.database import get_db
import os
import MySQLdb.cursors
logger = logging.getLogger(__name__)

class BulletinPDFGenerator:
    """Générateur de bulletins scolaires avec données réelles de la base"""
    
    def __init__(self):
        self.font_dir = Path(r"C:\Users\HP\Desktop\assistant_ISE - Copie\backend\agent\pdf_utils\fonts\Amiri")
        self.output_dir = Path(__file__).parent.parent.parent / "static" / "bulletins"
        self._validate_resources()

    def _validate_resources(self):
        """Vérifie que les ressources nécessaires sont disponibles"""
        if not self.font_dir.exists():
            raise FileNotFoundError(f"Dossier des polices introuvable: {self.font_dir}")

    def _render_arabic(self, text: str) -> str:
        """Traite le texte arabe pour l'affichage"""
        try:
            reshaped_text = arabic_reshaper.reshape(text)
            return get_display(reshaped_text)
        except Exception as e:
            logger.error(f"Erreur rendu arabe: {e}")
            return text

    def get_student_data_from_db(self, student_id: int, trimestre_id: int = 31, annee_scolaire: str = "2024/2025") -> Optional[Dict[str, Any]]:
        """
        Récupère les données complètes d'un élève depuis la base de données
        
        Args:
            student_id: ID de l'élève (ou matricule)
            trimestre_id: ID du trimestre (31=T1, 32=T2, 33=T3)
            annee_scolaire: Année scolaire (format: "2024/2025")
        """
        conn = None
        cursor = None
        
        try:
            conn = get_db()
            cursor = conn.cursor(MySQLdb.cursors.DictCursor)
            
            # ✅ Requête pour récupérer les informations de base de l'élève
            student_query = """
    SELECT 
        p.NomFr, p.PrenomFr,
        e.DateNaissance, e.LieuNaissance, e.AutreLieuNaissance,
        c.CODECLASSEFR as classe, n.NOMNIVAR as niveau,
        e.id as eleve_id, e.IdPersonne as matricule, ie.id as inscription_id
    FROM eleve e
    JOIN personne p ON e.IdPersonne = p.id
    JOIN inscriptioneleve ie ON e.id = ie.Eleve
    JOIN classe c ON ie.Classe = c.id
    JOIN niveau n ON c.IDNIV = n.id
    JOIN anneescolaire a ON ie.AnneeScolaire = a.id
    WHERE e.IdPersonne = %s AND a.AnneeScolaire = %s
    LIMIT 1
"""

            
            cursor.execute(student_query, (student_id, annee_scolaire))
            student_info = cursor.fetchone()
            
            if not student_info:
                logger.error(f"Élève {student_id} non trouvé pour l'année {annee_scolaire}")
                return None
            
            # ✅ Requête pour récupérer les notes par matière
            notes_query = """
            SELECT 
                m.LibelleMatiereCourtFr as matiere,
                m.CoefficientMatiere as coefficient,
                AVG(CAST(erc.Note as DECIMAL(5,2))) as moyenne_matiere,
                COUNT(erc.Note) as nb_notes
            FROM eduresultatcopie erc
            JOIN matiere m ON erc.Matiere = m.id
            JOIN inscriptioneleve ie ON erc.Inscription = ie.id
            JOIN trimestre t ON erc.Trimestre = t.id
            WHERE ie.id = %s 
                AND t.id = %s 
                AND erc.Note IS NOT NULL 
                AND erc.Note != ''
            GROUP BY m.id, m.LibelleMatiereCourtFr, m.CoefficientMatiere
            ORDER BY m.LibelleMatiereCourtFr
            
            """
            
            cursor.execute(notes_query, (student_info['inscription_id'], trimestre_id))
            notes_data = cursor.fetchall()
            
            # ✅ Calcul de la moyenne générale pondérée
            total_points = 0
            total_coefficients = 0
            matieres_formatted = []
            
            for note in notes_data:
                if note['moyenne_matiere'] and note['coefficient']:
                    moyenne = float(note['moyenne_matiere'])
                    coeff = int(note['coefficient'])
                    
                    total_points += moyenne * coeff
                    total_coefficients += coeff
                    
                    # Détermination de l'appréciation
                    if moyenne >= 16:
                        appreciation = "Très bien"
                    elif moyenne >= 14:
                        appreciation = "Bien"
                    elif moyenne >= 12:
                        appreciation = "Assez bien"
                    elif moyenne >= 10:
                        appreciation = "Passable"
                    else:
                        appreciation = "Insuffisant"
                    
                    matieres_formatted.append({
                        "nom": note['matiere'],
                        "coefficient": coeff,
                        "moyenne": round(moyenne, 2),
                        "appreciation": appreciation
                    })
            
            # Moyenne générale
            moyenne_generale = round(total_points / total_coefficients, 2) if total_coefficients > 0 else 0
            
            # ✅ Calcul du rang dans la classe
            rang_query = """
            SELECT COUNT(*) + 1 as rang
            FROM (
                SELECT 
                    ie2.id,
                    SUM(CAST(erc2.Note as DECIMAL(5,2)) * m2.CoefficientMatiere) / SUM(m2.CoefficientMatiere) as moyenne_gen
                FROM inscriptioneleve ie2
                JOIN eduresultatcopie erc2 ON ie2.id = erc2.Inscription
                JOIN matiere m2 ON erc2.Matiere = m2.id
                JOIN trimestre t2 ON erc2.Trimestre = t2.id
                WHERE ie2.Classe = (SELECT Classe FROM inscriptioneleve WHERE id = %s)
                    AND t2.id = %s
                    AND erc2.Note IS NOT NULL 
                    AND erc2.Note != ''
                GROUP BY ie2.id
                HAVING moyenne_gen > %s
            ) as classement
            """
            
            cursor.execute(rang_query, (student_info['inscription_id'], trimestre_id, moyenne_generale))
            rang_result = cursor.fetchone()
            rang = rang_result['rang'] if rang_result else 1
            
            # ✅ Effectif de la classe
            effectif_query = """
            SELECT COUNT(DISTINCT ie.id) as effectif
            FROM inscriptioneleve ie
            JOIN eduresultatcopie erc ON ie.id = erc.Inscription
            JOIN trimestre t ON erc.Trimestre = t.id
            WHERE ie.Classe = (SELECT Classe FROM inscriptioneleve WHERE id = %s)
                AND t.id = %s
            """
            
            cursor.execute(effectif_query, (student_info['inscription_id'], trimestre_id))
            effectif_result = cursor.fetchone()
            effectif = effectif_result['effectif'] if effectif_result else 0
            
            # Détermination de la mention
            if moyenne_generale >= 16:
                mention = "Très Bien"
            elif moyenne_generale >= 14:
                mention = "Bien"
            elif moyenne_generale >= 12:
                mention = "Assez Bien"
            elif moyenne_generale >= 10:
                mention = "Passable"
            else:
                mention = "Insuffisant"
            
            # Période (trimestre)
            trimestre_names = {31: "1er Trimestre", 32: "2ème Trimestre", 33: "3ème Trimestre"}
            periode = f"{trimestre_names.get(trimestre_id, 'Trimestre')} {annee_scolaire}"
            
            return {
                "student_data": {
                    "nom": f"{student_info['NomFr']} {student_info['PrenomFr']}",
                    "matricule": str(student_info['matricule']),
                    "classe": student_info['classe'],
                    "niveau": student_info['niveau'],
                    "periode": periode,
                    "moyenne_generale": moyenne_generale,
                    "rang": f"{rang}ème/{effectif}",
                    "mention": mention,
                    "date_naissance": student_info['DateNaissance'].strftime('%d/%m/%Y') if student_info['DateNaissance'] else "N/A"
                },
                "matieres": matieres_formatted
            }
            
        except Exception as e:
            logger.error(f"Erreur récupération données élève {student_id}: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def generate(self, student_info: Dict[str, Any], matieres: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Génère un bulletin scolaire dynamique
        """
        try:
            pdf = FPDF()
            pdf.add_page()
            
            # Configuration des polices
            self._setup_fonts(pdf)
            
            # En-tête
            self._add_header(pdf, student_info)
            
            # Informations élève
            self._add_student_info(pdf, student_info)
            
            # Tableau des matières
            self._add_grades_table(pdf, matieres)
            
            # Résultats généraux
            self._add_summary(pdf, student_info)
            
            # Sauvegarde
            return self._save_pdf(pdf, student_info["matricule"])
            
        except Exception as e:
            logger.error(f"Erreur génération bulletin: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    def _setup_fonts(self, pdf: FPDF):
        """Configure les polices Amiri"""
        pdf.add_font("Amiri", "", str(self.font_dir / "Amiri-Regular.ttf"), uni=True)
        pdf.add_font("Amiri", "B", str(self.font_dir / "Amiri-Bold.ttf"), uni=True)

    def _add_header(self, pdf: FPDF, student_info: Dict[str, Any]):
        """Ajoute l'en-tête institutionnel"""
        # Logo
        logo_path = Path(__file__).parent.parent.parent / "assets" / "logo_ise.jpeg"
        if logo_path.exists():
            pdf.image(str(logo_path), x=10, y=8, w=30)
        
        # Texte arabe
        pdf.set_font("Amiri", "", 12)
        pdf.set_xy(100, 10)
        institution_ar = self._render_arabic("المدرسة الدولية للنخبة بنابل")
        pdf.cell(0, 8, institution_ar, align="R")
        
        # Texte français
        pdf.set_font("Amiri", "", 10)
        pdf.set_xy(100, 20)
        pdf.cell(0, 6, "École Internationale de l'Élite - Nabeul", align="R")
        
        # Titre principal
        pdf.set_font("Amiri", "B", 18)
        pdf.set_y(45)
        pdf.cell(0, 12, "BULLETIN SCOLAIRE", ln=True, align="C")

    def _add_student_info(self, pdf: FPDF, student_info: Dict[str, Any]):
        """Ajoute les informations de l'élève"""
        pdf.set_font("Amiri", "", 12)
        pdf.set_y(65)
        
        infos = [
            ("Nom et Prénom", student_info["nom"]),
            ("Matricule", student_info["matricule"]),
            ("Classe", student_info["classe"]),
            ("Période", student_info["periode"])
        ]
        
        if "date_naissance" in student_info:
            infos.insert(2, ("Date de naissance", student_info["date_naissance"]))
        
        for label, value in infos:
            pdf.cell(45, 8, f"{label} :", 0, 0)
            pdf.set_font("Amiri", "B", 12)
            pdf.cell(0, 8, str(value), ln=True)
            pdf.set_font("Amiri", "", 12)
        
        pdf.ln(8)

    def _add_grades_table(self, pdf: FPDF, matieres: List[Dict[str, Any]]):
        """Ajoute le tableau des matières et notes"""
        pdf.set_font("Amiri", "B", 11)
        
        # En-tête du tableau
        headers = ["Matière", "Coeff", "Moyenne", "Appréciation"]
        col_widths = [65, 20, 25, 75]
        
        # Ligne d'en-tête avec fond gris
        pdf.set_fill_color(220, 220, 220)
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], 10, header, 1, 0, "C", True)
        pdf.ln()
        
        # Données
        pdf.set_font("Amiri", "", 11)
        pdf.set_fill_color(255, 255, 255)
        
        for i, matiere in enumerate(matieres):
            # Alternance de couleurs pour les lignes
            if i % 2 == 0:
                pdf.set_fill_color(245, 245, 245)
            else:
                pdf.set_fill_color(255, 255, 255)
            
            pdf.cell(col_widths[0], 10, matiere["nom"], 1, 0, "L", True)
            pdf.cell(col_widths[1], 10, str(matiere["coefficient"]), 1, 0, "C", True)
            pdf.cell(col_widths[2], 10, str(matiere["moyenne"]), 1, 0, "C", True)
            pdf.cell(col_widths[3], 10, matiere.get("appreciation", ""), 1, 0, "L", True)
            pdf.ln()
        
        pdf.ln(10)

    def _add_summary(self, pdf: FPDF, student_info: Dict[str, Any]):
        """Ajoute le résumé des résultats"""
        pdf.set_font("Amiri", "B", 14)
        pdf.cell(0, 10, "BILAN GÉNÉRAL", ln=True)
        pdf.ln(5)
        
        stats = [
            ("Moyenne Générale", f"{student_info.get('moyenne_generale', 'N/A')}/20"),
            ("Rang", student_info.get('rang', 'N/A')),
            ("Mention", student_info.get('mention', 'N/A'))
        ]
        
        pdf.set_font("Amiri", "", 12)
        for label, value in stats:
            pdf.cell(50, 8, f"{label} :", 0, 0)
            pdf.set_font("Amiri", "B", 12)
            pdf.cell(0, 8, str(value), ln=True)
            pdf.set_font("Amiri", "", 12)
        
        pdf.ln(15)
        
        # Signature
        pdf.cell(0, 8, f"Fait à Nabeul, le {datetime.now().strftime('%d/%m/%Y')}", ln=True)
        pdf.ln(10)
        pdf.cell(0, 8, "La Directrice", ln=True, align="R")
        pdf.set_font("Amiri", "B", 12)
        pdf.cell(0, 8, "Mme Balkis ZRELLI", ln=True, align="R")

    def _save_pdf(self, pdf: FPDF, matricule: str) -> Dict[str, Any]:
        """Sauvegarde le PDF généré"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"bulletin_{matricule}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        output_path = self.output_dir / filename
        
        pdf.output(str(output_path))
        
        return {
            "status": "success",
            "path": str(output_path),
            "filename": filename
        }


def export_bulletin_pdf(student_id: int, trimestre_id: int = 31, annee_scolaire: str = "2024/2025") -> Dict[str, Any]:
    """
    Interface principale pour générer un bulletin avec données réelles
    
    Args:
        student_id: ID de l'élève (matricule/IdPersonne)
        trimestre_id: ID du trimestre (31=T1, 32=T2, 33=T3)
        annee_scolaire: Année scolaire au format "2024/2025"
    
    Returns:
        Dict avec status, path, filename ou message d'erreur
    """
    try:
        generator = BulletinPDFGenerator()
        
        # ✅ Récupération des données réelles depuis la base
        student_data = generator.get_student_data_from_db(student_id, trimestre_id, annee_scolaire)
        
        if not student_data:
            return {
                "status": "error",
                "message": f"Aucune donnée trouvée pour l'élève {student_id} (Trimestre {trimestre_id}, Année {annee_scolaire})"
            }
        
        # ✅ Génération du PDF avec les vraies données
        result = generator.generate(student_data["student_data"], student_data["matieres"])
        
        if result["status"] == "success":
            logger.info(f"✅ Bulletin généré avec succès pour {student_data['student_data']['nom']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Erreur critique génération bulletin: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Erreur système: {str(e)}"
        }


# ✅ Exemple d'utilisation avec données réelles
if __name__ == "__main__":
    # Test avec un élève réel
    result = export_bulletin_pdf(
        student_id=12345,  # Remplacer par un vrai matricule
        trimestre_id=31,   # 1er trimestre
        annee_scolaire="2024/2025"
    )
    
    if result["status"] == "success":
        print(f"✅ Bulletin généré: {result['filename']}")
        print(f"📁 Chemin: {result['path']}")
    else:
        print(f"❌ Erreur: {result['message']}")