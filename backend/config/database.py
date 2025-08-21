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

    def get_table_info(self, table_names=None):
        """
        Récupère les informations des tables de la base de données
        
        Args:
            table_names (list, optional): Liste des noms de tables spécifiques. 
                                        Si None, récupère toutes les tables.
        
        Returns:
            str: Description des tables au format texte
        """
        try:
            if table_names is None:
                # Récupérer toutes les tables
                tables_result = self.run("SHOW TABLES")
                table_names = [list(table.values())[0] for table in tables_result]
            
            table_info = []
            for table_name in table_names:
                try:
                    # Récupérer la structure de la table
                    columns_result = self.run(f"DESCRIBE {table_name}")
                    columns_info = []
                    for column in columns_result:
                        col_name = column.get('Field', '')
                        col_type = column.get('Type', '')
                        col_null = column.get('Null', '')
                        col_key = column.get('Key', '')
                        col_default = column.get('Default', '')
                        
                        column_desc = f"  - {col_name} ({col_type})"
                        if col_null == 'NO':
                            column_desc += " NOT NULL"
                        if col_key == 'PRI':
                            column_desc += " PRIMARY KEY"
                        if col_default:
                            column_desc += f" DEFAULT {col_default}"
                        
                        columns_info.append(column_desc)
                    
                    table_info.append(f"Table: {table_name}\n" + "\n".join(columns_info))
                    
                except Exception as e:
                    logger.warning(f"Impossible de récupérer les infos pour la table {table_name}: {e}")
                    continue
            
            return "\n\n".join(table_info) if table_info else "Aucune table trouvée"
            
        except Exception as e:
            logger.error(f"Erreur get_table_info: {e}")
            return f"Erreur lors de la récupération des informations des tables: {str(e)}"

    
# ✅ Initialisation de Flask MySQL
def init_db(app):
    try:
        # Configuration de base pour Flask-MySQLdb (optionnel)
        app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST', 'localhost')
        app.config['MYSQL_USER'] = os.getenv('MYSQL_USER', 'root')
        app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD', 'infosef')
        app.config['MYSQL_DB'] = os.getenv('MYSQL_DATABASE', 'bd_eduise')
        app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
        app.config['MYSQL_AUTOCOMMIT'] = True
        app.config['MYSQL_CONNECT_TIMEOUT'] = 60
        app.config['MYSQL_CHARSET'] = 'latin1'
        
        # Vérification des variables critiques
        required_vars = ['MYSQL_HOST', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_DATABASE']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            logger.warning(f"⚠️ Variables manquantes: {missing_vars} - Utilisation des valeurs par défaut")

        # Test de connexion directe uniquement
        test_connection = create_direct_connection()
        if test_connection:
            test_connection.close()
            logger.info("✅ Configuration MySQL initialisée et testée")
            # Retourner un objet mock pour Flask-MySQLdb
            return type('MockMySQL', (), {'connection': None})()
        else:
            raise Exception("Impossible de se connecter à MySQL")

    except Exception as e:
        logger.error(f"❌ Erreur init MySQL: {e}")
        raise

# ✅ Connexion directe via MySQLdb
def create_direct_connection():
    try:
        # Configuration de base avec encodage latin1 compatible
        connection = MySQLdb.connect(
            host=os.getenv('MYSQL_HOST', 'localhost'),
            user=os.getenv('MYSQL_USER', 'root'),
            passwd=os.getenv('MYSQL_PASSWORD', 'infosef'),
            db=os.getenv('MYSQL_DATABASE', 'bd_eduise'),
            cursorclass=MySQLdb.cursors.DictCursor,
            autocommit=True,
            connect_timeout=10,
            charset='latin1'
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
            logger.error("❌ Variables de connexion DB manquantes")
            raise ValueError("Variables de connexion DB manquantes")

        db_uri = f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}?charset=latin1"
        db = CustomSQLDatabase.from_uri(db_uri)
        
        # Test de connexion
        test_result = db.run("SELECT 1 as test")
        if not test_result:
            raise Exception("Test de connexion échoué")
            
        logger.info("✅ Connexion LangChain SQLDatabase établie")
        return db

    except Exception as e:
        logger.error(f"❌ Erreur connexion LangChain: {e}")
        # Au lieu de retourner None, on lève une exception pour être plus explicite
        raise Exception(f"Impossible d'établir la connexion à la base de données: {str(e)}")

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