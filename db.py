import mysql.connector

def get_db_connection(db_name=None):
    try:
        return mysql.connector.connect(
            host='localhost',
            user='root',
            password='Goy@l123',
            database=db_name if db_name else 'mess_management'
        )
    except mysql.connector.Error as e:
        print(f"Error connecting to database {db_name}: {e}")
        return None

def is_valid_student(student_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT s_id FROM students WHERE s_id = %s", (student_id,))
    student = cursor.fetchone()
    cursor.close()
    connection.close()
    return student is not None