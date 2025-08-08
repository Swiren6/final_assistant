from agent.sql_agent import SQLAgent

agent = SQLAgent()
if agent.db:
    print("✅ DB chargée avec succès dans SQLAgent")
else:
    print("❌ DB non initialisée dans SQLAgent")
