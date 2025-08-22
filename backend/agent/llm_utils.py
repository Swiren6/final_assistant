from openai import OpenAI
import os
import logging

logger = logging.getLogger(__name__)

def ask_llm(prompt: str) -> str:
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("❌ OPENAI_API_KEY non définie dans les variables d'environnement")
            raise ValueError("Clé API OpenAI manquante")
        
        client = OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=2048,
            timeout=100  
        )
        
        result = response.choices[0].message.content
        if not result or result.strip() == "":
            raise ValueError("Réponse vide de l'IA")
            
        return result
        
    except Exception as e:
        error_msg = f"❌ Erreur LLM: {str(e)}"
        logger.error(error_msg)
        print(error_msg)
        
        raise ConnectionError(f"Service IA indisponible: {str(e)}")