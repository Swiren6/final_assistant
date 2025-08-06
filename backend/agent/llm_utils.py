from openai import OpenAI
import os

def ask_llm(prompt: str) -> str:
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        response = client.chat.completions.create(
            model="gpt-4o-mini", 
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=300
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ Erreur LLM: {str(e)}")
        return ""
