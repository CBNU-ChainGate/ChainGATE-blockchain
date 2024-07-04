import mysql.connector
from mysql.connector import Error

class MySQLManager:
    def __init__(self, host, user, password, database):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.connection = None

    def connect(self):
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database
            )
            if self.connection.is_connected():
                print("Connected to MySQL database")
        except Error as e:
            print(f"Error while connecting to MySQL: {e}")

    def close(self):
        if self.connection.is_connected():
            self.connection.close()
            print("MySQL connection is closed")

    def execute_query(self, query, params=None):
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, params)
            self.connection.commit()
            print("Query executed successfully")
        except Error as e:
            print(f"Error: {e}")
        finally:
            cursor.close()

    def fetch_query(self, query, params=None):
        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute(query, params)
            results = cursor.fetchall()
            return results
        except Error as e:
            print(f"Error: {e}")
        finally:
            cursor.close()

# Usage example (uncomment to test directly):
# if __name__ == "__main__":
#     db_manager = MySQLManager(host="localhost", user="root", password="password", database="test_db")
#     db_manager.connect()
#     db_manager.execute_query("CREATE TABLE IF NOT EXISTS example (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(255))")
#     db_manager.execute_query("INSERT INTO example (name) VALUES (%s)", ("John Doe",))
#     results = db_manager.fetch_query("SELECT * FROM example")
#     print(results)
#     db_manager.close()
