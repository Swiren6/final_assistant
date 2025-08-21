# import os, time, logging

# logger = logging.getLogger(__name__)

# def generate_attestation_with_preview(student_name: str, user_id: int) -> tuple[str, str]:
#     """
#     Génère l'attestation PDF + URL pour l'image de prévisualisation
#     Retourne (pdf_url, image_url)
#     """
#     try:
#         # 1. Générer le PDF comme d'habitude
#         timestamp = int(time.time())
#         pdf_filename = f"attestation_{user_id}.pdf"
#         pdf_path = os.path.join('static', 'attestations', pdf_filename)
        
#         # Créer le dossier attestations s'il n'existe pas
#         os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
        
#         # TODO: Votre code de génération PDF existant ici
#         # generate_pdf_content(pdf_path, student_name, ...)
#         # logger.info(f"📄 PDF généré: {pdf_path}")
        
#         # 2. Définir les URLs
#         pdf_url = f"/static/attestations/{pdf_filename}"
        
#         # L'image sera générée à la volée par l'endpoint /static/images/
#         img_filename = pdf_filename.replace('.pdf', '.png')
#         img_url = f"/static/images/{img_filename}"
        
#         # logger.info(f"✅ Attestation générée - PDF: {pdf_url}, Preview: {img_url}")
#         return pdf_url, img_url
        
#     except Exception as e:
#         logger.error(f"❌ Erreur génération attestation: {e}")
#         raise

