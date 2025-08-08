from flask_mysqldb import MySQL
from langchain_community.utilities import SQLDatabase
import MySQLdb
from urllib.parse import quote_plus
import os
import logging
from dotenv import load_dotenv
from contextlib import contextmanager

load_dotenv()

mysql = MySQL()
logger = logging.getLogger(__name__)

class CustomSQLDatabase(SQLDatabase):
    def execute_query(self, sql_query: str) -> dict:
        try:
            connection = get_db()  
            cursor = connection.cursor()
            cursor.execute(sql_query)

            columns = [desc[0] for desc in cursor.description]
            results = cursor.fetchall()
            data = [dict(zip(columns, row)) for row in results]

            return {"success": True, "data": data}

        except Exception as e:
            logger.error(f"Erreur d'exécution SQL : {e}")
            return {"success": False, "error": str(e), "sql_query": sql_query}

        finally:
            cursor.close()
            # Ne ferme la connexion que si elle a été créée en direct
            if hasattr(connection, '_direct_connection'):
                connection.close()



    def get_schema(self):
        try:
            return self.run("SHOW TABLES")
        except Exception as e:
            logger.error(f"Erreur get_schema: {e}")
            return None

    def get_simplified_relations_text(self):
        try:
            tables = self.run("SHOW TABLES")
            relations = []
            for table in tables:
                table_name = list(table.values())[0]
                relations.append(f"- {table_name}")
            return "\n".join(["Relations entre tables:"] + relations)
        except Exception as e:
            logger.error(f"Erreur get_simplified_relations_text: {e}")
            return ""

    
# ✅ Initialisation de Flask MySQL
def init_db(app):
    try:
        app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST')
        app.config['MYSQL_USER'] = os.getenv('MYSQL_USER')
        app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD')
        app.config['MYSQL_DB'] = os.getenv('MYSQL_DATABASE')
        app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
        app.config['MYSQL_AUTOCOMMIT'] = True
        app.config['MYSQL_CONNECT_TIMEOUT'] = 60

        required_vars = ['MYSQL_HOST', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_DATABASE']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Variables d'environnement manquantes: {missing_vars}")

        mysql.init_app(app)

        test_connection = create_direct_connection()
        if test_connection:
            test_connection.close()
            logger.info("✅ Configuration MySQL initialisée et testée")
        else:
            raise Exception("Impossible de se connecter à MySQL")

        return mysql
    except Exception as e:
        logger.error(f"❌ Erreur init MySQL: {e}")
        raise

# ✅ Connexion directe via MySQLdb
def create_direct_connection():
    try:
        connection = MySQLdb.connect(
            host=os.getenv('MYSQL_HOST'),
            user=os.getenv('MYSQL_USER'),
            passwd=os.getenv('MYSQL_PASSWORD'),
            db=os.getenv('MYSQL_DATABASE'),
            cursorclass=MySQLdb.cursors.DictCursor,
            autocommit=True,
            connect_timeout=10
        )
        connection._direct_connection = True  # Marqueur pour fermeture plus tard
        logger.debug("✅ Connexion MySQL directe créée")
        return connection
    except Exception as e:
        logger.error(f"❌ Erreur connexion MySQL directe: {e}")
        return None

# ✅ Utilisation dans contexte Flask ou fallback direct
def get_db():
    try:
        from flask import current_app
        if current_app and hasattr(current_app, 'extensions') and 'mysql' in current_app.extensions:
            mysql_connection = current_app.extensions['mysql'].connection
            if mysql_connection:
                try:
                    cursor = mysql_connection.cursor()
                    cursor.execute("SELECT 1")
                    cursor.close()
                    logger.debug("✅ Connexion Flask MySQL OK")
                    return mysql_connection
                except Exception as test_error:
                    logger.warning(f"⚠️ Connexion Flask MySQL échouée: {test_error}")
    except Exception as e:
        logger.warning(f"⚠️ Contexte Flask indisponible: {e}")

    logger.info("🔄 Utilisation de la connexion directe")
    return create_direct_connection()

# ✅ Context manager pour les requêtes SQL
@contextmanager
def get_db_cursor():
    connection = None
    cursor = None
    try:
        connection = get_db()
        cursor = connection.cursor(MySQLdb.cursors.DictCursor)  # ✅ Sûr avec MySQLdb
        yield cursor
        connection.commit()
    except Exception as e:
        if connection:
            connection.rollback()
        logger.error(f"❌ Erreur base de données: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection and hasattr(connection, '_direct_connection'):
            connection.close()
            logger.debug("✅ Connexion directe fermée")

# ✅ Intégration LangChain
def get_db_connection():
    try:
        db_user = os.getenv('MYSQL_USER')
        db_password = quote_plus(os.getenv('MYSQL_PASSWORD'))
        db_host = os.getenv('MYSQL_HOST')
        db_name = os.getenv('MYSQL_DATABASE')

        if not all([db_user, db_password, db_host, db_name]):
            raise ValueError("Variables de connexion DB manquantes")

        db_uri = f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}"
        db = CustomSQLDatabase.from_uri(db_uri)
        db.run("SELECT 1")
        logger.info("✅ Connexion LangChain SQLDatabase établie")
        return db

    except Exception as e:
        logger.error(f"❌ Erreur connexion LangChain: {e}")
        return None

def get_schema(self):
    """
    Get database schema information for the SQLAgent
    
    Returns:
        list: List of table names available in the database
    """
    try:
        cursor = self.connection.cursor()
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        cursor.close()
        
        # Extract table names from the result
        table_names = [table[0] for table in tables]
        return table_names
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting schema: {str(e)}")
        return []

def get_simplified_relations_text(self):
    """
    Get simplified foreign key relationships as text for the prompt
    
    Returns:
        str: Text description of table relationships
    """
    try:
        cursor = self.connection.cursor()
        
        # Get foreign key information
        query = """
        SELECT 
            TABLE_NAME,
            COLUMN_NAME,
            REFERENCED_TABLE_NAME,
            REFERENCED_COLUMN_NAME
        FROM 
            INFORMATION_SCHEMA.KEY_COLUMN_USAGE
        WHERE 
            REFERENCED_TABLE_SCHEMA = %s
            AND REFERENCED_TABLE_NAME IS NOT NULL
        """
        
        cursor.execute(query, (self.connection.database,))
        foreign_keys = cursor.fetchall()
        cursor.close()
        
        if not foreign_keys:
            return "Aucune relation de clé étrangère trouvée."
        
        relations_text = "Relations entre les tables :\n"
        for fk in foreign_keys:
            relations_text += f"- {fk[0]}.{fk[1]} → {fk[2]}.{fk[3]}\n"
        
        return relations_text
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting relations: {str(e)}")
        return "Erreur lors de la récupération des relations."