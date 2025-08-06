import os
from dotenv import load_dotenv
from mysql.connector import pooling
from langchain_community.utilities import SQLDatabase  # ✅ Ajout requis

load_dotenv()

config = {
    'user': os.getenv('MYSQL_USER'),
    'password': os.getenv('MYSQL_PASSWORD'),
    'host': os.getenv('MYSQL_HOST'),
    'database': os.getenv('MYSQL_DATABASE'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),
    'charset': 'utf8mb4',
    'use_unicode': True,
    'autocommit': True
}

connection_pool = None

def init_db(app=None):
    global connection_pool
    connection_pool = pooling.MySQLConnectionPool(
        pool_name="mypool",
        pool_size=10,
        pool_reset_session=True,
        **config
    )
    print("✅ Pool de connexions MySQL initialisé")
    return connection_pool

def get_db():
    global connection_pool
    if not connection_pool:
        init_db()
    return connection_pool.get_connection()

class ExtendedSQLDatabase(SQLDatabase):
    def get_schema(self):
        try:
            result = self.run("SHOW TABLES")
            if isinstance(result, str):
                return [line.strip() for line in result.split('\n') if line.strip()]
            return result
        except Exception as e:
            print(f"Erreur get_schema : {e}")
            return []

def get_db_connection():
    db_uri = f"mysql+mysqlconnector://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}"
    return ExtendedSQLDatabase.from_uri(db_uri)
