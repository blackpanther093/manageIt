import mysql.connector
# from flask import current_app
from dotenv import load_dotenv
import os

dotenv_path = os.path.join(os.path.dirname(__file__), 'myenv', '.env')
load_dotenv(dotenv_path=dotenv_path)

DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')

# print(f"DB_HOST: {DB_HOST}")
# print(f"DB_USER: {DB_USER}")
# print(f"DB_PASSWORD: {DB_PASSWORD}")
# print(f"DB_NAME: {DB_NAME}")

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = connection.cursor()
        cursor.execute("SET time_zone = '+05:30';")  # Set time zone for this session
        cursor.close()
        return connection
    except mysql.connector.Error as e:
        print(f"Error connecting to database {DB_NAME}: {e}")
        return None
    
def is_valid_student(student_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT s_id FROM students WHERE s_id = %s", (student_id,))
    student = cursor.fetchone()
    cursor.close()
    connection.close()
    return student is not None