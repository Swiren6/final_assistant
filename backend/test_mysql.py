import MySQLdb

try:
    conn = MySQLdb.connect(
        host="localhost",
        user="root",
        password="root",
        database="bd_eduise2",
        port=3306
    )
    print("✅ Connexion MySQL réussie")
except Exception as e:
    print(f"❌ Échec de connexion: {e}")
