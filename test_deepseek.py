# test_deepseek.py
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

print("🚀 Chargement du modèle DeepSeek Coder (7B instruct)...")
model_id = "deepseek-ai/deepseek-coder-7b-instruct-v1.5"

tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    trust_remote_code=True,
    device_map="auto",       # utilise "cpu" si pas de GPU
    torch_dtype="auto"
)

llm = pipeline(
    "text-generation",
    model=model,
    tokenizer=tokenizer,
    max_new_tokens=2048,
    temperature=0
)

prompt = """Tu es un assistant SQL. Génère une requête SQL correcte.

Question : Combien d'élèves ont payé par chèque ?
==>"""

print("🧠 DeepSeek génère une réponse...")
response = llm(prompt)[0]["generated_text"]
print("\n🟩 Réponse générée :\n")
print(response)
