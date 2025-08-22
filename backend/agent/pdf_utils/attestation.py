from fpdf import FPDF

from pathlib import Path
import os
import arabic_reshaper
from bidi.algorithm import get_display

from datetime import datetime
from pathlib import Path
import arabic_reshaper
from bidi.algorithm import get_display
import logging
from typing import Dict, Any
import os
# from reportlab.pdfbase import pdfmetrics
# from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)

def export_attestation_pdf(donnees):
    pdf = FPDF()
    pdf.add_page()

    base_path = Path(__file__).parent

    # Police dans: agent/pdf_utils/fonts/Amiri-1.002/
    base_dir = os.path.dirname(__file__)
    font_path = os.path.join(base_dir, 'fonts', 'Amiri', 'Amiri-Regular.ttf')
    # pdfmetrics.registerFont(TTFont('Amiri', font_path))

    pdf.ln(30)

    pdf.set_font("Amiri", 'B', 16)
    pdf.cell(0, 10, "ATTESTATION DE PRÉSENCE", ln=True, align='C')
    pdf.ln(10)

    pdf.set_font("Amiri", '', 14)
    texte_intro = (
        "Je soussignée, Mme Balkis Zrelli, Directrice du Collège et Lycée International School Of Elite, atteste que:\n"
    )
    pdf.multi_cell(0, 10, texte_intro)

    nom = donnees.get('nom_complet') or donnees.get('nom') or 'Nom non précisé'
    pdf.set_font("Amiri", 'B', 16)
    pdf.cell(0, 10, nom.upper(), ln=True, align='C')

    classe = donnees.get('classe', 'Classe non précisée')
    pdf.set_font("Amiri", '', 14)
    texte_avant_classe = "Est inscrit(e) et poursuit régulièrement ses études en "
    texte_apres_classe = " de l'année scolaire 2024/2025\nEn foi de quoi, la présente attestation lui est établie pour servir et valoir ce que de droit.\n"

    pdf.write(8, texte_avant_classe)
    pdf.set_font("Amiri", 'B', 14)
    pdf.write(8, classe)
    pdf.set_font("Amiri", '', 14)
    pdf.write(8, texte_apres_classe)

    pdf.ln(20)
    pdf.cell(0, 10, "Signature & Cachet :", ln=True, align='R')
    pdf.cell(0, 10, "_______________________", ln=True, align='R')

    # Sauvegarde dans static/attestations/
    output_dir = Path("static/attestations")
    output_dir.mkdir(parents=True, exist_ok=True)

    matricule = donnees.get('matricule', '0000')
    filename = f"attestation_presence_{matricule}.pdf"
    chemin = output_dir / filename

    pdf.output(str(chemin))
    return str(chemin)



class PDFGenerator:
    """Générateur d'attestations PDF avec support arabe/français"""
    
    def __init__(self):
        # Chemin exact que vous avez fourni
        self.font_dir = Path(__file__).parent / "fonts"  / "Amiri"
        self.base_dir = Path(__file__).parent.parent.parent  # Racine du projet
        self._validate_fonts()

    def _validate_fonts(self):
        """Vérifie que les polices sont bien installées"""
        required_fonts = {
            "regular": self.font_dir / "Amiri-Regular.ttf",
            "bold": self.font_dir / "Amiri-Bold.ttf"
        }

        for name, path in required_fonts.items():
            if not path.exists():
                raise FileNotFoundError(
                    f"Police manquante: {path}\n"
                    "Solution : Téléchargez les polices Amiri depuis :\n"
                    "https://github.com/khaledhosny/amiri-font/releases\n"
                    "Et copiez-les dans :\n"
                    f"{self.font_dir}"
                )

    def _render_arabic(self, text: str) -> str:
        """Prépare le texte arabe pour l'affichage"""
        try:
            return get_display(arabic_reshaper.reshape(text))
        except Exception as e:
            logger.error(f"Erreur traitement texte arabe : {e}")
            return text

    def generate(self, student_data: Dict[str, Any]) -> Dict[str, Any]:
        """Génère le PDF d'attestation"""
        try:
            pdf = FPDF()
            pdf.add_page()

            # Configuration des polices
            pdf.add_font("Amiri", "", str(self.font_dir / "Amiri-Regular.ttf"), uni=True)
            pdf.add_font("Amiri", "B", str(self.font_dir / "Amiri-Bold.ttf"), uni=True)

            # Contenu du PDF
            self._build_header(pdf)
            self._build_body(pdf, student_data)

            # Sauvegarde
            output_dir = self.base_dir / "static" / "attestations"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            filename = f"attestation_{student_data['matricule']}.pdf"
            output_path = output_dir / filename
            pdf.output(str(output_path))

            return {
                "status": "success",
                "path": str(output_path),
                "filename": filename
            }

        except Exception as e:
            logger.error(f"Erreur génération PDF : {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    def _build_header(self, pdf: FPDF):
        """Construit l'en-tête du document"""
        # Logo (optionnel)
        logo_path = self.base_dir / "assets" / "logo.png"
        if logo_path.exists():
            pdf.image(str(logo_path), x=10, y=10, w=30)

        # Texte arabe
        pdf.set_font("Amiri", "", 14)
        pdf.set_xy(110, 10)
        arabic_text = self._render_arabic(
            "الجمهورية التونسية\nوزارة التربية\nالمندوبية الجهوية للتربية بنابل\nالمدرسة الدولية للنخبة"
        )
        pdf.multi_cell(0, 8, arabic_text, align='R')
        pdf.ln(30)

    def _build_body(self, pdf: FPDF, data: Dict[str, Any]):
        """Construit le corps du document"""
        # Titre
        pdf.set_font("Amiri", 'B', 16)
        pdf.cell(0, 10, "ATTESTATION DE PRÉSENCE", ln=True, align='C')
        pdf.ln(10)

        # Contenu
        pdf.set_font("Amiri", "", 14)
        pdf.multi_cell(0, 10, 
            "Je soussignée, Mme Balkis Zrelli, Directrice de l'établissement, atteste que :"
        )
        pdf.ln(5)

        # Nom élève
        pdf.set_font("Amiri", 'B', 16)
        pdf.cell(0, 10, data['nom_complet'].upper(), ln=True, align='C')
        pdf.ln(5)

        # Détails
        pdf.set_font("Amiri", "", 14)
        pdf.multi_cell(0, 10,
            f"Est inscrit(e) en {data['classe']} pour l'année scolaire 2024/2025.\n\n"
            "En foi de quoi, la présente attestation lui est délivrée."
        )

        # Signature
        pdf.ln(20)
        pdf.cell(0, 10, f"Fait à Nabeul, le {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='L')
        pdf.ln(15)
        pdf.cell(0, 10, "Signature & Cachet :", ln=True, align='R')
        pdf.cell(0, 10, "_______________________", ln=True, align='R')